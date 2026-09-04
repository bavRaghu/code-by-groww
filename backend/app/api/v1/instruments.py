from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.instrument import Instrument
from app.schemas.instrument import InstrumentResponse

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", response_model=list[InstrumentResponse])
async def list_instruments(
    search: str | None = Query(None, description="Search by NSE symbol or company name"),
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
    stmt = stmt.order_by(Instrument.nse_symbol)
    result = await db.execute(stmt)
    return list(result.scalars().all())
