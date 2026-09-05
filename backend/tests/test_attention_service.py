import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detected_change import DetectedChange
from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.significance_assessment import SignificanceAssessment, SignificanceLevel
from app.models.user_observation import UserObservation
from app.models.watchlist import Watchlist, WatchlistItem
from app.providers.benchmark import BenchmarkProvider
from app.services.attention import get_watchlist_attention
from app.seed import DEV_USER_ID


class MockBenchmarkProvider(BenchmarkProvider):
    def __init__(self, benchmark_return: Decimal | None = None):
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
async def test_episode_grouping_prevents_double_counting(db_session: AsyncSession):
    """
    Tests that multiple candidate changes for a single stock episode
    (e.g., PRICE_MOVE + ABNORMAL_RETURN + VOLUME_ANOMALY) are grouped
    into a SINGLE AttentionItem rather than 3 separate cards.
    """
    t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Create instrument with history to trigger multiple change candidates
    inst = Instrument(nse_symbol="ATTN_GRP_1", company_name="Attention Grouping Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    # Historical observations for statistics (mean ~0, stddev ~0.01, median vol = 1000)
    for i in range(5):
        hist_t = t0 - timedelta(days=5 - i)
        p = Decimal("100.0000") + Decimal(str(i * 0.1))
        db_session.add(
            MarketObservation(
                instrument_id=inst.id,
                price=p,
                volume=1000,
                observed_at=hist_t,
                source="NSE",
                data_status="final",
            )
        )

    # Baseline observation at t0 (price = 100, volume = 1000)
    obs_base = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("100.0000"),
        volume=1000,
        observed_at=t0,
        source="NSE",
        data_status="final",
    )
    # Current observation at t1 (price = 110 (+10%), volume = 2500 (2.5x))
    obs_curr = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("110.0000"),
        volume=2500,
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add_all([obs_base, obs_curr])
    await db_session.commit()
    await db_session.refresh(obs_base)
    await db_session.refresh(obs_curr)

    # User baseline set to obs_base
    uobs = UserObservation(
        user_id=DEV_USER_ID,
        instrument_id=inst.id,
        last_seen_at=t0,
        last_seen_observation_id=obs_base.id,
    )
    wl = Watchlist(user_id=DEV_USER_ID, name="Grouping Watchlist")
    db_session.add_all([uobs, wl])
    await db_session.commit()
    await db_session.refresh(wl)

    wl_item = WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=0)
    db_session.add(wl_item)
    await db_session.commit()

    # Call get_watchlist_attention
    bench_mock = MockBenchmarkProvider(benchmark_return=Decimal("0.0100"))  # NIFTY +1%
    result = await get_watchlist_attention(
        db=db_session,
        user_id=DEV_USER_ID,
        watchlist_id=wl.id,
        benchmark_provider=bench_mock,
    )

    # Verification:
    # Multiple candidate changes were generated (PRICE_MOVE, ABNORMAL_RETURN, RELATIVE_PERFORMANCE, VOLUME_ANOMALY)
    # But only ONE AttentionItem is in the ranked feed!
    assert len(result.attention_items) == 1
    item = result.attention_items[0]
    assert item.symbol == "ATTN_GRP_1"
    assert "PRICE_MOVE" in item.constituent_change_types
    assert "ABNORMAL_RETURN" in item.constituent_change_types
    assert "VOLUME_ANOMALY" in item.constituent_change_types
    assert "RELATIVE_PERFORMANCE" in item.constituent_change_types

    # Verify scores are populated and bounded
    assert Decimal("0.0") <= item.overall_score <= Decimal("1.0")
    assert item.significance_level in ("HIGH", "MEDIUM")
    assert item.component_scores.magnitude is not None
    assert item.component_scores.abnormality is not None
    assert item.component_scores.volume is not None
    assert item.component_scores.relative_performance is not None

    # Verify non-causal explanation
    assert "caused by" not in item.explanation.lower()
    assert "accompanied by" in item.explanation.lower() or "unusually" in item.explanation.lower()

    # Verify persistence: check significance_assessments table for this instrument
    ass_stmt = (
        select(SignificanceAssessment)
        .join(DetectedChange, SignificanceAssessment.detected_change_id == DetectedChange.id)
        .where(DetectedChange.instrument_id == inst.id)
    )
    ass_rows = (await db_session.execute(ass_stmt)).scalars().all()
    # Each detected change candidate got an assessment record
    assert len(ass_rows) >= 3
    for ass in ass_rows:
        assert ass.overall_score == item.overall_score
        assert ass.significance_level == item.significance_level



