import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detected_change import ChangeType, DetectedChange
from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.user_observation import UserObservation
from app.models.watchlist import Watchlist, WatchlistItem
from app.providers.benchmark import BenchmarkProvider
from app.services.change_detection import detect_changes_for_watchlist
from app.services.user_observation import mark_watchlist_checked
from app.seed import DEV_USER_ID


class MockBenchmarkProvider(BenchmarkProvider):
    def __init__(self, benchmark_return: Decimal | None):
        self.benchmark_return = benchmark_return

    async def get_benchmark_return(
        self,
        db: AsyncSession,
        start_time: datetime,
        end_time: datetime,
        benchmark_symbol: str = "NIFTY 50",
    ) -> Decimal | None:
        return self.benchmark_return


@pytest.mark.asyncio
async def test_price_move_detection(db_session: AsyncSession):
    """
    Tests that a newer observation with a price change generates a PRICE_MOVE candidate.
    Tests formula: ((current_price - baseline_price) / baseline_price) * 100.
    """
    t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)

    inst = Instrument(nse_symbol="TEST_PM_INST", company_name="Price Move Test Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    # Create baseline observation
    obs0 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("2000.0000"),
        observed_at=t0,
        source="NSE",
        data_status="final",
    )
    # Create current observation (+5% move)
    obs1 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("2100.0000"),
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add_all([obs0, obs1])
    await db_session.commit()
    await db_session.refresh(obs0)
    await db_session.refresh(obs1)

    # Set user observation baseline to obs0
    uobs = UserObservation(
        user_id=DEV_USER_ID,
        instrument_id=inst.id,
        last_seen_at=t0,
        last_seen_observation_id=obs0.id,
    )
    wl = Watchlist(user_id=DEV_USER_ID, name="Price Move WL")
    db_session.add_all([uobs, wl])
    await db_session.commit()
    await db_session.refresh(wl)

    wl_item = WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=0)
    db_session.add(wl_item)
    await db_session.commit()

    # Run detection
    result = await detect_changes_for_watchlist(db_session, DEV_USER_ID, wl.id)

    price_moves = [c for c in result.changes if c.change_type == ChangeType.PRICE_MOVE.value]
    assert len(price_moves) == 1
    pm = price_moves[0]
    assert pm.baseline_observation_id == obs0.id
    assert pm.current_observation_id == obs1.id
    assert pm.magnitude == Decimal("5.0000")
    assert pm.evidence["absolute_change"] == 100.0
    assert pm.evidence["percentage_change"] == 5.0
    assert pm.evidence["baseline_price"] == 2000.0
    assert pm.evidence["current_price"] == 2100.0


@pytest.mark.asyncio
async def test_no_price_move_candidate_if_price_unchanged(db_session: AsyncSession):
    """Verifies that no PRICE_MOVE candidate is generated if price is identical."""
    t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)

    inst = Instrument(nse_symbol="TEST_UNCHANGED", company_name="Unchanged Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    obs0 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("800.0000"),
        observed_at=t0,
        source="NSE",
        data_status="final",
    )
    obs1 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("800.0000"),
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add_all([obs0, obs1])
    await db_session.commit()

    uobs = UserObservation(
        user_id=DEV_USER_ID,
        instrument_id=inst.id,
        last_seen_at=t0,
        last_seen_observation_id=obs0.id,
    )
    wl = Watchlist(user_id=DEV_USER_ID, name="Unchanged Price WL")
    db_session.add_all([uobs, wl])
    await db_session.commit()

    wl_item = WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=0)
    db_session.add(wl_item)
    await db_session.commit()

    result = await detect_changes_for_watchlist(db_session, DEV_USER_ID, wl.id)
    price_moves = [c for c in result.changes if c.change_type == ChangeType.PRICE_MOVE.value]
    assert len(price_moves) == 0


