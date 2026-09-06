from dataclasses import dataclass
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.market_observation import MarketObservation
from app.models.user_observation import UserObservation
from app.models.watchlist import Watchlist, WatchlistItem


@dataclass
class WatchlistCheckResult:
    watchlist_id: int
    checked_at: datetime
    number_of_instruments: int
    number_with_market_data: int
    number_without_market_data: int
    last_checked_at: datetime


async def mark_watchlist_checked(
    db: AsyncSession,
    user_id: int,
    watchlist_id: int,
) -> WatchlistCheckResult:
    """
    Records the user's observation baseline for all instruments in a watchlist.
    Updates UserObservation for each instrument to point to the latest
    persisted MarketObservation without altering market data records.
    Idempotent: repeatedly checking unchanged data updates last_seen_at without duplicating records.
    """
    stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.items))
        .where(Watchlist.id == watchlist_id)
    )
    res = await db.execute(stmt)
    watchlist = res.scalar_one_or_none()
    if watchlist is None:
        raise ValueError("Watchlist not found")
    if watchlist.user_id != user_id:
        raise PermissionError("Access denied")

    check_time = datetime.now(timezone.utc)
    total_instruments = len(watchlist.items)
    with_data = 0
    without_data = 0

    item_ids = [item.instrument_id for item in watchlist.items]
    user_obs_map: dict[int, UserObservation] = {}
    if item_ids:
        uobs_stmt = select(UserObservation).where(
            UserObservation.user_id == user_id,
            UserObservation.instrument_id.in_(item_ids),
        )
        uobs_res = await db.execute(uobs_stmt)
        user_obs_map = {uo.instrument_id: uo for uo in uobs_res.scalars().all()}

    for item in watchlist.items:
        obs_stmt = (
            select(MarketObservation)
            .where(MarketObservation.instrument_id == item.instrument_id)
            .order_by(MarketObservation.observed_at.desc(), MarketObservation.id.desc())
            .limit(1)
        )
        obs_res = await db.execute(obs_stmt)
        latest_obs = obs_res.scalar_one_or_none()

        obs_id = latest_obs.id if latest_obs is not None else None
        if obs_id is not None:
            with_data += 1
        else:
            without_data += 1

        user_obs = user_obs_map.get(item.instrument_id)

        if user_obs is None:
            user_obs = UserObservation(
                user_id=user_id,
                instrument_id=item.instrument_id,
                last_seen_at=check_time,
                last_seen_observation_id=obs_id,
                created_at=check_time,
                updated_at=check_time,
            )
            db.add(user_obs)
            user_obs_map[item.instrument_id] = user_obs
        else:
            user_obs.last_seen_at = check_time
            user_obs.last_seen_observation_id = obs_id
            user_obs.updated_at = check_time

    watchlist.last_checked_at = check_time
    watchlist.updated_at = check_time

    await db.commit()

    return WatchlistCheckResult(
        watchlist_id=watchlist.id,
        checked_at=check_time,
        number_of_instruments=total_instruments,
        number_with_market_data=with_data,
        number_without_market_data=without_data,
        last_checked_at=check_time,
    )