@pytest.mark.asyncio
async def test_deterministic_attention_ranking_order(db_session: AsyncSession):
    """
    Tests ranking criteria:
    1. overall_score DESCENDING
    2. available evidence count DESCENDING
    3. symbol ASCENDING (alphabetical tie-breaker)
    """
    t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)

    # Create 3 stocks:
    # Stock A: High move (+12%)
    # Stock B: Moderate move (+4%)
    # Stock C: High move (+12%), same score as A, but alphabetically after A
    inst_a = Instrument(nse_symbol="ATTN_RNK_A", company_name="Rank A Corp")
    inst_b = Instrument(nse_symbol="ATTN_RNK_B", company_name="Rank B Corp")
    inst_c = Instrument(nse_symbol="ATTN_RNK_C", company_name="Rank C Corp")
    db_session.add_all([inst_a, inst_b, inst_c])
    await db_session.commit()

    for inst, p0, p1 in [(inst_a, Decimal("100"), Decimal("112")),
                         (inst_b, Decimal("100"), Decimal("104")),
                         (inst_c, Decimal("100"), Decimal("112"))]:
        ob0 = MarketObservation(instrument_id=inst.id, price=p0, observed_at=t0, source="NSE", data_status="final")
        ob1 = MarketObservation(instrument_id=inst.id, price=p1, observed_at=t1, source="NSE", data_status="final")
        db_session.add_all([ob0, ob1])
        await db_session.commit()

        uo = UserObservation(user_id=DEV_USER_ID, instrument_id=inst.id, last_seen_at=t0, last_seen_observation_id=ob0.id)
        db_session.add(uo)

    wl = Watchlist(user_id=DEV_USER_ID, name="Ranking Watchlist")
    db_session.add(wl)
    await db_session.commit()

    db_session.add_all([
        WatchlistItem(watchlist_id=wl.id, instrument_id=inst_b.id, position=0),
        WatchlistItem(watchlist_id=wl.id, instrument_id=inst_c.id, position=1),
        WatchlistItem(watchlist_id=wl.id, instrument_id=inst_a.id, position=2),
    ])
    await db_session.commit()

    result = await get_watchlist_attention(db=db_session, user_id=DEV_USER_ID, watchlist_id=wl.id)

    # All 3 have meaningful changes (>= 4% move gives >= 0.20 score)
    assert len(result.attention_items) == 3
    # Top two should be A and C (highest score ~12% move), with A before C alphabetically
    assert result.attention_items[0].symbol == "ATTN_RNK_A"
    assert result.attention_items[1].symbol == "ATTN_RNK_C"
    # Third should be B (lower score ~4% move)
    assert result.attention_items[2].symbol == "ATTN_RNK_B"
    assert result.attention_items[0].overall_score >= result.attention_items[2].overall_score


@pytest.mark.asyncio
async def test_repeated_attention_calls_are_idempotent(db_session: AsyncSession):
    """
    Tests that calling get_watchlist_attention multiple times updates existing records
    and does NOT create duplicate SignificanceAssessment records.
    """
    t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)

    inst = Instrument(nse_symbol="ATTN_IDEMP_1", company_name="Idempotency Corp")
    db_session.add(inst)
    await db_session.commit()

    ob0 = MarketObservation(instrument_id=inst.id, price=Decimal("500.00"), observed_at=t0, source="NSE", data_status="final")
    ob1 = MarketObservation(instrument_id=inst.id, price=Decimal("530.00"), observed_at=t1, source="NSE", data_status="final")
    db_session.add_all([ob0, ob1])
    await db_session.commit()

    uo = UserObservation(user_id=DEV_USER_ID, instrument_id=inst.id, last_seen_at=t0, last_seen_observation_id=ob0.id)
    wl = Watchlist(user_id=DEV_USER_ID, name="Idempotent WL")
    db_session.add_all([uo, wl])
    await db_session.commit()

    db_session.add(WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=0))
    await db_session.commit()

    # First call
    res1 = await get_watchlist_attention(db=db_session, user_id=DEV_USER_ID, watchlist_id=wl.id)
    count_stmt = (
        select(SignificanceAssessment)
        .join(DetectedChange, SignificanceAssessment.detected_change_id == DetectedChange.id)
        .where(DetectedChange.instrument_id == inst.id)
    )
    count1 = len((await db_session.execute(count_stmt)).scalars().all())

    # Second call
    res2 = await get_watchlist_attention(db=db_session, user_id=DEV_USER_ID, watchlist_id=wl.id)
    count2 = len((await db_session.execute(count_stmt)).scalars().all())

    assert count1 == count2
    assert count1 > 0
    assert res1.attention_items[0].overall_score == res2.attention_items[0].overall_score

