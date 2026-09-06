import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.user_observation import UserObservation
from app.models.detected_change import DetectedChange
from app.models.watchlist import Watchlist, WatchlistItem
from app.ingestion.service import IngestionService, sync_provider_instruments, import_instruments
from app.providers.base import NormalizedObservation
from app.providers.nse import NSEHistoricalProvider
from app.services.market_refresh import refresh_watchlist_market
from app.seed import DEV_USER_ID


@pytest.mark.asyncio
async def test_1_real_instrument_discovery_beyond_seed(client: AsyncClient):
    """
    1. Real instrument discovery beyond the 4 seed instruments.
    Verifies that security master data makes stocks like TATAMOTORS, BHARTIARTL, ITC
    discoverable via search, while non-equity (GB series) bonds are filtered out.
    """
    # Search for TATAMOTORS
    res_tata = await client.get("/api/v1/instruments?search=TATAMOTORS")
    assert res_tata.status_code == 200
    items_tata = res_tata.json()
    assert len(items_tata) >= 1
    tata = next((it for it in items_tata if it["nse_symbol"] == "TATAMOTORS"), None)
    assert tata is not None
    assert tata["isin"] == "INE155A01022"
    assert "Tata Motors" in tata["company_name"]

    # Search for BHARTIARTL
    res_bharti = await client.get("/api/v1/instruments?search=BHARTIARTL")
    assert res_bharti.status_code == 200
    items_bharti = res_bharti.json()
    bharti = next((it for it in items_bharti if it["nse_symbol"] == "BHARTIARTL"), None)
    assert bharti is not None
    assert bharti["isin"] == "INE397D01024"

    # Search for ITC
    res_itc = await client.get("/api/v1/instruments?search=ITC")
    assert res_itc.status_code == 200
    items_itc = res_itc.json()
    assert any(it["nse_symbol"] == "ITC" for it in items_itc)

    # Verify non-equity bond GS2026 is filtered out and NOT in instruments
    res_bond = await client.get("/api/v1/instruments?search=GS2026")
    assert res_bond.status_code == 200
    assert len(res_bond.json()) == 0


@pytest.mark.asyncio
async def test_2_idempotent_security_master_discovery_imports(db_session: AsyncSession):
    """
    2. Idempotent security-master / discovery imports.
    Importing instruments repeatedly should not create duplicates or fail.
    """
    counts_first = await sync_provider_instruments(db_session)
    counts_second = await sync_provider_instruments(db_session)

    # Second sync should create 0 new instruments
    assert counts_second["instruments_created"] == 0

    # Ensure uniqueness of nse_symbol
    stmt = (
        select(Instrument.nse_symbol, func.count(Instrument.id))
        .group_by(Instrument.nse_symbol)
        .having(func.count(Instrument.id) > 1)
    )
    res = await db_session.execute(stmt)
    duplicates = res.all()
    assert len(duplicates) == 0, f"Found duplicate instruments: {duplicates}"


@pytest.mark.asyncio
async def test_3_newer_market_observation_updates_watchlist_snapshot(client: AsyncClient, db_session: AsyncSession):
    """
    3. Ingestion of newer market observations updates watchlist current snapshot.
    """
    s_sym = f"SNAP_{uuid.uuid4().hex[:6]}"
    inst = Instrument(nse_symbol=s_sym, company_name="Snapshot Test Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    # Create watchlist
    wl_res = await client.post("/api/v1/watchlists", json={"name": "Snapshot Watchlist"})
    assert wl_res.status_code == 201
    wl_id = wl_res.json()["id"]

    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # Initial market view: no observation
    mkt_res = await client.get(f"/api/v1/watchlists/{wl_id}/market")
    assert mkt_res.status_code == 200
    items = mkt_res.json()["items"]
    assert len(items) == 1
    assert items[0]["latest_price"] is None

    # Ingest observation 1
    t1 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    obs1 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("100.00"),
        volume=1000,
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs1)
    await db_session.commit()

    # Verify snapshot reflects observation 1
    mkt_res1 = await client.get(f"/api/v1/watchlists/{wl_id}/market")
    assert float(mkt_res1.json()["items"][0]["latest_price"]) == 100.00

    # Ingest newer observation 2
    t2 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    obs2 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("115.00"),
        volume=1500,
        observed_at=t2,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs2)
    await db_session.commit()

    # Verify snapshot now reflects observation 2
    mkt_res2 = await client.get(f"/api/v1/watchlists/{wl_id}/market")
    item2 = mkt_res2.json()["items"][0]
    assert float(item2["latest_price"]) == 115.00
    assert float(item2["absolute_change"]) == 15.00
    assert float(item2["percentage_change"]) == 15.00


