import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.user import User
from app.seed import DEV_USER_ID, SEED_INSTRUMENTS, seed_dev_data


@pytest.mark.asyncio
async def test_seed_creates_required_instruments_and_user(db_session: AsyncSession):
    # Ensure seed executed
    await seed_dev_data(db_session)

    # 1. Dev user exists with deterministic ID
    user_stmt = select(User).where(User.id == DEV_USER_ID)
    user_res = await db_session.execute(user_stmt)
    user = user_res.scalar_one_or_none()
    assert user is not None
    assert user.id == 1

    # 2. Required instruments exist
    expected_symbols = [item["nse_symbol"] for item in SEED_INSTRUMENTS]
    assert len(expected_symbols) == 6
    assert set(expected_symbols) == {"TCS", "RELIANCE", "INFY", "HDFCBANK", "SBIN", "ICICIBANK"}

    inst_stmt = select(Instrument).where(Instrument.nse_symbol.in_(expected_symbols))
    inst_res = await db_session.execute(inst_stmt)
    found = inst_res.scalars().all()
    found_symbols = {inst.nse_symbol for inst in found}
    assert found_symbols == set(expected_symbols)


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session: AsyncSession):
    # Running seed second time must not create duplicates or fail
    counts = await seed_dev_data(db_session)
    assert counts["users_created"] == 0
    assert counts["instruments_created"] == 0

    # Total instruments count should still have exactly one of each
    for symbol in ["TCS", "RELIANCE", "INFY", "HDFCBANK", "SBIN", "ICICIBANK"]:
        stmt = select(func.count(Instrument.id)).where(Instrument.nse_symbol == symbol)
        res = await db_session.execute(stmt)
        count = res.scalar_one()
        assert count == 1, f"Expected 1 record for {symbol}, got {count}"
