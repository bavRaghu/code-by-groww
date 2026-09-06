from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.db.session import get_db
from app.models.instrument import Instrument
from app.models.user import User
from app.schemas.instrument import InstrumentResponse
from app.schemas.stock_detail import StockDetailResponse
from app.services.stock_detail import get_stock_detail

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", response_model=list[InstrumentResponse])
async def list_instruments(
    search: str | None = Query(None, description="Search by NSE symbol or company name"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of instruments to return"),
    db: AsyncSession = Depends(get_db),
) -> list[InstrumentResponse]:
    """
    Search or list available instruments.
    """
    stmt = select(Instrument)
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Instrument.nse_symbol.ilike(term),
                Instrument.company_name.ilike(term),
            )
        )
    stmt = stmt.order_by(Instrument.nse_symbol).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{instrument_id}", response_model=StockDetailResponse)
@router.get("/{instrument_id}/detail", response_model=StockDetailResponse)
async def get_instrument_detail(
    instrument_id: int,
    watchlist_id: int | None = Query(None, description="Optional active watchlist context"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> StockDetailResponse:
    """
    Retrieve comprehensive stock detail including 'since you last checked' comparison,
    evidence breakdown, change timeline episodes, and bounded chart series.
    """
    user_id = current_user.id if current_user else 1
    try:
        return await get_stock_detail(
            db=db,
            user_id=user_id,
            instrument_id=instrument_id,
            watchlist_id=watchlist_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