@pytest.mark.asyncio
async def test_4_older_observation_does_not_overwrite_newer_snapshot(client: AsyncClient, db_session: AsyncSession):
    """
    4. Out-of-order / older observations do not overwrite newer observation snapshot.
    Snapshot is determined strictly by observed_at DESC, not ingestion order.
    """
    s_sym = f"ORDER_{uuid.uuid4().hex[:6]}"
    inst = Instrument(nse_symbol=s_sym, company_name="Order Test Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "Order Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # Ingest Newer Observation (Day 2) FIRST
    t2 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    obs_newer = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("500.00"),
        volume=2000,
        observed_at=t2,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs_newer)
    await db_session.commit()

    # Now Ingest Older Observation (Day 1) SECOND
    t1 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    obs_older = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("450.00"),
        volume=1800,
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs_older)
    await db_session.commit()

    # Snapshot must still show Day 2 (500.00), NOT 450.00
    mkt_res = await client.get(f"/api/v1/watchlists/{wl_id}/market")
    assert float(mkt_res.json()["items"][0]["latest_price"]) == 500.00


@pytest.mark.asyncio
async def test_5_duplicate_observation_ingestion_is_idempotent(db_session: AsyncSession):
    """
    5. Duplicate observation ingestion does not corrupt state.
    """
    s_sym = f"DUP_{uuid.uuid4().hex[:6]}"
    inst = Instrument(nse_symbol=s_sym, company_name="Duplicate Obs Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    t_obs = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    norm = NormalizedObservation(
        symbol=s_sym,
        price=Decimal("250.00"),
        open=None,
        high=None,
        low=None,
        close=None,
        volume=5000,
        observed_at=t_obs,
        source="NSE",
        data_status="final",
    )

    ingest_svc = IngestionService()
    res1 = await ingest_svc.ingest_observations(db_session, [norm])
    assert res1.persisted_observations == 1

    # Ingest same observation again
    res2 = await ingest_svc.ingest_observations(db_session, [norm])
    assert res2.persisted_observations == 1

    # Ensure exactly 1 row in DB (idempotent, no duplicates created)
    cnt_stmt = select(func.count(MarketObservation.id)).where(MarketObservation.instrument_id == inst.id)
    cnt = (await db_session.execute(cnt_stmt)).scalar()
    assert cnt == 1


@pytest.mark.asyncio
async def test_6_refreshing_market_data_does_not_advance_user_baseline(client: AsyncClient, db_session: AsyncSession):
    """
    6. Refreshing market data does not advance user last-checked state.
    Strict separation:
    - Refreshing market data ingests newer market state.
    - UserObservation baseline remains anchored until explicit user check.
    """
    s_sym = f"BASE_{uuid.uuid4().hex[:6]}"
    inst = Instrument(nse_symbol=s_sym, company_name="Baseline Test Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "Baseline Separation Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # Ingest Day 1 observation
    t1 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    obs1 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1000.00"),
        volume=1000,
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs1)
    await db_session.commit()
    await db_session.refresh(obs1)

    # User checks watchlist -> baseline set to Day 1 obs
    chk_res = await client.post(f"/api/v1/watchlists/{wl_id}/check")
    assert chk_res.status_code == 200

    uo_stmt = select(UserObservation).where(
        UserObservation.user_id == DEV_USER_ID,
        UserObservation.instrument_id == inst.id,
    )
    uo = (await db_session.execute(uo_stmt)).scalar_one()
    assert uo.last_seen_observation_id == obs1.id

    # Ingest Day 2 observation (newer market data)
    t2 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    obs2 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1080.00"),
        volume=1200,
        observed_at=t2,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs2)
    await db_session.commit()
    await db_session.refresh(obs2)

    # Re-query UserObservation using fresh select
    uo_after_stmt = select(UserObservation.last_seen_observation_id).where(
        UserObservation.user_id == DEV_USER_ID,
        UserObservation.instrument_id == inst.id,
    ).execution_options(populate_existing=True)
    after_last_seen_id = (await db_session.execute(uo_after_stmt)).scalar_one()

    # CRITICAL: Baseline has NOT advanced. It is still obs1.id
    assert after_last_seen_id == obs1.id
    assert after_last_seen_id != obs2.id