@pytest.mark.asyncio
async def test_abnormal_return_detection_with_sufficient_history(db_session: AsyncSession):
    """
    Tests ABNORMAL_RETURN candidate generation:
    Creates historical observations strictly before current observation,
    calculates returns, mean, stddev, and z-score.
    """
    inst = Instrument(nse_symbol="TEST_ABNORMAL", company_name="Abnormal Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    base_time = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    prices = [Decimal("1000.0"), Decimal("1010.0"), Decimal("1020.0"), Decimal("1015.0"), Decimal("1025.0")]
    for i, p in enumerate(prices):
        obs = MarketObservation(
            instrument_id=inst.id,
            price=p,
            observed_at=base_time + timedelta(days=i),
            source="NSE",
            data_status="final",
        )
        db_session.add(obs)
    await db_session.commit()

    # Baseline observation (Day 5)
    t_base = base_time + timedelta(days=5)
    obs_base = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1025.0"),
        observed_at=t_base,
        source="NSE",
        data_status="final",
    )
    # Current observation (Day 6, big jump to 1100.0, ~7.3% jump)
    t_curr = base_time + timedelta(days=6)
    obs_curr = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1100.0"),
        observed_at=t_curr,
        source="NSE",
        data_status="final",
    )
    db_session.add_all([obs_base, obs_curr])
    await db_session.commit()

    uobs = UserObservation(
        user_id=DEV_USER_ID,
        instrument_id=inst.id,
        last_seen_at=t_base,
        last_seen_observation_id=obs_base.id,
    )
    wl = Watchlist(user_id=DEV_USER_ID, name="Abnormal Return WL")
    db_session.add_all([uobs, wl])
    await db_session.commit()

    wl_item = WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=0)
    db_session.add(wl_item)
    await db_session.commit()

    result = await detect_changes_for_watchlist(
        db_session, DEV_USER_ID, wl.id, min_history_sample_size=3
    )

    abnormal_moves = [c for c in result.changes if c.change_type == ChangeType.ABNORMAL_RETURN.value]
    assert len(abnormal_moves) == 1
    am = abnormal_moves[0]
    assert "z_score" in am.evidence
    assert am.evidence["z_score"] > 0
    assert am.evidence["sample_size"] >= 3
    assert "historical_mean" in am.evidence
    assert "historical_stddev" in am.evidence


@pytest.mark.asyncio
async def test_relative_performance_detection(db_session: AsyncSession):
    """
    Tests RELATIVE_PERFORMANCE:
    When benchmark return is provided via BenchmarkProvider,
    calculates excess return: stock_return - benchmark_return.
    """
    inst = Instrument(nse_symbol="TEST_RELPERF", company_name="Relative Perf Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)

    # Stock moves from 1000 to 1050 (+5%)
    obs0 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1000.0000"),
        observed_at=t0,
        source="NSE",
        data_status="final",
    )
    obs1 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1050.0000"),
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add_all([obs0, obs1])
    await db_session.commit()

    uobs = UserObservation(
        user_id=DEV_USER_ID,
        instrument_id=inst.id,
        last_seen_at=t0,
        last_seen_observation_id=obs0.id,
    )
    wl = Watchlist(user_id=DEV_USER_ID, name="Relative Perf WL")
    db_session.add_all([uobs, wl])
    await db_session.commit()

    wl_item = WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=0)
    db_session.add(wl_item)
    await db_session.commit()

    # Benchmark moved +2% (0.02)
    mock_bench = MockBenchmarkProvider(benchmark_return=Decimal("0.02"))

    result = await detect_changes_for_watchlist(
        db_session, DEV_USER_ID, wl.id, benchmark_provider=mock_bench
    )

    rel_perf = [c for c in result.changes if c.change_type == ChangeType.RELATIVE_PERFORMANCE.value]
    assert len(rel_perf) == 1
    rp = rel_perf[0]
    # Stock 5% - Bench 2% = 3% excess return
    assert rp.magnitude == Decimal("3.0000")
    assert rp.evidence["excess_return"] == 0.03
    assert rp.evidence["stock_return"] == 0.05
    assert rp.evidence["benchmark_return"] == 0.02


@pytest.mark.asyncio
async def test_volume_anomaly_detection(db_session: AsyncSession):
    """
    Tests VOLUME_ANOMALY:
    When current volume significantly exceeds historical median (ratio >= 1.25).
    """
    inst = Instrument(nse_symbol="TEST_VOLANOM", company_name="Volume Anomaly Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    base_time = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
    # 3 historical observations with median volume 1,000,000
    for i, vol in enumerate([900000, 1000000, 1100000]):
        obs = MarketObservation(
            instrument_id=inst.id,
            price=Decimal("4000.0"),
            volume=vol,
            observed_at=base_time + timedelta(days=i),
            source="NSE",
            data_status="final",
        )
        db_session.add(obs)
    await db_session.commit()

    t_base = base_time + timedelta(days=3)
    obs_base = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("4000.0"),
        volume=1000000,
        observed_at=t_base,
        source="NSE",
        data_status="final",
    )
    # Current observation has spike to 2,000,000 (2.0x median)
    t_curr = base_time + timedelta(days=4)
    obs_curr = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("4050.0"),
        volume=2000000,
        observed_at=t_curr,
        source="NSE",
        data_status="final",
    )
    db_session.add_all([obs_base, obs_curr])
    await db_session.commit()

    uobs = UserObservation(
        user_id=DEV_USER_ID,
        instrument_id=inst.id,
        last_seen_at=t_base,
        last_seen_observation_id=obs_base.id,
    )
    wl = Watchlist(user_id=DEV_USER_ID, name="Volume Anomaly WL")
    db_session.add_all([uobs, wl])
    await db_session.commit()

    wl_item = WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=0)
    db_session.add(wl_item)
    await db_session.commit()

    result = await detect_changes_for_watchlist(
        db_session, DEV_USER_ID, wl.id, min_volume_sample_size=3
    )

    vol_anomalies = [c for c in result.changes if c.change_type == ChangeType.VOLUME_ANOMALY.value]
    assert len(vol_anomalies) == 1
    va = vol_anomalies[0]
    assert va.magnitude == Decimal("2.0000")
    assert va.evidence["volume_ratio"] == 2.0
    assert va.evidence["historical_median_volume"] == 1000000.0


