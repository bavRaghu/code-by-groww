import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
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
async def test_product_thesis_significance_over_raw_percentage_move(db_session: AsyncSession):
    """
    PROVES THE CORE PRODUCT THESIS:
    Attention ranking is driven by significance evidence, NOT by raw percentage change alone.

    Setup:
    - Stock A: High raw move (+10.0%), but normal volume and normal relative to high-volatility history (z ~ 1.0).
    - Stock B: Smaller raw move (+4.0%), but extremely abnormal relative to very calm history (z ~ 15.0)
      and accompanied by 3.0x volume anomaly.

    Assertion:
    - Stock B receives a HIGHER overall_score than Stock A.
    - Attention ranking places Stock B AHEAD of Stock A, despite Stock A having more than double the raw % return!
    """
    t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)

    # Stock A: High historical volatility (daily moves ~8-10%), median vol = 1000
    inst_a = Instrument(nse_symbol="M4_THESIS_A", company_name="High Volatility Stock A")
    # Stock B: Very low historical volatility (daily moves ~0.1%), median vol = 1000
    inst_b = Instrument(nse_symbol="M4_THESIS_B", company_name="Calm Stock B")
    db_session.add_all([inst_a, inst_b])
    await db_session.commit()

    # Stock A history: prices fluctuate wildly (100 -> 110 -> 99 -> 111 -> 100)
    a_prices = [Decimal("100.0"), Decimal("110.0"), Decimal("99.0"), Decimal("111.0"), Decimal("100.0")]
    for idx, p in enumerate(a_prices):
        db_session.add(MarketObservation(
            instrument_id=inst_a.id,
            price=p,
            volume=1000,
            observed_at=t0 - timedelta(days=5 - idx),
            source="NSE",
            data_status="final",
        ))

    # Stock B history: prices are extremely steady (100.0, 100.1, 100.05, 100.15, 100.1)
    b_prices = [Decimal("100.0"), Decimal("100.1"), Decimal("100.05"), Decimal("100.15"), Decimal("100.1")]
    for idx, p in enumerate(b_prices):
        db_session.add(MarketObservation(
            instrument_id=inst_b.id,
            price=p,
            volume=1000,
            observed_at=t0 - timedelta(days=5 - idx),
            source="NSE",
            data_status="final",
        ))

    # Baseline observations at t0
    base_a = MarketObservation(instrument_id=inst_a.id, price=Decimal("100.0"), volume=1000, observed_at=t0, source="NSE", data_status="final")
    base_b = MarketObservation(instrument_id=inst_b.id, price=Decimal("100.0"), volume=1000, observed_at=t0, source="NSE", data_status="final")
    # Current observations at t1:
    # A moves +10% (100 -> 110), volume = 1000 (normal 1.0x)
    curr_a = MarketObservation(instrument_id=inst_a.id, price=Decimal("110.0"), volume=1000, observed_at=t1, source="NSE", data_status="final")
    # B moves +4% (100 -> 104), volume = 3000 (3.0x median anomaly)
    curr_b = MarketObservation(instrument_id=inst_b.id, price=Decimal("104.0"), volume=3000, observed_at=t1, source="NSE", data_status="final")

    db_session.add_all([base_a, base_b, curr_a, curr_b])
    await db_session.commit()

    # User baselines
    uo_a = UserObservation(user_id=DEV_USER_ID, instrument_id=inst_a.id, last_seen_at=t0, last_seen_observation_id=base_a.id)
    uo_b = UserObservation(user_id=DEV_USER_ID, instrument_id=inst_b.id, last_seen_at=t0, last_seen_observation_id=base_b.id)
    wl = Watchlist(user_id=DEV_USER_ID, name="Thesis Test Watchlist")
    db_session.add_all([uo_a, uo_b, wl])
    await db_session.commit()

    db_session.add_all([
        WatchlistItem(watchlist_id=wl.id, instrument_id=inst_a.id, position=0),
        WatchlistItem(watchlist_id=wl.id, instrument_id=inst_b.id, position=1),
    ])
    await db_session.commit()

    # Evaluate attention feed
    response = await get_watchlist_attention(db=db_session, user_id=DEV_USER_ID, watchlist_id=wl.id)

    assert len(response.attention_items) == 2
    # Verify Stock B (smaller raw move, but massive abnormality & volume corroboration) ranks FIRST
    first_item = response.attention_items[0]
    second_item = response.attention_items[1]

    assert first_item.symbol == "M4_THESIS_B"
    assert second_item.symbol == "M4_THESIS_A"
    assert first_item.percentage_change == Decimal("4.0000")
    assert second_item.percentage_change == Decimal("10.0000")
    assert first_item.overall_score > second_item.overall_score


