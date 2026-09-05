import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.user import User
from app.models.user_observation import UserObservation
from app.models.watchlist import Watchlist, WatchlistItem
from app.seed import DEV_USER_ID


@pytest.mark.asyncio
async def test_user_observation_unique_constraint(db_session: AsyncSession):
    """Verifies that a user can have at most one UserObservation per instrument."""
    user = (await db_session.execute(select(User).where(User.id == DEV_USER_ID))).scalar_one()

    # Create dedicated instrument for isolation
    inst = Instrument(nse_symbol="UO_UNIQ_INST", company_name="Unique User Obs Corp")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    now = datetime.now(timezone.utc)
    obs1 = UserObservation(
        user_id=user.id,
        instrument_id=inst.id,
        last_seen_at=now,
        last_seen_observation_id=None,
    )
    db_session.add(obs1)
    await db_session.commit()

    obs2 = UserObservation(
        user_id=user.id,
        instrument_id=inst.id,
        last_seen_at=now,
        last_seen_observation_id=None,
    )
    db_session.add(obs2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_watchlist_check_endpoint_lifecycle(client: AsyncClient, db_session: AsyncSession):
    """
    Tests POST /api/v1/watchlists/{id}/check:
    1. Sets baseline for all instruments with observations.
    2. Leaves last_seen_observation_id null when no observation exists.
    3. Idempotent: repeated checks update timestamps without duplicating rows.
    """
    # Create isolated instruments: one with market data, one without
    inst_with_data = Instrument(nse_symbol="UO_WITH_DATA", company_name="Has Market Data Ltd")
    inst_no_data = Instrument(nse_symbol="UO_NO_DATA", company_name="No Market Data Ltd")
    db_session.add_all([inst_with_data, inst_no_data])
    await db_session.commit()
    await db_session.refresh(inst_with_data)
    await db_session.refresh(inst_no_data)

    # 1. Create a watchlist
    create_res = await client.post("/api/v1/watchlists", json={"name": "Check Lifecycle WL"})
    assert create_res.status_code == 201
    wl_id = create_res.json()["id"]

    # 2. Add instruments
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst_with_data.id})
    await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"instrument_id": inst_no_data.id})

    # Add observation only for inst_with_data
    now = datetime.now(timezone.utc)
    obs = MarketObservation(
        instrument_id=inst_with_data.id,
        price=Decimal("4200.0000"),
        observed_at=now,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs)
    await db_session.commit()
    await db_session.refresh(obs)

    # 3. Call check endpoint
    check_res = await client.post(f"/api/v1/watchlists/{wl_id}/check")
    assert check_res.status_code == 200
    data = check_res.json()
    assert data["watchlist_id"] == wl_id
    assert data["number_of_instruments"] == 2
    assert data["number_with_market_data"] == 1
    assert data["number_without_market_data"] == 1
    assert data["checked_at"] is not None

    # 4. Verify persisted UserObservation records
    uobs_with = (
        await db_session.execute(
            select(UserObservation).where(
                UserObservation.user_id == DEV_USER_ID,
                UserObservation.instrument_id == inst_with_data.id,
            )
        )
    ).scalar_one()
    assert uobs_with.last_seen_observation_id == obs.id

    uobs_without = (
        await db_session.execute(
            select(UserObservation).where(
                UserObservation.user_id == DEV_USER_ID,
                UserObservation.instrument_id == inst_no_data.id,
            )
        )
    ).scalar_one()
    assert uobs_without.last_seen_observation_id is None

    # 5. Check again without new observations (Idempotency test)
    check_res2 = await client.post(f"/api/v1/watchlists/{wl_id}/check")
    assert check_res2.status_code == 200

    # Ensure no duplicate rows exist
    rows = (
        await db_session.execute(
            select(UserObservation).where(
                UserObservation.user_id == DEV_USER_ID,
                UserObservation.instrument_id == inst_with_data.id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
