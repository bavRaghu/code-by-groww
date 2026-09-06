from datetime import datetime
from pydantic import BaseModel, ConfigDict


class InstrumentBase(BaseModel):
    nse_symbol: str
    company_name: str
    exchange: str = "NSE"
    isin: str | None = None
    bse_code: str | None = None
    sector: str | None = None


class InstrumentResponse(InstrumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
