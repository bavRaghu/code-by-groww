import asyncio
import logging
import os
import sys

# Ensure backend root is in python path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


async def seed_dev_data(session: AsyncSession, seed_demo_market_data: bool = True) -> dict[str, int]:
    """
    Idempotently seeds the deterministic dev user and initial instruments.
    When seed_demo_market_data=True, also ingests all available NSE sessions,
    configures the default 'Growth Leaders' watchlist, and establishes the demo baseline
    at Session 2 (2026-09-02) so meaningful changes are immediately demonstrable.
    Returns counts of created records.
    """
    counts = {"users_created": 0, "instruments_created": 0}

    # 1. Deterministic Dev User
    from app.core.security import hash_password

    user_stmt = select(User).where(User.id == DEV_USER_ID)
    user_result = await session.execute(user_stmt)
    dev_user = user_result.scalar_one_or_none()
    if dev_user is None:
        dev_user = User(
            id=DEV_USER_ID,
            email="dev@example.com",
            hashed_password=hash_password("password123"),
            name="Dev User",
            is_active=True,
        )
        session.add(dev_user)
        counts["users_created"] += 1
        logger.info("Created development user with id=%d (dev@example.com)", DEV_USER_ID)
    else:
        if not getattr(dev_user, "email", None) or not getattr(dev_user, "hashed_password", None):
            dev_user.email = "dev@example.com"
            dev_user.hashed_password = hash_password("password123")
            dev_user.name = "Dev User"
            dev_user.is_active = True
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

    # 3. Populate wider NSE instrument universe from security master
    try:
        from app.providers.nse import NSEHistoricalProvider
        provider = NSEHistoricalProvider()
        wider_instruments = provider.get_available_instruments()
        for winst in wider_instruments:
            sym = winst["nse_symbol"]
            inst_stmt = select(Instrument).where(Instrument.nse_symbol == sym)
            inst_res = await session.execute(inst_stmt)
            if inst_res.scalar_one_or_none() is None:
                session.add(Instrument(
                    nse_symbol=sym,
                    company_name=winst["company_name"],
                    isin=winst.get("isin"),
                    exchange="NSE",
                ))
                counts["instruments_created"] += 1
                logger.info("Imported instrument %s (%s)", sym, winst["company_name"])
        await session.commit()
    except Exception as e:
        logger.warning("Could not load wider NSE security master: %s", e)

    # 4. Clean up any transient test/verification artifacts from past test runs
    from app.models.watchlist import Watchlist, WatchlistItem
    from app.models.market_observation import MarketObservation
    from app.models.detected_change import DetectedChange
    from app.models.user_observation import UserObservation
    from sqlalchemy import delete

    test_insts = (await session.execute(
        select(Instrument).where(
            (Instrument.nse_symbol.like("VERIFY%")) | (Instrument.company_name.like("%Verification%"))
        )
    )).scalars().all()
    test_inst_ids = [ti.id for ti in test_insts]

    test_wls = (await session.execute(
        select(Watchlist).where(
            (Watchlist.name.ilike("%verification%")) | (Watchlist.name == "Verification WL")
        )
    )).scalars().all()
    test_wl_ids = [tw.id for tw in test_wls]

    if test_wl_ids or test_inst_ids:
        await session.execute(delete(WatchlistItem).where(
            (WatchlistItem.watchlist_id.in_(test_wl_ids)) | (WatchlistItem.instrument_id.in_(test_inst_ids))
        ))
        if test_inst_ids:
            await session.execute(delete(UserObservation).where(UserObservation.instrument_id.in_(test_inst_ids)))
            await session.execute(delete(DetectedChange).where(DetectedChange.instrument_id.in_(test_inst_ids)))
            await session.execute(delete(MarketObservation).where(MarketObservation.instrument_id.in_(test_inst_ids)))
            await session.execute(delete(Instrument).where(Instrument.id.in_(test_inst_ids)))
        if test_wl_ids:
            await session.execute(delete(Watchlist).where(Watchlist.id.in_(test_wl_ids)))
        await session.commit()

    # 5. Ingest market sessions and initialize demo baseline at Session 2 (2026-09-02)
    if seed_demo_market_data:
        from app.ingestion.service import IngestionService
        from app.providers.nse import NSEHistoricalProvider
        from app.models.watchlist import Watchlist, WatchlistItem
        from app.models.market_observation import MarketObservation
        from app.models.user_observation import UserObservation
        from sqlalchemy.orm import selectinload

        provider = NSEHistoricalProvider()
        available_sessions = provider.get_available_sessions()

        # Ingest observations for all available sessions (Sep 1, Sep 2, Sep 3, Sep 4)
        if available_sessions:
            ingestion_service = IngestionService(provider=provider)
            for s in available_sessions:
                obs_list = provider.get_observations_for_session(s)
                if obs_list:
                    await ingestion_service.ingest_observations(session, obs_list, auto_create_instruments=True)

            # Target baseline is Session 2 (2026-09-02)
            session_2_dt = available_sessions[1] if len(available_sessions) > 1 else available_sessions[0]

            # Ensure demo watchlist "Growth Leaders" exists
            demo_wl_stmt = select(Watchlist).options(selectinload(Watchlist.items)).where(
                Watchlist.user_id == DEV_USER_ID,
                Watchlist.name == "Growth Leaders",
            )
            demo_wl_res = await session.execute(demo_wl_stmt)
            demo_wl = demo_wl_res.scalar_one_or_none()

            if demo_wl is None:
                demo_wl = Watchlist(
                    user_id=DEV_USER_ID,
                    name="Growth Leaders",
                    last_checked_at=session_2_dt,
                )
                session.add(demo_wl)
                await session.flush()
            else:
                demo_wl.last_checked_at = session_2_dt

            demo_symbols = ["TCS", "RELIANCE", "INFY", "HDFCBANK", "SBIN", "TATAMOTORS"]
            for pos, sym in enumerate(demo_symbols):
                inst_stmt = select(Instrument).where(Instrument.nse_symbol == sym)
                inst = (await session.execute(inst_stmt)).scalar_one_or_none()
                if not inst:
                    continue

                # Ensure item in watchlist
                item_stmt = select(WatchlistItem).where(
                    WatchlistItem.watchlist_id == demo_wl.id,
                    WatchlistItem.instrument_id == inst.id,
                )
                item = (await session.execute(item_stmt)).scalar_one_or_none()
                if item is None:
                    session.add(WatchlistItem(
                        watchlist_id=demo_wl.id,
                        instrument_id=inst.id,
                        position=pos,
                    ))

                # Point UserObservation to Session 2 observation
                s2_obs_stmt = (
                    select(MarketObservation)
                    .where(
                        MarketObservation.instrument_id == inst.id,
                        MarketObservation.observed_at == session_2_dt,
                    )
                    .order_by(MarketObservation.id.desc())
                    .limit(1)
                )
                s2_obs = (await session.execute(s2_obs_stmt)).scalar_one_or_none()
                if s2_obs:
                    uo_stmt = select(UserObservation).where(
                        UserObservation.user_id == DEV_USER_ID,
                        UserObservation.instrument_id == inst.id,
                    )
                    uo = (await session.execute(uo_stmt)).scalar_one_or_none()
                    if uo is None:
                        session.add(UserObservation(
                            user_id=DEV_USER_ID,
                            instrument_id=inst.id,
                            last_seen_observation_id=s2_obs.id,
                            last_seen_at=session_2_dt,
                        ))
                    else:
                        uo.last_seen_observation_id = s2_obs.id
                        uo.last_seen_at = session_2_dt

            await session.commit()

    # Advance sequences past seeded IDs so autoincrement doesn't conflict
    from sqlalchemy import text
    bind = session.get_bind()
    if bind and bind.dialect.name == "postgresql":
        await session.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), coalesce((SELECT max(id) FROM users), 1))"))
        await session.execute(text("SELECT setval(pg_get_serial_sequence('instruments', 'id'), coalesce((SELECT max(id) FROM instruments), 1))"))
        await session.execute(text("SELECT setval(pg_get_serial_sequence('watchlists', 'id'), coalesce((SELECT max(id) FROM watchlists), 1))"))
        await session.execute(text("SELECT setval(pg_get_serial_sequence('watchlist_items', 'id'), coalesce((SELECT max(id) FROM watchlist_items), 1))"))
        await session.execute(text("SELECT setval(pg_get_serial_sequence('market_observations', 'id'), coalesce((SELECT max(id) FROM market_observations), 1))"))
        await session.execute(text("SELECT setval(pg_get_serial_sequence('user_observations', 'id'), coalesce((SELECT max(id) FROM user_observations), 1))"))
        await session.commit()

    return counts


async def main() -> None:
    async with AsyncSessionLocal() as session:
        counts = await seed_dev_data(session)
        logger.info("Seeding completed: %s", counts)


if __name__ == "__main__":
    asyncio.run(main())
