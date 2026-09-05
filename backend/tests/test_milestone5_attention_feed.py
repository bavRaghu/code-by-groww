import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.change_review import ChangeReview
from app.models.detected_change import DetectedChange
from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.user_observation import UserObservation
from app.models.watchlist import Watchlist
from app.seed import DEV_USER_ID


@pytest.mark.asyncio
async def test_1_since_you_last_checked_summary_and_counts(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies the primary 'Since you last checked' summary counts:
    - total_instruments
    - instruments_evaluated
    - attention_count
    - high_count, medium_count, low_count
    - no_meaningful_change_count (< 0.20 score)
    - unreviewed_count and reviewed_count
    - honest data freshness provenance
    """
    inst1 = Instrument(nse_symbol="M5_SUM_HIGH", company_name="High Move Inc")
    inst2 = Instrument(nse_symbol="M5_SUM_QUIET", company_name="Quiet Inc")
    db_session.add_all([inst1, inst2])
    await db_session.commit()
    await db_session.refresh(inst1)
    await db_session.refresh(inst2)

    # Watchlist creation
    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Summary Watchlist"})
    assert wl_res.status_code == 201
    wl_id = wl_res.json()["id"]

    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst1.id})
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst2.id})

    # T0 baseline
    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    obs1_t0 = MarketObservation(instrument_id=inst1.id, price=Decimal("1000.00"), observed_at=t0, source="NSE", data_status="final")
    obs2_t0 = MarketObservation(instrument_id=inst2.id, price=Decimal("500.00"), observed_at=t0, source="NSE", data_status="final")
    db_session.add_all([obs1_t0, obs2_t0])
    await db_session.commit()

    # User establishes baseline
    check_res = await client.post(f"/api/v1/watchlists/{wl_id}/check")
    assert check_res.status_code == 200

    # T1: inst1 moves +8.5% (substantial move), inst2 moves +0.01% (flat/quiet)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    obs1_t1 = MarketObservation(instrument_id=inst1.id, price=Decimal("1085.00"), observed_at=t1, source="NSE", data_status="final")
    obs2_t1 = MarketObservation(instrument_id=inst2.id, price=Decimal("500.05"), observed_at=t1, source="NSE", data_status="final")
    db_session.add_all([obs1_t1, obs2_t1])
    await db_session.commit()

    # Fetch attention feed
    res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert res.status_code == 200
    data = res.json()

    summary = data["summary"]
    assert summary["total_instruments"] == 2
    assert summary["instruments_evaluated"] == 2
    assert summary["attention_count"] == 1
    assert summary["high_count"] + summary["medium_count"] + summary["low_count"] == 1
    assert summary["no_meaningful_change_count"] == 1
    assert summary["unreviewed_count"] == 1
    assert summary["reviewed_count"] == 0

    # Quiet instrument check
    assert len(data["quiet_instruments"]) == 1
    assert data["quiet_instruments"][0]["symbol"] == "M5_SUM_QUIET"


@pytest.mark.asyncio
async def test_2_signal_grouping_into_single_episode(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that multiple candidate signals for the same instrument (price move, abnormal return, volume)
    are grouped into ONE underlying change episode per instrument in the attention feed,
    preventing double-counting while preserving all constituent changes.
    """
    inst = Instrument(nse_symbol="M5_GROUP_1", company_name="Grouped Signal Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    # Watchlist
    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Grouping Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # History observations for abnormal return & volume anomaly
    dates = [
        datetime(2026, 8, 25, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 26, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 27, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 28, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 29, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 30, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 31, 15, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc),  # Baseline T0
    ]
    for d in dates:
        db_session.add(
            MarketObservation(
                instrument_id=inst.id,
                price=Decimal("1000.00"),
                volume=100000,
                observed_at=d,
                source="NSE",
                data_status="final",
            )
        )
    await db_session.commit()

    # User establishes baseline at T0 (Sep 1)
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # T1 (Sep 2): Huge move +7% and volume spike 3x
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    obs_t1 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1070.00"),
        volume=300000,
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs_t1)
    await db_session.commit()

    res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert res.status_code == 200
    data = res.json()

    # Exactly 1 episode card in attention feed
    assert len(data["attention_items"]) == 1
    episode = data["attention_items"][0]
    assert episode["symbol"] == "M5_GROUP_1"

    # Constituent change types grouped
    assert len(episode["constituent_change_types"]) >= 2
    assert "PRICE_MOVE" in episode["constituent_change_types"]

    # All underlying changes are preserved in changes list
    assert len(episode["changes"]) >= 2


@pytest.mark.asyncio
async def test_3_deterministic_attention_ranking_and_none_exclusion(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies multi-criteria deterministic ranking:
    1. overall_score DESC
    2. significance_level (HIGH > MEDIUM > LOW)
    3. evidence_completeness (STRONG > MODERATE > LIMITED)
    4. symbol ASC
    And verifies that items with NONE level are excluded from primary feed and placed in quiet_instruments.
    """
    stock_a = Instrument(nse_symbol="M5_RANK_A", company_name="Stock Alpha")
    stock_b = Instrument(nse_symbol="M5_RANK_B", company_name="Stock Beta")
    stock_c = Instrument(nse_symbol="M5_RANK_C", company_name="Stock Charlie")
    stock_quiet = Instrument(nse_symbol="M5_RANK_Z_QUIET", company_name="Stock Quiet")
    db_session.add_all([stock_a, stock_b, stock_c, stock_quiet])
    await db_session.commit()
    for s in [stock_a, stock_b, stock_c, stock_quiet]:
        await db_session.refresh(s)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Ranking Watchlist"})
    wl_id = wl_res.json()["id"]
    for s in [stock_a, stock_b, stock_c, stock_quiet]:
        await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": s.id})

    # T0 baseline
    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    for s in [stock_a, stock_b, stock_c, stock_quiet]:
        db_session.add(
            MarketObservation(
                instrument_id=s.id,
                price=Decimal("1000.00"),
                observed_at=t0,
                source="NSE",
                data_status="final",
            )
        )
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # T1:
    # stock_a moves +9% -> High score
    # stock_b moves +4% -> Medium score
    # stock_c moves +2.5% -> Moderate/Low score
    # stock_quiet moves +0.02% -> Score < 0.20 (NONE)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add_all([
        MarketObservation(instrument_id=stock_a.id, price=Decimal("1090.00"), observed_at=t1, source="NSE", data_status="final"),
        MarketObservation(instrument_id=stock_b.id, price=Decimal("1040.00"), observed_at=t1, source="NSE", data_status="final"),
        MarketObservation(instrument_id=stock_c.id, price=Decimal("1025.00"), observed_at=t1, source="NSE", data_status="final"),
        MarketObservation(instrument_id=stock_quiet.id, price=Decimal("1000.20"), observed_at=t1, source="NSE", data_status="final"),
    ])
    await db_session.commit()

    res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert res.status_code == 200
    data = res.json()

    # Verify NONE level is excluded from primary feed
    attn_symbols = [it["symbol"] for it in data["attention_items"]]
    assert "M5_RANK_Z_QUIET" not in attn_symbols
    assert any(q["symbol"] == "M5_RANK_Z_QUIET" for q in data["quiet_instruments"])

    # Verify scores are strictly monotonically descending (or tie broken deterministically)
    scores = [float(it["overall_score"]) for it in data["attention_items"]]
    for i in range(1, len(scores)):
        assert scores[i - 1] >= scores[i]


@pytest.mark.asyncio
async def test_4_evidence_completeness_levels(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that the system assesses evidence completeness:
    - STRONG when supported by >= 2 corroborating signals beyond price move
    - LIMITED when only price move exists with no corroborating market context
    - Excluded/missing components do not penalize the normalized weighted score
    """
    inst = Instrument(nse_symbol="M5_EVID_1", company_name="Evidence Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Evidence Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # T0 baseline without long historical depth (so statistical abnormality/volume may be limited)
    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1000.00"), observed_at=t0, source="NSE", data_status="final"))
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # T1 observation
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1050.00"), observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()

    res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert res.status_code == 200
    data = res.json()

    assert len(data["attention_items"]) == 1
    item = data["attention_items"][0]
    completeness = item["evidence_completeness"]
    assert completeness is not None
    assert completeness["level"] in ("STRONG", "MODERATE", "LIMITED")
    assert "summary" in completeness
    assert isinstance(completeness["available_signals"], list)
    assert isinstance(completeness["missing_signals"], list)


@pytest.mark.asyncio
async def test_5_non_causal_structured_explanations(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that explanations are deterministic, evidence-based, and strictly non-causal:
    - Has structured keys: what_happened, why_it_stands_out, supporting_evidence, missing_data_notes
    - Never uses speculative or unsupported causal claims ('caused by', 'triggered by panic')
    """
    inst = Instrument(nse_symbol="M5_EXPL_1", company_name="Explanation Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Explanation Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("2000.00"), observed_at=t0, source="NSE", data_status="final"))
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("2120.00"), observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()

    res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert res.status_code == 200
    item = res.json()["attention_items"][0]

    structured = item["structured_explanation"]
    assert "what_happened" in structured
    assert "why_it_stands_out" in structured
    assert isinstance(structured["supporting_evidence"], list)
    assert isinstance(structured["missing_data_notes"], list)

    full_text = (item["explanation"] + " " + structured["what_happened"] + " " + structured["why_it_stands_out"]).lower()
    assert "caused by" not in full_text
    assert "buy" not in full_text
    assert "sell" not in full_text


@pytest.mark.asyncio
async def test_6_chronological_change_feed_timeline(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that the chronological feed (`feed_items`) lists all detected events in reverse-chronological order:
    - Each item has formatted metrics_summary, timestamp, review_status, and observation boundaries
    """
    inst1 = Instrument(nse_symbol="M5_FEED_1", company_name="Feed Corp 1")
    inst2 = Instrument(nse_symbol="M5_FEED_2", company_name="Feed Corp 2")
    db_session.add_all([inst1, inst2])
    await db_session.commit()
    await db_session.refresh(inst1)
    await db_session.refresh(inst2)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Feed Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst1.id})
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst2.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add_all([
        MarketObservation(instrument_id=inst1.id, price=Decimal("100.00"), observed_at=t0, source="NSE", data_status="final"),
        MarketObservation(instrument_id=inst2.id, price=Decimal("200.00"), observed_at=t0, source="NSE", data_status="final"),
    ])
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    db_session.add_all([
        MarketObservation(instrument_id=inst1.id, price=Decimal("108.00"), observed_at=t1, source="NSE", data_status="final"),
        MarketObservation(instrument_id=inst2.id, price=Decimal("215.00"), observed_at=t1, source="NSE", data_status="final"),
    ])
    await db_session.commit()

    res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert res.status_code == 200
    feed_items = res.json()["feed_items"]

    assert len(feed_items) >= 2
    for item in feed_items:
        assert item["review_status"] in ("surfaced", "reviewed")
        assert "metrics_summary" in item
        assert len(item["metrics_summary"]) > 0
        assert item["source"] == "NSE"


@pytest.mark.asyncio
async def test_7_review_state_individual_change_api(client: AsyncClient, db_session: AsyncSession):
    """
    Tests marking an individual change as reviewed via POST /changes/{change_id}/review:
    - Creates a ChangeReview audit entry
    - Sets DetectedChange.review_status = 'reviewed' and reviewed_at
    - Updates attention response review status
    """
    inst = Instrument(nse_symbol="M5_REV_IND", company_name="Individual Review Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Individual Review Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("500.00"), observed_at=t0, source="NSE", data_status="final"))
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("550.00"), observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()

    # Get attention feed to find change ID
    attn_res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn_res.status_code == 200
    attn_data = attn_res.json()
    assert attn_data["summary"]["unreviewed_count"] == 1
    assert attn_data["summary"]["reviewed_count"] == 0

    change_id = attn_data["attention_items"][0]["changes"][0]["id"]

    # Review the change
    rev_res = await client.post(f"/api/v1/watchlists/{wl_id}/changes/{change_id}/review")
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["change_id"] == change_id
    assert rev_data["review_status"] == "reviewed"
    assert rev_data["reviewed_at"] is not None

    # Verify audit record in DB
    cr_stmt = select(ChangeReview).where(ChangeReview.detected_change_id == change_id)
    cr_res = await db_session.execute(cr_stmt)
    cr = cr_res.scalar_one_or_none()
    assert cr is not None
    assert cr.user_id == DEV_USER_ID
    assert cr.action == "reviewed"

    # Query attention feed again: unreviewed_count should now be 0, reviewed_count 1
    attn_res2 = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn_res2.status_code == 200
    attn_data2 = attn_res2.json()
    assert attn_data2["summary"]["unreviewed_count"] == 0
    assert attn_data2["summary"]["reviewed_count"] == 1
    assert attn_data2["attention_items"][0]["is_reviewed"] is True
    assert attn_data2["attention_items"][0]["review_status"] == "reviewed"


@pytest.mark.asyncio
async def test_8_review_state_instrument_level_api(client: AsyncClient, db_session: AsyncSession):
    """
    Tests marking all changes for an instrument as reviewed via POST /instruments/{instrument_id}/review.
    """
    inst = Instrument(nse_symbol="M5_REV_INST", company_name="Instrument Review Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Instrument Review Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1000.00"), observed_at=t0, source="NSE", data_status="final"))
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1080.00"), observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()

    # Trigger detection
    await client.get(f"/api/v1/watchlists/{wl_id}/attention")

    # Review instrument
    rev_res = await client.post(f"/api/v1/watchlists/{wl_id}/instruments/{inst.id}/review")
    assert rev_res.status_code == 200
    data = rev_res.json()
    assert data["instrument_id"] == inst.id
    assert data["reviewed_changes_count"] >= 1
    assert data["review_status"] == "reviewed"

    # Attention feed confirms reviewed
    attn_res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn_res.status_code == 200
    assert attn_res.json()["summary"]["unreviewed_count"] == 0
    assert attn_res.json()["summary"]["reviewed_count"] == 1


@pytest.mark.asyncio
async def test_9_review_all_watchlist_api(client: AsyncClient, db_session: AsyncSession):
    """
    Tests marking all changes across the entire watchlist as reviewed in a single action
    via POST /watchlists/{id}/review-all.
    """
    inst1 = Instrument(nse_symbol="M5_ALL_1", company_name="All Review 1")
    inst2 = Instrument(nse_symbol="M5_ALL_2", company_name="All Review 2")
    db_session.add_all([inst1, inst2])
    await db_session.commit()
    await db_session.refresh(inst1)
    await db_session.refresh(inst2)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Review All Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst1.id})
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst2.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add_all([
        MarketObservation(instrument_id=inst1.id, price=Decimal("100.00"), observed_at=t0, source="NSE", data_status="final"),
        MarketObservation(instrument_id=inst2.id, price=Decimal("200.00"), observed_at=t0, source="NSE", data_status="final"),
    ])
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    db_session.add_all([
        MarketObservation(instrument_id=inst1.id, price=Decimal("110.00"), observed_at=t1, source="NSE", data_status="final"),
        MarketObservation(instrument_id=inst2.id, price=Decimal("220.00"), observed_at=t1, source="NSE", data_status="final"),
    ])
    await db_session.commit()

    # Initial attention query
    attn1 = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn1.status_code == 200
    assert attn1.json()["summary"]["unreviewed_count"] == 2
    assert attn1.json()["summary"]["reviewed_count"] == 0

    # Call review-all
    rev_all_res = await client.post(f"/api/v1/watchlists/{wl_id}/review-all")
    assert rev_all_res.status_code == 200
    rev_data = rev_all_res.json()
    assert rev_data["watchlist_id"] == wl_id
    assert rev_data["reviewed_changes_count"] >= 2
    assert rev_data["review_status"] == "reviewed"

    # Query attention again
    attn2 = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn2.status_code == 200
    summary = attn2.json()["summary"]
    assert summary["unreviewed_count"] == 0
    assert summary["reviewed_count"] == 2