@pytest.mark.asyncio
async def test_7_candidate_change_detection_uses_newly_refreshed_observations(client: AsyncClient, db_session: AsyncSession):
    """
    7. Candidate change detection uses newly refreshed observations.
    """
    s_sym = f"CHG_{uuid.uuid4().hex[:6]}"
    inst = Instrument(nse_symbol=s_sym, company_name="Change Detection Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "Change Detection Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # Day 1
    t1 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    obs1 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("2000.00"),
        volume=10000,
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs1)
    await db_session.commit()

    # User establishes baseline
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # Day 2
    t2 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    obs2 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("2100.00"),
        volume=15000,
        observed_at=t2,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs2)
    await db_session.commit()

    # Query changes
    chg_res = await client.get(f"/api/v1/watchlists/{wl_id}/changes")
    assert chg_res.status_code == 200
    data = chg_res.json()
    assert data["summary"]["instruments_with_changes"] == 1

    pm = next((c for c in data["changes"] if c["instrument_id"] == inst.id and c["change_type"] == "PRICE_MOVE"), None)
    assert pm is not None
    assert float(pm["baseline_price"]) == 2000.00
    assert float(pm["current_price"]) == 2100.00
    assert float(pm["absolute_change"]) == 100.00
    assert float(pm["percentage_change"]) == 5.00


@pytest.mark.asyncio
async def test_8_no_newer_observation_produces_no_false_change(client: AsyncClient, db_session: AsyncSession):
    """
    8. No newer observation => no new false change detected.
    """
    s_sym = f"NO_CHG_{uuid.uuid4().hex[:6]}"
    inst = Instrument(nse_symbol=s_sym, company_name="No False Change Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "No False Change Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # Day 1
    t1 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    obs1 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("500.00"),
        volume=5000,
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs1)
    await db_session.commit()

    # User checks at Day 1
    await client.post(f"/api/v1/watchlists/{wl_id}/check")

    # Without any new observation, check for changes
    chg_res = await client.get(f"/api/v1/watchlists/{wl_id}/changes")
    assert chg_res.status_code == 200
    data = chg_res.json()
    assert data["summary"]["instruments_with_changes"] == 0
    assert len(data["changes"]) == 0


