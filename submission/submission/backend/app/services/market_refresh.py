import logging
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ingestion.service import IngestionService
from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.watchlist import Watchlist, WatchlistItem
from app.providers.base import MarketDataProvider
from app.providers.nse import NSEHistoricalProvider
from app.schemas.market import MarketRefreshResponse

logger = logging.getLogger(__name__)


async def refresh_watchlist_market(
    db: AsyncSession,
    user_id: int,
    watchlist_id: int,
    provider: MarketDataProvider | None = None,
) -> MarketRefreshResponse:
    """
    Refreshes market observations for all instruments in a watchlist.
    Fetches the next available sequential market session from the provider,
    persisting new MarketObservation records idempotently.
    
    IMPORTANT:
    - Does NOT modify UserObservation (user baseline remains intact).
    - Does NOT fabricate synthetic prices.
    - If no newer market data is available, honestly reports up_to_date.
    """
    if provider is None:
        provider = NSEHistoricalProvider()

    # 1. Fetch watchlist with items
    wl_stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.items).selectinload(WatchlistItem.instrument))
        .where(Watchlist.id == watchlist_id)
    )
    wl_res = await db.execute(wl_stmt)
    watchlist = wl_res.scalar_one_or_none()
    if watchlist is None:
        raise ValueError("Watchlist not found")
    if watchlist.user_id != user_id:
        raise PermissionError("Access denied")

    if not watchlist.items:
        return MarketRefreshResponse(
            status="no_data",
            message="Watchlist has no instruments to refresh.",
            new_observations_count=0,
            latest_observed_at=None,
            latest_session_date=None,
            has_newer_data=False,
            data_status="UNAVAILABLE",
            source="NSE",
        )

    inst_ids = [item.instrument_id for item in watchlist.items if item.instrument]
    watchlist_symbols = {item.instrument.nse_symbol.upper() for item in watchlist.items if item.instrument}

    # 2. Get available sessions from provider
    available_sessions = provider.get_available_sessions()
    if not available_sessions:
        return MarketRefreshResponse(
            status="no_data",
            message="No market data sessions available from provider.",
            new_observations_count=0,
            latest_observed_at=None,
            latest_session_date=None,
            has_newer_data=False,
            data_status="UNAVAILABLE",
            source="NSE",
        )

    # 3. Find current maximum observed_at in DB for these instruments
    max_stmt = select(func.max(MarketObservation.observed_at)).where(
        MarketObservation.instrument_id.in_(inst_ids)
    )
    max_res = await db.execute(max_stmt)
    current_max_observed = max_res.scalar()

    ingestion_service = IngestionService(provider=provider)
    total_persisted = 0

    if current_max_observed is None:
        # No observations exist for watchlist instruments yet.
        # Ingest the first available session.
        target_session = available_sessions[0]
        observations = provider.get_observations_for_session(target_session)
        filtered = [o for o in observations if o.symbol.upper() in watchlist_symbols]
        ingest_res = await ingestion_service.ingest_observations(
            db, filtered or observations, auto_create_instruments=True
        )
        total_persisted += ingest_res.persisted_observations
        has_newer = len(available_sessions) > 1

        return MarketRefreshResponse(
            status="refreshed",
            message=f"Ingested initial market data for session {target_session.strftime('%b %d, %Y')}.",
            new_observations_count=total_persisted,
            latest_observed_at=target_session,
            latest_session_date=target_session.strftime("%Y-%m-%d"),
            has_newer_data=has_newer,
            data_status="HISTORICAL",
            source="NSE",
        )

    # Check for newer sessions
    newer_sessions = [s for s in available_sessions if s > current_max_observed]

    # Also catch up any missing instruments for past sessions <= current_max_observed
    missing_caught_up = False
    for s in available_sessions:
        if s <= current_max_observed:
            obs_at_s_stmt = select(MarketObservation.instrument_id).where(
                MarketObservation.instrument_id.in_(inst_ids),
                MarketObservation.observed_at == s,
            )
            obs_at_s_res = await db.execute(obs_at_s_stmt)
            present_ids = set(obs_at_s_res.scalars().all())
            missing_ids = set(inst_ids) - present_ids
            if missing_ids:
                obs_s = provider.get_observations_for_session(s)
                missing_symbols = {
                    item.instrument.nse_symbol.upper()
                    for item in watchlist.items
                    if item.instrument and item.instrument_id in missing_ids
                }
                filtered_missing = [o for o in obs_s if o.symbol.upper() in missing_symbols]
                if filtered_missing:
                    ing_res = await ingestion_service.ingest_observations(
                        db, filtered_missing, auto_create_instruments=True
                    )
                    total_persisted += ing_res.persisted_observations
                    missing_caught_up = True

    if not newer_sessions:
        msg = f"No newer market data available. Latest available session: {current_max_observed.strftime('%b %d, %Y')}."
        if missing_caught_up:
            msg = f"Caught up newly added instruments to session {current_max_observed.strftime('%b %d, %Y')}."

        return MarketRefreshResponse(
            status="refreshed" if missing_caught_up else "up_to_date",
            message=msg,
            new_observations_count=total_persisted,
            latest_observed_at=current_max_observed,
            latest_session_date=current_max_observed.strftime("%Y-%m-%d"),
            has_newer_data=False,
            data_status="HISTORICAL",
            source="NSE",
        )

    # Next available session
    next_session = newer_sessions[0]
    obs_next = provider.get_observations_for_session(next_session)
    filtered_next = [o for o in obs_next if o.symbol.upper() in watchlist_symbols]
    ingest_res = await ingestion_service.ingest_observations(
        db, filtered_next or obs_next, auto_create_instruments=True
    )
    total_persisted += ingest_res.persisted_observations
    has_more_newer = len(newer_sessions) > 1

    return MarketRefreshResponse(
        status="refreshed",
        message=f"Ingested market data for session {next_session.strftime('%b %d, %Y')}.",
        new_observations_count=total_persisted,
        latest_observed_at=next_session,
        latest_session_date=next_session.strftime("%Y-%m-%d"),
        has_newer_data=has_more_newer,
        data_status="HISTORICAL",
        source="NSE",
    )
