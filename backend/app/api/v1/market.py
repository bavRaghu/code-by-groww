from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.market_observation import MarketObservation
from app.models.watchlist import Watchlist, WatchlistItem
from app.schemas.market import WatchlistInstrumentMarket, WatchlistMarketResponse
from app.seed import DEV_USER_ID

router = APIRouter(prefix="/watchlists", tags=["market"])


@router.get("/{watchlist_id}/market", response_model=WatchlistMarketResponse)
async def get_watchlist_market(
    watchlist_id: int,
    db: AsyncSession = Depends(get_db),
) -> WatchlistMarketResponse:
    # 1. Fetch watchlist with items and instruments
    wl_stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.items).selectinload(WatchlistItem.instrument))
        .where(Watchlist.id == watchlist_id)
    )
    wl_result = await db.execute(wl_stmt)
    watchlist = wl_result.scalar_one_or_none()
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    if watchlist.user_id != DEV_USER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Sort watchlist items according to position
    sorted_items = sorted(watchlist.items, key=lambda x: x.position)

    market_items: list[WatchlistInstrumentMarket] = []

    for item in sorted_items:
        inst = item.instrument
        if inst is None:
            continue

        # Fetch latest two observations to calculate change
        obs_stmt = (
            select(MarketObservation)
            .where(MarketObservation.instrument_id == inst.id)
            .order_by(MarketObservation.observed_at.desc())
            .limit(2)
        )
        obs_res = await db.execute(obs_stmt)
        observations = obs_res.scalars().all()

        if not observations:
            # No observation available
            market_items.append(
                WatchlistInstrumentMarket(
                    instrument_id=inst.id,
                    symbol=inst.nse_symbol,
                    company_name=inst.company_name,
                    latest_price=None,
                    absolute_change=None,
                    percentage_change=None,
                    volume=None,
                    observed_at=None,
                    data_status=None,
                    source=None,
                )
            )
        elif len(observations) == 1:
            # Only latest observation, no previous observation to calculate change
            latest = observations[0]
            market_items.append(
                WatchlistInstrumentMarket(
                    instrument_id=inst.id,
                    symbol=inst.nse_symbol,
                    company_name=inst.company_name,
                    latest_price=latest.price,
                    absolute_change=None,
                    percentage_change=None,
                    volume=latest.volume,
                    observed_at=latest.observed_at,
                    data_status=latest.data_status,
                    source=latest.source,
                )
            )
        else:
            # Latest and previous observations available
            latest = observations[0]
            previous = observations[1]
            abs_change = latest.price - previous.price
            pct_change = (
                round(((latest.price - previous.price) / previous.price) * Decimal("100"), 4)
                if previous.price > 0
                else None
            )

            market_items.append(
                WatchlistInstrumentMarket(
                    instrument_id=inst.id,
                    symbol=inst.nse_symbol,
                    company_name=inst.company_name,
                    latest_price=latest.price,
                    absolute_change=round(abs_change, 4),
                    percentage_change=pct_change,
                    volume=latest.volume,
                    observed_at=latest.observed_at,
                    data_status=latest.data_status,
                    source=latest.source,
                )
            )

    return WatchlistMarketResponse(
        watchlist_id=watchlist.id,
        watchlist_name=watchlist.name,
        items=market_items,
    )