@pytest.mark.asyncio
async def test_9_repeated_change_detection_is_idempotent(client: AsyncClient, db_session: AsyncSession):
    """
    9. Repeated change detection without new data is idempotent.
    """
    s_sym = f"IDEM_{uuid.uuid4().hex[:6]}"
    inst = Instrument(nse_symbol=s_sym, company_name="Idempotent Detect Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "Idempotent Detect Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t1 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    obs1 = MarketObservation(instrument_id=inst.id, price=Decimal("100.00"), volume=1000, observed_at=t1, source="NSE", data_status="final")
    t2 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    obs2 = MarketObservation(instrument_id=inst.id, price=Decimal("120.00"), volume=2000, observed_at=t2, source="NSE", data_status="final")
    db_session.add_all([obs1, obs2])
    await db_session.commit()

    # Check baseline at obs1
    uo = UserObservation(user_id=DEV_USER_ID, instrument_id=inst.id, last_seen_observation_id=obs1.id, last_seen_at=t1)
    db_session.add(uo)
    await db_session.commit()

    # Run change detection call 1
    res1 = await client.get(f"/api/v1/watchlists/{wl_id}/changes")
    count1 = len(res1.json()["changes"])

    # Run change detection call 2
    res2 = await client.get(f"/api/v1/watchlists/{wl_id}/changes")
    count2 = len(res2.json()["changes"])

    assert count1 == count2
    assert count1 > 0

    # Ensure no duplicate rows in detected_changes table
    cnt_stmt = select(func.count(DetectedChange.id)).where(
        DetectedChange.user_id == DEV_USER_ID,
        DetectedChange.instrument_id == inst.id,
    )
    db_cnt = (await db_session.execute(cnt_stmt)).scalar()
    assert db_cnt == count1


@pytest.mark.asyncio
async def test_10_significance_scoring_reflects_newly_refreshed_observation(client: AsyncClient, db_session: AsyncSession):
    """
    10. Significance scoring reflects newly refreshed observation.
    """
    s_sym = f"SIG_{uuid.uuid4().hex[:6]}"
    inst = Instrument(nse_symbol=s_sym, company_name="Significance Move Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "Significance Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    # History: 10 observations with small movements
    base_dt = datetime(2026, 8, 20, 15, 30, 0, tzinfo=timezone.utc)
    for i in range(10):
        dt = base_dt + timedelta(days=i)
        db_session.add(MarketObservation(
            instrument_id=inst.id,
            price=Decimal(f"{100.0 + (i * 0.2):.2f}"),
            volume=1000,
            observed_at=dt,
            source="NSE",
            data_status="final",
        ))
    await db_session.commit()

    # User baseline at day 9
    last_hist_obs = (await db_session.execute(
        select(MarketObservation).where(MarketObservation.instrument_id == inst.id).order_by(MarketObservation.observed_at.desc()).limit(1)
    )).scalar_one()

    uo = UserObservation(user_id=DEV_USER_ID, instrument_id=inst.id, last_seen_observation_id=last_hist_obs.id, last_seen_at=last_hist_obs.observed_at)
    db_session.add(uo)
    await db_session.commit()

    # Ingest large anomalous movement on day 10
    dt_shock = base_dt + timedelta(days=10)
    obs_shock = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("125.00"),  # +22.5% massive jump
        volume=10000,  # 10x volume spike
        observed_at=dt_shock,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs_shock)
    await db_session.commit()

    # Query attention endpoint
    attn_res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn_res.status_code == 200
    data = attn_res.json()

    assert data["summary"]["attention_count"] >= 1
    item = next((it for it in data["items"] if it["instrument_id"] == inst.id), None)
    assert item is not None
    assert item["significance_level"] in ("HIGH", "MEDIUM")
    assert float(item["overall_score"]) >= 0.35
    assert "what_happened" in item["structured_explanation"]
    assert "why_it_stands_out" in item["structured_explanation"]


@pytest.mark.asyncio
async def test_11_honest_data_freshness_reporting(client: AsyncClient, db_session: AsyncSession):
    """
    11. Honest data freshness (NSE Historical EOD, not claimed live).
    """
    s_sym = f"HONEST_{uuid.uuid4().hex[:6]}"
    inst = Instrument(nse_symbol=s_sym, company_name="Honest Data Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl_res = await client.post("/api/v1/watchlists", json={"name": "Honest Data Watchlist"})
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst.id})

    t1 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    obs1 = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("100.00"),
        volume=1000,
        observed_at=t1,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs1)
    await db_session.commit()

    mkt_res = await client.get(f"/api/v1/watchlists/{wl_id}/market")
    assert mkt_res.status_code == 200
    mkt = mkt_res.json()

    assert mkt["source"] == "NSE"
    assert mkt["data_status"] == "HISTORICAL"
    assert "NSE CM-UDiFF EOD Historical Data" in mkt["freshness_note"]

    item = mkt["items"][0]
    assert item["source"] == "NSE"
    assert item["data_status"] == "HISTORICAL"


@pytest.mark.asyncio
async def test_12_multi_session_progression_end_to_end(client: AsyncClient, db_session: AsyncSession):
    """
    12. Multi-session progression end-to-end (Sep 1 -> Sep 2 -> Sep 3 -> Sep 4).
    Tests sequential refresh of available sessions from official NSE bhavcopy files.
    """
    # Find TCS instrument
    tcs_stmt = select(Instrument).where(Instrument.nse_symbol == "TCS")
    tcs = (await db_session.execute(tcs_stmt)).scalar_one_or_none()
    assert tcs is not None

    wl_res = await client.post("/api/v1/watchlists", json={"name": "Multi Session TCS Progression"})
    assert wl_res.status_code == 201
    wl_id = wl_res.json()["id"]
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": tcs.id})

    # Provider sessions available: Sep 1, Sep 2, Sep 3, Sep 4
    provider = NSEHistoricalProvider()
    sessions = provider.get_available_sessions()
    assert len(sessions) >= 4

    # Call refresh endpoint to progress sequentially
    refresh_res = await client.post(f"/api/v1/watchlists/{wl_id}/refresh")
    assert refresh_res.status_code == 200
    r_data = refresh_res.json()
    assert r_data["data_status"] == "HISTORICAL"
    assert r_data["source"] == "NSE"

    # Check market snapshot
    mkt = (await client.get(f"/api/v1/watchlists/{wl_id}/market")).json()
    tcs_mkt = next((it for it in mkt["items"] if it["instrument_id"] == tcs.id), None)
    assert tcs_mkt is not None
    assert tcs_mkt["latest_price"] is not None

    # Mark as checked
    chk_res = await client.post(f"/api/v1/watchlists/{wl_id}/check")
    assert chk_res.status_code == 200

    # Verify no candidate changes immediately after check
    chg_res = await client.get(f"/api/v1/watchlists/{wl_id}/changes")
    assert chg_res.status_code == 200
    assert chg_res.json()["summary"]["instruments_with_changes"] == 0
