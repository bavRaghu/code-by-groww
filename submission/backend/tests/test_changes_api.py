import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.seed import DEV_USER_ID


@pytest.mark.asyncio
async def test_end_to_end_changes_lifecycle(client: AsyncClient, db_session: AsyncSession):
    """
    Implements and verifies the exact Definition of Done lifecycle:
    STATE A:
      Stock latest observation = Sep 3.
      User checks watchlist.
      System stores last_seen_observation_id = Sep 3 observation.
    STATE B:
      Sep 4 observation becomes available.
      User returns and requests changes.
      System detects candidate PRICE_MOVE with exact absolute and percentage change.
    STATE C:
      User marks watchlist as checked.
      Baseline advances to Sep 4.
      Running detection again produces no new changes relative to the new baseline.
    """
    # Create isolated test stock
    stock = Instrument(nse_symbol="DOD_TCS", company_name="DoD Test TCS Corp")
    db_session.add(stock)
    await db_session.commit()
    await db_session.refresh(stock)

    # 1. Create watchlist and add stock
    wl_res = await client.post("/api/v1/watchlists", json={"name": "DoD Lifecycle Watchlist"})
    assert wl_res.status_code == 201
    wl_id = wl_res.json()["id"]

    item_res = await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": stock.id})
    assert item_res.status_code == 201

    # STATE A:
    # Latest observation = Sep 3 (₹3,980)
    t_sep3 = datetime(2026, 9, 3, 15, 30, 0, tzinfo=timezone.utc)
    obs_sep3 = MarketObservation(
        instrument_id=stock.id,
        price=Decimal("3980.0000"),
        observed_at=t_sep3,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs_sep3)
    await db_session.commit()
    await db_session.refresh(obs_sep3)

    # User checks watchlist
    check_a = await client.post(f"/api/v1/watchlists/{wl_id}/check")
    assert check_a.status_code == 200
    assert check_a.json()["number_with_market_data"] == 1

    # Verify no changes right after checking
    changes_a = await client.get(f"/api/v1/watchlists/{wl_id}/changes")
    assert changes_a.status_code == 200
    data_a = changes_a.json()
    assert len(data_a["changes"]) == 0
    assert data_a["summary"]["has_unseen_changes"] is False

    # STATE B:
    # Sep 4 observation becomes available: ₹4,150 (+₹170, +4.2714%)
    t_sep4 = datetime(2026, 9, 4, 15, 30, 0, tzinfo=timezone.utc)
    obs_sep4 = MarketObservation(
        instrument_id=stock.id,
        price=Decimal("4150.0000"),
        observed_at=t_sep4,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs_sep4)
    await db_session.commit()
    await db_session.refresh(obs_sep4)

    # User returns -> query changes
    changes_b = await client.get(f"/api/v1/watchlists/{wl_id}/changes")
    assert changes_b.status_code == 200
    data_b = changes_b.json()
    assert data_b["summary"]["has_unseen_changes"] is True
    assert len(data_b["changes"]) >= 1

    price_move = next(c for c in data_b["changes"] if c["change_type"] == "PRICE_MOVE")
    assert price_move["symbol"] == "DOD_TCS"
    assert price_move["baseline_observation_id"] == obs_sep3.id
    assert price_move["current_observation_id"] == obs_sep4.id
    assert float(price_move["baseline_price"]) == 3980.0
    assert float(price_move["current_price"]) == 4150.0
    assert float(price_move["absolute_change"]) == 170.0
    expected_pct = round(((4150.0 - 3980.0) / 3980.0) * 100, 4)
    assert round(float(price_move["percentage_change"]), 4) == expected_pct

    # STATE C:
    # User marks watchlist as checked
    check_c = await client.post(f"/api/v1/watchlists/{wl_id}/check")
    assert check_c.status_code == 200

    # Baseline has advanced to Sep 4
    # Query changes again -> 0 new changes relative to the new baseline!
    changes_c = await client.get(f"/api/v1/watchlists/{wl_id}/changes")
    assert changes_c.status_code == 200
    data_c = changes_c.json()
    assert len(data_c["changes"]) == 0
    assert data_c["summary"]["has_unseen_changes"] is False


@pytest.mark.asyncio
async def test_changes_api_error_handling(client: AsyncClient):
    """Verifies 404 for nonexistent watchlist on check and changes endpoints."""
    res_check = await client.post("/api/v1/watchlists/999999/check")
    assert res_check.status_code == 404

    res_changes = await client.get("/api/v1/watchlists/999999/changes")
    assert res_changes.status_code == 404