@pytest.mark.asyncio
async def test_structured_explanation_and_non_causality(db_session: AsyncSession):
    """
    Verifies that attention items include a structured explanation with:
    - what_happened
    - why_it_stands_out
    - supporting_evidence (list of bullets)
    - missing_data_notes
    and that no unsupported causal claims (e.g. 'caused by') appear.
    """
    t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)

    inst = Instrument(nse_symbol="M4_EXP_TCS", company_name="Tata Consultancy Services")
    db_session.add(inst)
    await db_session.commit()

    # Create history
    for i in range(5):
        db_session.add(MarketObservation(
            instrument_id=inst.id,
            price=Decimal("4000.0") + Decimal(str(i)),
            volume=500000,
            observed_at=t0 - timedelta(days=5 - i),
            source="NSE",
            data_status="final",
        ))

    ob0 = MarketObservation(instrument_id=inst.id, price=Decimal("4000.0"), volume=500000, observed_at=t0, source="NSE", data_status="final")
    ob1 = MarketObservation(instrument_id=inst.id, price=Decimal("4170.8"), volume=1100000, observed_at=t1, source="NSE", data_status="final")
    db_session.add_all([ob0, ob1])
    await db_session.commit()

    uo = UserObservation(user_id=DEV_USER_ID, instrument_id=inst.id, last_seen_at=t0, last_seen_observation_id=ob0.id)
    wl = Watchlist(user_id=DEV_USER_ID, name="Explanation WL")
    db_session.add_all([uo, wl])
    await db_session.commit()
    db_session.add(WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=0))
    await db_session.commit()

    bench_mock = MockBenchmarkProvider(benchmark_return=Decimal("0.0050"))
    res = await get_watchlist_attention(db=db_session, user_id=DEV_USER_ID, watchlist_id=wl.id, benchmark_provider=bench_mock)

    assert len(res.attention_items) == 1
    item = res.attention_items[0]

    # Structured explanation fields
    struct_exp = item.structured_explanation
    assert struct_exp.what_happened != ""
    assert "M4_EXP_TCS moved +4.27%" in struct_exp.what_happened
    assert "₹170.80" in struct_exp.what_happened
    assert "unusually large" in struct_exp.why_it_stands_out.lower() or "noteworthy" in struct_exp.why_it_stands_out.lower()
    assert len(struct_exp.supporting_evidence) >= 2

    # Verify volume bullet
    assert any("2.2×" in bullet or "median" in bullet for bullet in struct_exp.supporting_evidence)

    # Strictly non-causal verification
    full_text = (item.explanation + " " + struct_exp.what_happened + " " + struct_exp.why_it_stands_out + " " + " ".join(struct_exp.supporting_evidence)).lower()
    assert "caused by" not in full_text
    assert "because of" not in full_text
    assert "due to earnings" not in full_text


