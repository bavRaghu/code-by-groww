import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import pytest_asyncio
from sqlalchemy import delete
from tests.conftest import TestAsyncSessionLocal
from app.models.change_review import ChangeReview
from app.models.detected_change import DetectedChange
from app.models.news_article import NewsArticle
from app.models.significance_assessment import SignificanceAssessment
from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.user_observation import UserObservation
from app.models.watchlist import Watchlist, WatchlistItem
from app.providers.nse import NSEHistoricalProvider
from app.seed import DEV_USER_ID, seed_dev_data
from app.services.market_refresh import refresh_watchlist_market
from app.services.attention import get_watchlist_attention


@pytest_asyncio.fixture(scope="module", autouse=True)
async def cleanup_lifecycle_demo_state():
    yield
    async with TestAsyncSessionLocal() as session:
        await session.execute(delete(ChangeReview))
        await session.execute(delete(SignificanceAssessment))
        await session.execute(delete(DetectedChange))
        await session.execute(delete(UserObservation))
        await session.execute(delete(NewsArticle))
        await session.execute(delete(WatchlistItem))
        await session.execute(delete(Watchlist))
        await session.execute(delete(MarketObservation))
        await session.commit()


@pytest.mark.asyncio
async def test_demo_seed_baseline_and_meaningful_attention(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that seed_dev_data initializes the demo user's baseline at Session 2 (2026-09-02)
    while retaining later observations (Session 3 and Session 4), so the default watchlist
    ('Growth Leaders') immediately demonstrates meaningful changes.
    """
    await seed_dev_data(db_session)

    # 1. Verify 'Growth Leaders' exists
    stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.items).selectinload(Watchlist.items.property.mapper.class_.instrument))
        .where(Watchlist.user_id == DEV_USER_ID, Watchlist.name == "Growth Leaders")
    )
    wl = (await db_session.execute(stmt)).scalar_one_or_none()
    assert wl is not None
    assert len(wl.items) == 6

    # 2. Verify baseline is at Session 2 (2026-09-02)
    tcs_inst = next(it.instrument for it in wl.items if it.instrument.nse_symbol == "TCS")
    uo_stmt = select(UserObservation).where(
        UserObservation.user_id == DEV_USER_ID,
        UserObservation.instrument_id == tcs_inst.id,
    )
    uo = (await db_session.execute(uo_stmt)).scalar_one_or_none()
    assert uo is not None
    assert uo.last_seen_observation_id is not None

    base_obs = (await db_session.execute(
        select(MarketObservation).where(MarketObservation.id == uo.last_seen_observation_id)
    )).scalar_one()
    assert base_obs.observed_at.strftime("%Y-%m-%d") == "2026-09-02"

    # 3. Verify latest market observation is at Session 4 (2026-09-04)
    latest_obs = (await db_session.execute(
        select(MarketObservation)
        .where(MarketObservation.instrument_id == tcs_inst.id)
        .order_by(MarketObservation.observed_at.desc())
        .limit(1)
    )).scalar_one()
    assert latest_obs.observed_at.strftime("%Y-%m-%d") == "2026-09-04"
    assert latest_obs.id != base_obs.id

    # 4. Fetch attention feed via API
    res = await client.get(f"/api/v1/watchlists/{wl.id}/attention")
    assert res.status_code == 200
    data = res.json()

    # Must immediately demonstrate stocks deserving attention
    assert data["summary"]["attention_count"] >= 1
    assert data["summary"]["no_meaningful_change_count"] >= 1

    symbols_in_feed = [it["symbol"] for it in data["items"]]
    assert "TCS" in symbols_in_feed

    tcs_item = next(it for it in data["items"] if it["symbol"] == "TCS")
    assert float(tcs_item["overall_score"]) >= 0.20
    assert tcs_item["significance_level"] in ("LOW", "MEDIUM", "HIGH")
    assert "VOLUME_ANOMALY" in tcs_item["constituent_change_types"]


@pytest.mark.asyncio
async def test_exhausted_sessions_refresh_preserves_baseline(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that calling /refresh when all market sessions are exhausted returns status='up_to_date',
    creates 0 new observations, and crucially DOES NOT advance or mutate the user's baseline.
    The attention feed continues to report changes against Session 2.
    """
    await seed_dev_data(db_session)

    wl_stmt = select(Watchlist).where(Watchlist.user_id == DEV_USER_ID, Watchlist.name == "Growth Leaders")
    wl = (await db_session.execute(wl_stmt)).scalar_one()
    wl_id = wl.id

    # Get baseline observation ID before refresh
    tcs = (await db_session.execute(
        select(Instrument).where(Instrument.nse_symbol == "TCS")
    )).scalar_one()
    tcs_id = tcs.id
    uo_before = (await db_session.execute(
        select(UserObservation).where(
            UserObservation.user_id == DEV_USER_ID,
            UserObservation.instrument_id == tcs_id,
        )
    )).scalar_one()
    baseline_id_before = uo_before.last_seen_observation_id

    # Call refresh endpoint
    ref_res = await client.post(f"/api/v1/watchlists/{wl_id}/refresh")
    assert ref_res.status_code == 200
    ref_data = ref_res.json()
    assert ref_data["status"] == "up_to_date"
    assert ref_data["new_observations_count"] == 0
    assert ref_data["has_newer_data"] is False
    assert "No newer market data available" in ref_data["message"]

    # Verify baseline is unchanged
    db_session.expire_all()
    uo_after = (await db_session.execute(
        select(UserObservation).where(
            UserObservation.user_id == DEV_USER_ID,
            UserObservation.instrument_id == tcs_id,
        )
    )).scalar_one()
    assert uo_after.last_seen_observation_id == baseline_id_before

    # Verify attention feed still returns the changes
    attn_res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn_res.status_code == 200
    assert attn_res.json()["summary"]["attention_count"] >= 1


@pytest.mark.asyncio
async def test_explicit_baseline_advancement_clears_attention(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that explicitly calling POST /watchlists/{id}/check advances the baseline
    to the latest market session, and subsequent change detection / attention feed
    truthfully reports up_to_date with 0 attention items.
    """
    await seed_dev_data(db_session)

    wl_stmt = select(Watchlist).where(Watchlist.user_id == DEV_USER_ID, Watchlist.name == "Growth Leaders")
    wl = (await db_session.execute(wl_stmt)).scalar_one()

    # Prior to check: attention items exist
    attn_before = (await client.get(f"/api/v1/watchlists/{wl.id}/attention")).json()
    assert attn_before["summary"]["attention_count"] >= 1

    # User clicks 'Advance Baseline' (POST /check)
    chk_res = await client.post(f"/api/v1/watchlists/{wl.id}/check")
    assert chk_res.status_code == 200
    chk_data = chk_res.json()
    assert chk_data["watchlist_id"] == wl.id

    # After check: baseline == current market observation
    attn_after = (await client.get(f"/api/v1/watchlists/{wl.id}/attention")).json()
    assert attn_after["summary"]["attention_count"] == 0
    assert len(attn_after["items"]) == 0
    assert attn_after["summary"]["no_meaningful_change_count"] == 6

    # Candidate changes endpoint also reports 0 changes
    chg_after = (await client.get(f"/api/v1/watchlists/{wl.id}/changes")).json()
    assert chg_after["summary"]["instruments_with_changes"] == 0
    assert len(chg_after["changes"]) == 0