@pytest.mark.asyncio
async def test_repeated_detection_is_idempotent(db_session: AsyncSession):
    """Verifies that running detection twice creates no duplicate DetectedChange rows."""
    inst = Instrument(nse_symbol="TEST_IDEMPOTENT", company_name="Idempotent Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)

    obs0 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1500.0000"),
        observed_at=t0,
        source="NSE",
        data_status="final",
    )
    obs1 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1550.0000"),
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add_all([obs0, obs1])
    await db_session.commit()

    uobs = UserObservation(
        user_id=DEV_USER_ID,
        instrument_id=inst.id,
        last_seen_at=t0,
        last_seen_observation_id=obs0.id,
    )
    wl = Watchlist(user_id=DEV_USER_ID, name="Idempotent WL")
    db_session.add_all([uobs, wl])
    await db_session.commit()

    wl_item = WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=0)
    db_session.add(wl_item)
    await db_session.commit()

    # Run detection first time
    res1 = await detect_changes_for_watchlist(db_session, DEV_USER_ID, wl.id)
    count1 = len(res1.changes)
    assert count1 > 0

    # Run detection second time
    res2 = await detect_changes_for_watchlist(db_session, DEV_USER_ID, wl.id)
    assert len(res2.changes) == count1

    # Verify directly from DB that total records matching identity is count1
    all_db_changes = (
        await db_session.execute(
            select(DetectedChange).where(
                DetectedChange.user_id == DEV_USER_ID,
                DetectedChange.instrument_id == inst.id,
                DetectedChange.baseline_observation_id == obs0.id,
                DetectedChange.current_observation_id == obs1.id,
            )
        )
    ).scalars().all()
    assert len(all_db_changes) == count1


@pytest.mark.asyncio
async def test_baseline_advances_and_clears_changes_relative_to_new_baseline(db_session: AsyncSession):
    """
    Explicitly verifies items 12, 13, and 14:
    12. Verify the baseline moves to observation B when checked.
    13. Run detection again.
    14. Verify previously detected changes are no longer treated as new changes relative to the new baseline.
    """
    inst = Instrument(nse_symbol="TEST_STEP12_14", company_name="Step 12-14 Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl = Watchlist(user_id=DEV_USER_ID, name="Step 12-14 WL")
    db_session.add(wl)
    await db_session.commit()
    await db_session.refresh(wl)

    wl_item = WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=0)
    db_session.add(wl_item)
    await db_session.commit()

    # Observation A: Sep 3
    t_a = datetime(2026, 9, 3, 15, 30, tzinfo=timezone.utc)
    obs_a = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1000.0000"),
        observed_at=t_a,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs_a)
    await db_session.commit()
    await db_session.refresh(obs_a)

    # Initial check sets baseline to Obs A
    await mark_watchlist_checked(db_session, DEV_USER_ID, wl.id)

    # Observation B arrives: Sep 4
    t_b = datetime(2026, 9, 4, 15, 30, tzinfo=timezone.utc)
    obs_b = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1100.0000"),
        observed_at=t_b,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs_b)
    await db_session.commit()
    await db_session.refresh(obs_b)

    # Detection 1 finds change between A and B
    res1 = await detect_changes_for_watchlist(db_session, DEV_USER_ID, wl.id)
    assert len(res1.changes) >= 1
    assert res1.changes[0].baseline_observation_id == obs_a.id
    assert res1.changes[0].current_observation_id == obs_b.id

    # 12. User marks watchlist checked -> baseline moves to Obs B
    await mark_watchlist_checked(db_session, DEV_USER_ID, wl.id)
    uobs = (
        await db_session.execute(
            select(UserObservation).where(
                UserObservation.user_id == DEV_USER_ID,
                UserObservation.instrument_id == inst.id,
            )
        )
    ).scalar_one()
    assert uobs.last_seen_observation_id == obs_b.id

    # 13. Run detection again
    res2 = await detect_changes_for_watchlist(db_session, DEV_USER_ID, wl.id)

    # 14. Verify previously detected changes are no longer treated as new changes relative to the new baseline
    assert len(res2.changes) == 0
    assert any(s.instrument_id == inst.id and s.status == "up_to_date" for s in res2.instrument_statuses)