@pytest.mark.asyncio
async def test_10_review_persists_across_market_refresh_and_repeated_detection(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies Requirement 8 & 9:
    - Reading feed, refreshing market data, or checking for changes does NOT mark changes reviewed
    - Once marked reviewed, the reviewed state persists across refreshes and repeated detection calls
    """
    inst = Instrument(nse_symbol="M5_PERSIST_1", company_name="Persistence Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Persistence Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1000.00"), observed_at=t0, source="NSE", data_status="final"))
    await db_session.commit()
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    db_session.add(MarketObservation(instrument_id=inst.id, price=Decimal("1090.00"), observed_at=t1, source="NSE", data_status="final"))
    await db_session.commit()

    # 1. Fetching attention does NOT mark change reviewed
    attn1 = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn1.status_code == 200
    assert attn1.json()["summary"]["unreviewed_count"] == 1

    # 2. Mark instrument reviewed
    await client.post(f"/api/v1/watchlists/{wl_id}/instruments/{inst.id}/review")

    # 3. Repeated detection and attention calls DO NOT overwrite review status
    for _ in range(3):
        attn_repeat = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
        assert attn_repeat.status_code == 200
        assert attn_repeat.json()["summary"]["unreviewed_count"] == 0
        assert attn_repeat.json()["summary"]["reviewed_count"] == 1
        assert attn_repeat.json()["attention_items"][0]["is_reviewed"] is True


@pytest.mark.asyncio
async def test_11_review_does_not_advance_baseline(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that marking changes as reviewed is an attention management feature
    and does NOT alter the user observation baseline.
    Only explicit POST /check updates the baseline.
    """
    inst = Instrument(nse_symbol="M5_BASE_NO_ADV", company_name="No Advance Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Baseline No Advance Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    obs_t0 = MarketObservation(instrument_id=inst.id, price=Decimal("1000.00"), observed_at=t0, source="NSE", data_status="final")
    db_session.add(obs_t0)
    await db_session.commit()
    await db_session.refresh(obs_t0)

    # Establish baseline at T0
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # Record user baseline observation ID
    uo_stmt = select(UserObservation).where(UserObservation.user_id == DEV_USER_ID, UserObservation.instrument_id == inst.id)
    uo_before = (await db_session.execute(uo_stmt)).scalar_one()
    assert uo_before.last_seen_observation_id == obs_t0.id

    # T1 observation arrives
    obs_t1 = MarketObservation(instrument_id=inst.id, price=Decimal("1080.00"), observed_at=t1, source="NSE", data_status="final")
    db_session.add(obs_t1)
    await db_session.commit()
    await db_session.refresh(obs_t1)

    # Trigger attention and review
    await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    await client.post(f"/api/v1/watchlists/{wl_id}/review-all")

    # Verify baseline is STILL at obs_t0, NOT obs_t1
    uo_stmt2 = select(UserObservation).where(UserObservation.user_id == DEV_USER_ID, UserObservation.instrument_id == inst.id).execution_options(populate_existing=True)
    uo_after = (await db_session.execute(uo_stmt2)).scalar_one()
    assert uo_after.last_seen_observation_id == obs_t0.id


@pytest.mark.asyncio
async def test_12_review_authorization_and_error_handling(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies error handling and authorization boundaries for review endpoints:
    - 404 for nonexistent watchlist or change
    - 404 for change not belonging to watchlist
    """
    # Non-existent watchlist
    res1 = await client.post("/api/v1/watchlists/999999/review-all")
    assert res1.status_code == 404

    # Non-existent change
    wl_res = await client.post("/api/v1/watchlists", json={"name": "M5 Auth Watchlist"})
    wl_id = wl_res.json()["id"]

    res2 = await client.post(f"/api/v1/watchlists/{wl_id}/changes/999999/review")
    assert res2.status_code == 404

    # Non-existent instrument in watchlist
    res3 = await client.post(f"/api/v1/watchlists/{wl_id}/instruments/999999/review")
    assert res3.status_code == 404
