import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.instrument import Instrument

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Deterministic development user ID
DEV_USER_ID = 1

# Authoritative seed instruments with NSE symbols and well-known company names
SEED_INSTRUMENTS = [
    {
        "nse_symbol": "TCS",
        "company_name": "Tata Consultancy Services Limited",
        "exchange": "NSE",
    },
    {
        "nse_symbol": "RELIANCE",
        "company_name": "Reliance Industries Limited",
        "exchange": "NSE",
    },
    {
        "nse_symbol": "INFY",
        "company_name": "Infosys Limited",
        "exchange": "NSE",
    },
    {
        "nse_symbol": "HDFCBANK",
        "company_name": "HDFC Bank Limited",
        "exchange": "NSE",
    },
    {
        "nse_symbol": "SBIN",
        "company_name": "State Bank of India",
        "exchange": "NSE",
    },
    {
        "nse_symbol": "ICICIBANK",
        "company_name": "ICICI Bank Limited",
        "exchange": "NSE",
    },
]


async def seed_dev_data(session: AsyncSession) -> dict[str, int]:
    """
    Idempotently seeds the deterministic dev user and initial instruments.
    Returns counts of created records.
    """
    counts = {"users_created": 0, "instruments_created": 0}

    # 1. Deterministic Dev User
    user_stmt = select(User).where(User.id == DEV_USER_ID)
    user_result = await session.execute(user_stmt)
    dev_user = user_result.scalar_one_or_none()
    if dev_user is None:
        dev_user = User(id=DEV_USER_ID)
        session.add(dev_user)
        counts["users_created"] += 1
        logger.info("Created development user with id=%d", DEV_USER_ID)
    else:
        logger.info("Development user id=%d already exists", DEV_USER_ID)

    # 2. Instruments
    for inst_data in SEED_INSTRUMENTS:
        inst_stmt = select(Instrument).where(Instrument.nse_symbol == inst_data["nse_symbol"])
        inst_result = await session.execute(inst_stmt)
        existing = inst_result.scalar_one_or_none()
        if existing is None:
            new_inst = Instrument(
                nse_symbol=inst_data["nse_symbol"],
                company_name=inst_data["company_name"],
                exchange=inst_data["exchange"],
                isin=None,
                bse_code=None,
                sector=None,
            )
            session.add(new_inst)
            counts["instruments_created"] += 1
            logger.info("Created instrument %s (%s)", inst_data["nse_symbol"], inst_data["company_name"])
        else:
            logger.info("Instrument %s already exists", inst_data["nse_symbol"])

    await session.commit()

    # Advance sequences past seeded IDs so autoincrement doesn't conflict
    from sqlalchemy import text
    await session.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), coalesce((SELECT max(id) FROM users), 1))"))
    await session.execute(text("SELECT setval(pg_get_serial_sequence('instruments', 'id'), coalesce((SELECT max(id) FROM instruments), 1))"))
    await session.commit()

    return counts


async def main() -> None:
    async with AsyncSessionLocal() as session:
        counts = await seed_dev_data(session)
        logger.info("Seeding completed: %s", counts)


if __name__ == "__main__":
    asyncio.run(main())
