from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.market_observation import MarketObservation
from app.models.watchlist import Watchlist, WatchlistItem
from app.schemas.market import MarketRefreshResponse, WatchlistInstrumentMarket, WatchlistMarketResponse
from app.services.market_refresh import refresh_watchlist_market
from app.seed import DEV_USER_ID

router = APIRouter(prefix="/watchlists", tags=["market"])


@router.post("/{watchlist_id}/refresh", response_model=MarketRefreshResponse)
async def refresh_watchlist_market_endpoint(
    watchlist_id: int,
    db: AsyncSession = Depends(get_db),
) -> MarketRefreshResponse:
    """
    Ingests the next chronological market observation session from the configured provider
    for all instruments in the watchlist.
    Does NOT modify user observation baselines.
    """
    try:
        return await refresh_watchlist_market(db, DEV_USER_ID, watchlist_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


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

        # Fetch latest observation strictly ordered by observed_at descending
        latest_stmt = (
            select(MarketObservation)
            .where(MarketObservation.instrument_id == inst.id)
            .order_by(MarketObservation.observed_at.desc(), MarketObservation.id.desc())
            .limit(1)
        )
        latest_res = await db.execute(latest_stmt)
        latest = latest_res.scalar_one_or_none()

        if latest is None:
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
                    data_status="UNAVAILABLE",
                    source="NSE",
                    freshness_note="No market data recorded yet.",
                )
            )
        else:
            # Fetch strictly prior observation from the same source to calculate change
            prev_stmt = (
                select(MarketObservation)
                .where(
                    MarketObservation.instrument_id == inst.id,
                    MarketObservation.source == latest.source,
                    MarketObservation.observed_at < latest.observed_at,
                )
                .order_by(MarketObservation.observed_at.desc(), MarketObservation.id.desc())
                .limit(1)
            )
            prev_res = await db.execute(prev_stmt)
            previous = prev_res.scalar_one_or_none()

            abs_change: Decimal | None = None
            pct_change: Decimal | None = None
            if previous is not None:
                abs_change = round(latest.price - previous.price, 4)
                if previous.price > 0:
                    pct_change = round(
                        ((latest.price - previous.price) / previous.price) * Decimal("100"), 4
                    )

            obs_date_str = latest.observed_at.strftime("%b %d, %Y")
            market_items.append(
                WatchlistInstrumentMarket(
                    instrument_id=inst.id,
                    symbol=inst.nse_symbol,
                    company_name=inst.company_name,
                    latest_price=latest.price,
                    absolute_change=abs_change,
                    percentage_change=pct_change,
                    volume=latest.volume,
                    observed_at=latest.observed_at,
                    data_status="HISTORICAL",
                    source=latest.source or "NSE",
                    freshness_note=f"Historical EOD data from {latest.source or 'NSE'} ({obs_date_str}).",
                )
            )

    latest_obs_time = max((m.observed_at for m in market_items if m.observed_at is not None), default=None)

    return WatchlistMarketResponse(
        watchlist_id=watchlist.id,
        watchlist_name=watchlist.name,
        items=market_items,
        latest_observed_at=latest_obs_time,
        data_status="HISTORICAL" if latest_obs_time else "UNAVAILABLE",
        source="NSE",
        freshness_note="NSE CM-UDiFF EOD Historical Data",
    )