@pytest.mark.asyncio
async def test_realistic_20_stocks_watchlist_lifecycle(client: AsyncClient, db_session: AsyncSession):
    """
    Creates the realistic user experience scenario specified in Milestone 4:
    - Watchlist of 20 instruments.
    - User establishes baseline (POST /check).
    - Market updates arrive:
      * 1 stock moves significantly (+12%, high volume, abnormal -> HIGH)
      * 1 stock moves moderately (+4.5%, abnormal -> MEDIUM)
      * 1 stock moves modestly (+2.5% -> LOW)
      * 17 stocks have negligible or no change (NONE or 0.0%)
    - GET /api/v1/watchlists/{id}/attention returns:
      * "3 stocks deserve your attention"
      * "17 stocks had no meaningful changes"
      * Ranking: HIGH -> MEDIUM -> LOW
      * Exactly 1 attention item per episode
    - User clicks "Mark as Checked" -> baseline advances.
    - Calling GET /api/v1/watchlists/{id}/attention again returns 0 attention items (all caught up).
    """
    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)

    # 1. Create 20 instruments
    instruments = []
    for i in range(20):
        inst = Instrument(nse_symbol=f"M4_REAL_{i:02d}", company_name=f"Realistic Stock {i:02d}")
        db_session.add(inst)
        instruments.append(inst)
    await db_session.commit()

    # Create watchlist
    wl_res = await client.post("/api/v1/watchlists", json={"name": "Realistic 20 Stocks Portfolio"})
    assert wl_res.status_code == 201
    wl_id = wl_res.json()["id"]

    for inst in instruments:
        await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # Add baseline observations at t0 for all 20 instruments with realistic historical variance
    hist_prices = [
        Decimal("985.00"),
        Decimal("1010.00"),
        Decimal("990.00"),
        Decimal("1005.00"),
    ]
    for inst in instruments:
        for h, hp in enumerate(hist_prices):
            db_session.add(MarketObservation(
                instrument_id=inst.id,
                price=hp,
                volume=50000,
                observed_at=t0 - timedelta(days=4 - h),
                source="NSE",
                data_status="final",
            ))
        db_session.add(MarketObservation(
            instrument_id=inst.id,
            price=Decimal("1000.00"),
            volume=50000,
            observed_at=t0,
            source="NSE",
            data_status="final",
        ))
    await db_session.commit()

    # User establishes initial baseline
    check_a = await client.post(f"/api/v1/watchlists/{wl_id}/check")
    assert check_a.status_code == 200

    # Market advances to t1:
    # Stock 0: HIGH (+12% move to ₹1120, 2.5x volume)
    db_session.add(MarketObservation(instrument_id=instruments[0].id, price=Decimal("1120.00"), volume=125000, observed_at=t1, source="NSE", data_status="final"))
    # Stock 1: MEDIUM (+4.5% move to ₹1045, normal volume)
    db_session.add(MarketObservation(instrument_id=instruments[1].id, price=Decimal("1045.00"), volume=50000, observed_at=t1, source="NSE", data_status="final"))
    # Stock 2: LOW (+2.2% move to ₹1022, normal volume)
    db_session.add(MarketObservation(instrument_id=instruments[2].id, price=Decimal("1022.00"), volume=50000, observed_at=t1, source="NSE", data_status="final"))

    # Stocks 3-19 (17 stocks): 10 remain unchanged (₹1000), 7 have negligible 0.01% fluctuation (NONE)
    for i in range(3, 10):
        db_session.add(MarketObservation(instrument_id=instruments[i].id, price=Decimal("1000.00"), volume=50000, observed_at=t1, source="NSE", data_status="final"))
    for i in range(10, 20):
        db_session.add(MarketObservation(instrument_id=instruments[i].id, price=Decimal("1000.10"), volume=50000, observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()

    # Query Attention Endpoint
    attn_res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn_res.status_code == 200
    data = attn_res.json()

    summary = data["summary"]
    # Total instruments = 20
    assert summary["total_instruments"] == 20
    assert summary["instruments_evaluated"] == 20
    # 3 stocks deserve attention
    assert summary["attention_count"] == 3
    assert summary["high_count"] == 1
    assert summary["medium_count"] == 1
    assert summary["low_count"] == 1
    # 17 stocks had no meaningful changes
    assert summary["no_meaningful_change_count"] == 17
    assert summary["insufficient_data_count"] == 0

    # Exactly 3 attention items surfaced in feed
    items = data["items"]
    assert len(items) == 3
    # Verify ranking: HIGH -> MEDIUM -> LOW
    assert items[0]["significance_level"] == "HIGH"
    assert items[0]["symbol"] == "M4_REAL_00"
    assert items[1]["significance_level"] == "MEDIUM"
    assert items[1]["symbol"] == "M4_REAL_01"
    assert items[2]["significance_level"] == "LOW"
    assert items[2]["symbol"] == "M4_REAL_02"

    # Verify structured explanation
    assert "structured_explanation" in items[0]
    assert items[0]["structured_explanation"]["what_happened"] != ""

    # Verify quiet instruments list contains 17 stocks
    assert len(data["quiet_instruments"]) == 17

    # Advancing baseline clears the attention feed
    check_b = await client.post(f"/api/v1/watchlists/{wl_id}/check")
    assert check_b.status_code == 200

    # Subsequent call returns 0 attention items
    attn_res2 = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn_res2.status_code == 200
    data2 = attn_res2.json()
    assert data2["summary"]["attention_count"] == 0
    assert data2["summary"]["no_meaningful_change_count"] == 20
    assert len(data2["items"]) == 0


@pytest.mark.asyncio
async def test_insufficient_data_diagnostics_separation(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that instruments with missing baseline or missing observations
    are categorized as 'insufficient_data_count' rather than 'no_meaningful_change_count'.
    """
    inst_ok = Instrument(nse_symbol="M4_DIAG_OK", company_name="Observed Stock")
    inst_nobase = Instrument(nse_symbol="M4_DIAG_NOBASE", company_name="Unchecked Stock")
    db_session.add_all([inst_ok, inst_nobase])
    await db_session.commit()

    wl_res = await client.post("/api/v1/watchlists", json={"name": "Diagnostics Test WL"})
    wl_id = wl_res.json()["id"]

    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst_ok.id})

    t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    obs = MarketObservation(instrument_id=inst_ok.id, price=Decimal("100.0"), observed_at=t0, source="NSE", data_status="final")
    db_session.add(obs)
    await db_session.commit()

    # User establishes baseline for inst_ok
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # Now add inst_nobase to watchlist (has no observation and no baseline)
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst_nobase.id})

    # Query attention
    res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert res.status_code == 200
    data = res.json()

    # Total = 2, insufficient data = 1, evaluated = 1, no meaningful change = 1
    assert data["summary"]["total_instruments"] == 2
    assert data["summary"]["insufficient_data_count"] == 1
    assert data["summary"]["instruments_evaluated"] == 1
    assert data["summary"]["no_meaningful_change_count"] == 1
    assert len(data["insufficient_data_instruments"]) == 1
    assert data["insufficient_data_instruments"][0]["symbol"] == "M4_DIAG_NOBASE"
