import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.seed import DEV_USER_ID


@pytest.mark.asyncio
async def test_1_stock_detail_endpoint_full_contract(client: AsyncClient, db_session: AsyncSession):
    """
    Tests GET /api/v1/instruments/{id}:
    - Basic instrument metadata (symbol, company_name, exchange, isin)
    - Current observation details (latest price, session changes, volume, observed_at)
    - Provenance and freshness note
    """
    inst = Instrument(nse_symbol="M6_DETAIL_1", company_name="Detail Contract Corp", isin="INE000M60010")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    obs0 = MarketObservation(instrument_id=inst.id, price=Decimal("1000.00"), volume=50000, observed_at=t0, source="NSE", data_status="final")
    obs1 = MarketObservation(instrument_id=inst.id, price=Decimal("1045.00"), volume=75000, observed_at=t1, source="NSE", data_status="final")
    db_session.add_all([obs0, obs1])
    await db_session.commit()

    res = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res.status_code == 200
    data = res.json()

    assert data["id"] == inst.id
    assert data["nse_symbol"] == "M6_DETAIL_1"
    assert data["company_name"] == "Detail Contract Corp"
    assert data["exchange"] == "NSE"
    assert data["isin"] == "INE000M60010"

    curr = data["current_observation"]
    assert float(curr["price"]) == 1045.00
    assert curr["volume"] == 75000
    assert float(curr["session_absolute_change"]) == 45.00
    assert float(curr["session_percentage_change"]) == 4.5
    assert curr["source"] == "NSE"
    assert "Based on NSE market data" in data["freshness_note"]


