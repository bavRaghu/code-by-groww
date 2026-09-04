import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.watchlist import Watchlist, WatchlistItem


@pytest.mark.asyncio
async def test_watchlist_market_endpoint(client: AsyncClient, db_session: AsyncSession):
    # 1. Create 3 fresh instruments with unique symbols
    s_no = f"NO_OBS_{uuid.uuid4().hex[:6]}"
    s_one = f"ONE_OBS_{uuid.uuid4().hex[:6]}"
    s_two = f"TWO_OBS_{uuid.uuid4().hex[:6]}"
    inst_no_obs = Instrument(nse_symbol=s_no, company_name="No Obs Company")
    inst_one_obs = Instrument(nse_symbol=s_one, company_name="One Obs Company")
    inst_two_obs = Instrument(nse_symbol=s_two, company_name="Two Obs Company")
    db_session.add_all([inst_no_obs, inst_one_obs, inst_two_obs])
    await db_session.commit()
    await db_session.refresh(inst_no_obs)
    await db_session.refresh(inst_one_obs)
    await db_session.refresh(inst_two_obs)

    # 2. Add observations
    base_time = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    later_time = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)

    # inst_one_obs has only 1 observation
    obs_one = MarketObservation(
        instrument_id=inst_one_obs.id,
        price=Decimal("100.00"),
        volume=1000,
        observed_at=base_time,
        source="NSE",
        data_status="final",
    )

    # inst_two_obs has 2 observations: Day 1: 200.00, Day 2: 250.00 (+50.00, +25.0%)
    obs_prev = MarketObservation(
        instrument_id=inst_two_obs.id,
        price=Decimal("200.00"),
        volume=2000,
        observed_at=base_time,
        source="NSE",
        data_status="final",
    )
    obs_latest = MarketObservation(
        instrument_id=inst_two_obs.id,
        price=Decimal("250.00"),
        volume=3000,
        observed_at=later_time,
        source="NSE",
        data_status="final",
    )
    db_session.add_all([obs_one, obs_prev, obs_latest])
    await db_session.commit()

    # 3. Create watchlist with all 3 instruments
    wl = Watchlist(user_id=1, name="Market Calc Test")
    db_session.add(wl)
    await db_session.commit()
    await db_session.refresh(wl)

    item1 = WatchlistItem(watchlist_id=wl.id, instrument_id=inst_no_obs.id, position=0)
    item2 = WatchlistItem(watchlist_id=wl.id, instrument_id=inst_one_obs.id, position=1)
    item3 = WatchlistItem(watchlist_id=wl.id, instrument_id=inst_two_obs.id, position=2)
    db_session.add_all([item1, item2, item3])
    await db_session.commit()

    # 4. Request market data
    response = await client.get(f"/api/v1/watchlists/{wl.id}/market")
    assert response.status_code == 200
    data = response.json()
    assert data["watchlist_id"] == wl.id
    items = data["items"]
    assert len(items) == 3

    # Case A: No observation
    item_no = next(it for it in items if it["symbol"] == s_no)
    assert item_no["latest_price"] is None
    assert item_no["absolute_change"] is None
    assert item_no["percentage_change"] is None
    assert item_no["volume"] is None
    assert item_no["observed_at"] is None

    # Case B: Single observation (missing previous observation -> change is null)
    item_single = next(it for it in items if it["symbol"] == s_one)
    assert float(item_single["latest_price"]) == 100.00
    assert item_single["absolute_change"] is None
    assert item_single["percentage_change"] is None
    assert item_single["volume"] == 1000
    assert item_single["observed_at"] is not None

    # Case C: Two observations (calculates changes accurately)
    item_multi = next(it for it in items if it["symbol"] == s_two)
    assert float(item_multi["latest_price"]) == 250.00
    assert float(item_multi["absolute_change"]) == 50.00
    assert float(item_multi["percentage_change"]) == 25.00
    assert item_multi["volume"] == 3000
    assert item_multi["observed_at"] is not None


@pytest.mark.asyncio
async def test_market_endpoint_nonexistent_watchlist(client: AsyncClient):
    res = await client.get("/api/v1/watchlists/999999/market")
    assert res.status_code == 404
