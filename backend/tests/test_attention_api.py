import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.seed import DEV_USER_ID


@pytest.mark.asyncio
async def test_end_to_end_attention_api_lifecycle(client: AsyncClient, db_session: AsyncSession):
    """
    Tests full attention ranking flow via FastAPI HTTP endpoints:
    1. User creates watchlist and adds 2 stocks.
    2. Observations exist at T0. User establishes baseline with POST /check.
    3. New observations arrive at T1:
       - Stock 1 moves +8% (Meaningful change -> HIGH/MEDIUM attention item)
       - Stock 2 moves +0.02% (Negligible move -> NONE level, excluded from active attention feed)
    4. GET /api/v1/watchlists/{id}/attention returns:
       - attention_items containing only Stock 1
       - summary showing total=2, meaningful=1, without_meaningful=1
    5. User calls POST /check to acknowledge and advance baseline.
    6. GET /api/v1/watchlists/{id}/attention returns 0 attention items (all caught up).
    """
    # 1. Create two isolated test instruments
    stock1 = Instrument(nse_symbol="ATTN_API_1", company_name="High Move Corp")
    stock2 = Instrument(nse_symbol="ATTN_API_2", company_name="Flat Move Corp")
    db_session.add_all([stock1, stock2])
    await db_session.commit()
    await db_session.refresh(stock1)
    await db_session.refresh(stock2)

    # Create watchlist and add both stocks
    wl_res = await client.post("/api/v1/watchlists", json={"name": "Attention API Test Watchlist"})
    assert wl_res.status_code == 201
    wl_id = wl_res.json()["id"]

    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": stock1.id})
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": stock2.id})

    # T0 observations
    t0 = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    obs1_t0 = MarketObservation(instrument_id=stock1.id, price=Decimal("1000.00"), observed_at=t0, source="NSE", data_status="final")
    obs2_t0 = MarketObservation(instrument_id=stock2.id, price=Decimal("500.00"), observed_at=t0, source="NSE", data_status="final")
    db_session.add_all([obs1_t0, obs2_t0])
    await db_session.commit()

    # User establishes baseline
    check_res = await client.post(f"/api/v1/watchlists/{wl_id}/check")
    assert check_res.status_code == 200

    # T1 observations: Stock 1 moves +8% to ₹1,080; Stock 2 moves +0.02% to ₹500.10
    t1 = datetime(2026, 9, 2, 15, 30, 0, tzinfo=timezone.utc)
    obs1_t1 = MarketObservation(instrument_id=stock1.id, price=Decimal("1080.00"), observed_at=t1, source="NSE", data_status="final")
    obs2_t1 = MarketObservation(instrument_id=stock2.id, price=Decimal("500.10"), observed_at=t1, source="NSE", data_status="final")
    db_session.add_all([obs1_t1, obs2_t1])
    await db_session.commit()

    # Query Attention Endpoint
    attn_res = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn_res.status_code == 200
    data = attn_res.json()

    # Verify response schema
    assert data["watchlist_id"] == wl_id
    assert data["watchlist_name"] == "Attention API Test Watchlist"
    assert data["last_checked_at"] is not None

    summary = data["summary"]
    assert summary["total_instruments"] == 2
    assert summary["instruments_with_meaningful_changes"] == 1
    assert summary["instruments_without_meaningful_changes"] == 1

    # Verify Attention Items
    items = data["attention_items"]
    assert len(items) == 1
    item = items[0]
    assert item["symbol"] == "ATTN_API_1"
    assert item["significance_level"] in ("HIGH", "MEDIUM")
    assert float(item["overall_score"]) >= 0.40
    assert "PRICE_MOVE" in item["constituent_change_types"]
    assert item["baseline_price"] == "1000.0000"
    assert item["current_price"] == "1080.0000"
    assert "explanation" in item
    assert "caused by" not in item["explanation"].lower()

    # Advance baseline to T1
    check2_res = await client.post(f"/api/v1/watchlists/{wl_id}/check")
    assert check2_res.status_code == 200

    # Query Attention Endpoint again -> All caught up!
    attn_res2 = await client.get(f"/api/v1/watchlists/{wl_id}/attention")
    assert attn_res2.status_code == 200
    data2 = attn_res2.json()

    assert len(data2["attention_items"]) == 0
    assert data2["summary"]["instruments_with_meaningful_changes"] == 0
    assert data2["summary"]["instruments_without_meaningful_changes"] == 2


@pytest.mark.asyncio
async def test_attention_endpoint_error_handling(client: AsyncClient):
    # Non-existent watchlist returns 404
    res = await client.get("/api/v1/watchlists/999999/attention")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
