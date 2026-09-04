import uuid
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.user import User
from app.models.watchlist import Watchlist, WatchlistItem


@pytest.mark.asyncio
async def test_user_watchlist_relationship(db_session: AsyncSession):
    # Create user and watchlist
    user = User()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    wl = Watchlist(user_id=user.id, name="Test User WL")
    db_session.add(wl)
    await db_session.commit()

    # Query user with watchlists
    stmt = select(User).where(User.id == user.id)
    res = await db_session.execute(stmt)
    loaded_user = res.scalar_one()
    assert loaded_user.id == user.id

    # Cascade delete
    await db_session.delete(loaded_user)
    await db_session.commit()

    # Verify watchlist was cascade-deleted
    wl_stmt = select(Watchlist).where(Watchlist.id == wl.id)
    wl_res = await db_session.execute(wl_stmt)
    assert wl_res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_instrument_uniqueness(db_session: AsyncSession):
    unique_symbol = f"UNIQ_{uuid.uuid4().hex[:8]}"
    # nse_symbol must be unique
    inst1 = Instrument(nse_symbol=unique_symbol, company_name="Test Company 1")
    db_session.add(inst1)
    await db_session.commit()

    # Attempt inserting another instrument with duplicate nse_symbol
    inst2 = Instrument(nse_symbol=unique_symbol, company_name="Duplicate Company")
    db_session.add(inst2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_watchlist_item_uniqueness(db_session: AsyncSession):
    unique_symbol = f"ITEM_{uuid.uuid4().hex[:8]}"
    # Watchlist 1 -> N WatchlistItem with UNIQUE(watchlist_id, instrument_id)
    inst = Instrument(nse_symbol=unique_symbol, company_name="Item Uniq")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    wl = Watchlist(user_id=1, name="Item Uniq Watchlist")
    db_session.add(wl)
    await db_session.commit()
    await db_session.refresh(wl)

    item1 = WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=0)
    db_session.add(item1)
    await db_session.commit()

    # Add duplicate instrument to same watchlist
    item2 = WatchlistItem(watchlist_id=wl.id, instrument_id=inst.id, position=1)
    db_session.add(item2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_market_observation_persistence(db_session: AsyncSession):
    inst = Instrument(nse_symbol=f"OBS_{uuid.uuid4().hex[:8]}", company_name="Obs Test")
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    now = datetime.now(timezone.utc)
    obs = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1500.25"),
        open=Decimal("1480.00"),
        high=Decimal("1510.00"),
        low=Decimal("1475.50"),
        close=Decimal("1505.00"),
        volume=250000,
        observed_at=now,
        source="NSE",
        data_status="final",
    )
    db_session.add(obs)
    await db_session.commit()

    # Query observation
    stmt = select(MarketObservation).where(MarketObservation.id == obs.id)
    res = await db_session.execute(stmt)
    loaded = res.scalar_one()
    assert loaded.instrument_id == inst.id
    assert loaded.price == Decimal("1500.25")
    assert loaded.volume == 250000
    assert loaded.source == "NSE"

    # Verify unique constraint on (instrument_id, observed_at, source)
    duplicate_obs = MarketObservation(
        instrument_id=inst.id,
        price=Decimal("1500.25"),
        observed_at=now,
        source="NSE",
        data_status="final",
    )
    db_session.add(duplicate_obs)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