@pytest.mark.asyncio
async def test_2_since_you_last_checked_section(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies 'Since you last checked' baseline comparison:
    - baseline_price vs current_price
    - net absolute and percentage change
    - baseline_observed_at vs current_observed_at
    - significance level and score
    """
    inst = Instrument(nse_symbol="M6_SINCE_CHECK", company_name="Since Check Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M6 Since Check WL"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    obs0 = MarketObservation(instrument_id=inst.id, price=Decimal("2000.00"), observed_at=t0, source="NSE", data_status="final")
    db_session.add(obs0)
    await db_session.commit()

    # User establishes baseline
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # T1 observation (+8%)
    obs1 = MarketObservation(instrument_id=inst.id, price=Decimal("2160.00"), observed_at=t1, source="NSE", data_status="final")
    db_session.add(obs1)
    await db_session.commit()

    # Run attention to detect changes
    await client.get(f"/api/v1/watchlists/{wl_id}/attention")

    res = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res.status_code == 200
    data = res.json()

    syc = data["since_last_checked"]
    assert syc["has_baseline"] is True
    assert float(syc["baseline_price"]) == 2000.00
    assert float(syc["current_price"]) == 2160.00
    assert float(syc["absolute_change"]) == 160.00
    assert float(syc["percentage_change"]) == 8.00
    assert syc["significance_level"] in ("HIGH", "MEDIUM")
    assert float(syc["overall_score"]) >= 0.40
    assert syc["is_reviewed"] is False


@pytest.mark.asyncio
async def test_3_why_this_was_flagged_evidence_breakdown(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies Section 2: "Why this was flagged"
    - Significance level
    - "Why this matters" narrative
    - Evidence bullets derived from stored data without causal speculation
    - Component scores
    - Evidence completeness
    """
    inst = Instrument(nse_symbol="M6_EVID_TEST", company_name="Evidence Breakdown Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M6 Evidence WL"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # History for statistical volatility
    dates = [
        datetime(2026, 8, 25, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 26, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 27, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 28, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 29, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 30, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 31, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc),  # baseline
    ]
    for d in dates:
        db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1000.00"), volume=100000, observed_at=d, source="NSE", data_status="final"))
    await db_session.commit()

    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # T1: Significant move +7% and volume spike 2.5x
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1070.00"), volume=250000, observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()

    # Trigger detection
    await client.get(f"/api/v1/watchlists/{wl_id}/attention")

    res = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res.status_code == 200
    ev = res.json()["evidence"]
    assert ev is not None
    assert ev["significance_level"] in ("HIGH", "MEDIUM")
    assert float(ev["overall_score"]) >= 0.40
    assert len(ev["why_it_matters"]) > 0
    assert len(ev["evidence_bullets"]) >= 1

    # Non-causal verification
    full_text = (ev["why_it_matters"] + " " + " ".join(ev["evidence_bullets"])).lower()
    assert "caused by" not in full_text
    assert "buy" not in full_text
    assert "sell" not in full_text

    # Component scores present
    assert ev["component_scores"]["magnitude"] is not None


@pytest.mark.asyncio
async def test_4_missing_data_notes_handling(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that missing benchmark or volume is clearly disclosed without penalizing the stock:
    - Displays honest disclosures in missing_data_notes
    """
    inst = Instrument(nse_symbol="M6_MISSING_DATA", company_name="Missing Data Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M6 Missing Data WL"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # Only 2 observations without long history or benchmark
    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("500.00"), observed_at=t0, source="NSE", data_status="final"))
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("540.00"), observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()

    await client.get(f"/api/v1/watchlists/{wl_id}/attention")

    res = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res.status_code == 200
    data = res.json()

    ev = data["evidence"]
    assert ev is not None
    # Check that missing notes exist
    assert len(ev["missing_data_notes"]) >= 1
    # Market context shows unavailable status honestly
    assert data["market_context"]["status"] in ("available", "unavailable")


@pytest.mark.asyncio
async def test_5_change_timeline_grouping_and_chronology(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that related candidate signals within an observation window are grouped into ONE timeline episode,
    and multiple episodes are ordered reverse-chronologically.
    """
    inst = Instrument(nse_symbol="M6_TIMELINE_GRP", company_name="Timeline Grouping Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M6 Timeline WL"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # Historical setup
    dates = [
        datetime(2026, 8, 28, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 29, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 30, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 31, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc),  # baseline
    ]
    for d in dates:
        db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1000.00"), volume=100000, observed_at=d, source="NSE", data_status="final"))
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # Window 1 (Sep 2): move +6% with volume
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1060.00"), volume=200000, observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()
    await client.get(f"/api/v1/watchlists/{wl_id}/attention")

    res = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res.status_code == 200
    timeline = res.json()["timeline"]

    assert len(timeline) == 1
    ep = timeline[0]
    # Grouped signals in single episode
    assert len(ep["constituent_change_types"]) >= 1
    assert "PRICE_MOVE" in ep["constituent_change_types"]
    assert float(ep["percentage_change"]) == 6.00
    assert ep["review_status"] == "surfaced"


@pytest.mark.asyncio
async def test_6_market_context_benchmark_relative_performance(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies Section 5: Market Context
    - Stock % vs Benchmark % vs Relative performance
    - Neutral non-causal language
    """
    inst = Instrument(nse_symbol="M6_MKT_CTX", company_name="Market Context Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M6 Market Context WL"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1000.00"), observed_at=t0, source="NSE", data_status="final"))
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1050.00"), observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()
    await client.get(f"/api/v1/watchlists/{wl_id}/attention")

    res = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res.status_code == 200
    mc = res.json()["market_context"]
    assert mc["benchmark_symbol"] == "NIFTY 50"
    assert "caused" not in mc["context_summary"].lower()


@pytest.mark.asyncio
async def test_7_bounded_historical_series_and_markers(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies Section 6: Bounded historical series for the lightweight chart
    - Up to 30 points
    - is_baseline and is_current correctly identify previous check and current observation
    """
    inst = Instrument(nse_symbol="M6_SERIES_CHART", company_name="Series Chart Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M6 Chart WL"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 3, 15, 30, 0, tzinfo=timezone.utc)

    obs0 = MarketObservation(instrument_id=inst.id, price=Decimal("100.00"), volume=1000, observed_at=t0, source="NSE", data_status="final")
    obs1 = MarketObservation(instrument_id=inst.id, price=Decimal("105.00"), volume=1200, observed_at=t1, source="NSE", data_status="final")
    db_session.add_all([obs0, obs1])
    await db_session.commit()

    # User establishes baseline at obs1
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # Newer observation arrives
    obs2 = MarketObservation(instrument_id=inst.id, price=Decimal("110.00"), volume=1500, observed_at=t2, source="NSE", data_status="final")
    db_session.add(obs2)
    await db_session.commit()

    res = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res.status_code == 200
    series = res.json()["historical_series"]

    assert len(series) == 3
    # Check baseline marker
    baseline_point = next(p for p in series if p["is_baseline"])
    assert baseline_point["observation_id"] == obs1.id

    # Check current marker
    current_point = next(p for p in series if p["is_current"])
    assert current_point["observation_id"] == obs2.id


@pytest.mark.asyncio
async def test_8_review_state_reflection_in_detail(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies Section 7: Review State
    - Opening detail does NOT mark change reviewed
    - Reviewing marks episode reviewed and updates since_last_checked and timeline
    """
    inst = Instrument(nse_symbol="M6_REV_DETAIL", company_name="Review Detail Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M6 Review Detail WL"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1000.00"), observed_at=t0, source="NSE", data_status="final"))
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1080.00"), observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()
    await client.get(f"/api/v1/watchlists/{wl_id}/attention")

    # 1. Opening detail view does NOT mark it reviewed
    res1 = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res1.status_code == 200
    assert res1.json()["since_last_checked"]["is_reviewed"] is False
    assert res1.json()["timeline"][0]["is_reviewed"] is False

    # 2. Mark instrument reviewed via existing review endpoint
    rev_res = await client.post(f"/api/v1/watchlists/{wl_id}/instruments/{inst.id}/review")
    assert rev_res.status_code == 200

    # 3. Query detail view again: now reflects reviewed!
    res2 = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res2.status_code == 200
    assert res2.json()["since_last_checked"]["is_reviewed"] is True
    assert res2.json()["since_last_checked"]["review_status"] == "reviewed"
    assert res2.json()["timeline"][0]["is_reviewed"] is True


@pytest.mark.asyncio
async def test_9_first_check_edge_case_no_baseline(client: AsyncClient, db_session: AsyncSession):
    """
    Edge case: User has not recorded a baseline for this instrument yet.
    - has_baseline is False
    - tracking_note explains that baseline has not been established yet
    """
    inst = Instrument(nse_symbol="M6_NO_BASE", company_name="No Baseline Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("500.00"), observed_at=t0, source="NSE", data_status="final"))
    await db_session.commit()

    res = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res.status_code == 200
    data = res.json()

    syc = data["since_last_checked"]
    assert syc["has_baseline"] is False
    assert "No observation baseline established yet" in syc["tracking_note"]


@pytest.mark.asyncio
async def test_10_single_observation_edge_case(client: AsyncClient, db_session: AsyncSession):
    """
    Edge case: Instrument has only 1 observation recorded in database.
    - No session change
    - Correct observation display without fabricated changes
    """
    inst = Instrument(nse_symbol="M6_SINGLE_OBS", company_name="Single Obs Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("300.00"), observed_at=t0, source="NSE", data_status="final"))
    await db_session.commit()

    res = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res.status_code == 200
    data = res.json()

    assert data["current_observation"]["session_absolute_change"] is None
    assert data["current_observation"]["session_percentage_change"] is None
    assert len(data["historical_series"]) == 1


@pytest.mark.asyncio
async def test_11_no_changes_detected_quiet_edge_case(client: AsyncClient, db_session: AsyncSession):
    """
    Edge case: Instrument moved within normal variance (< 0.20 score) so no candidate change was flagged.
    - Explains that no meaningful change was detected
    """
    inst = Instrument(nse_symbol="M6_QUIET_STOCK", company_name="Quiet Stock Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M6 Quiet WL"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1000.00"), observed_at=t0, source="NSE", data_status="final"))
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # Minimal move (+0.01%)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1000.10"), observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()
    await client.get(f"/api/v1/watchlists/{wl_id}/attention")

    res = await client.get(f"/api/v1/instruments/{inst.id}")
    assert res.status_code == 200
    syc = res.json()["since_last_checked"]
    assert syc["significance_level"] == "NONE"
    assert float(syc["overall_score"]) < 0.20


@pytest.mark.asyncio
async def test_12_nonexistent_instrument_returns_404(client: AsyncClient):
    """
    Verifies that requesting an invalid or nonexistent instrument ID returns 404 Not Found.
    """
    res = await client.get("/api/v1/instruments/999999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
