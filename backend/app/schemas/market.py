from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class WatchlistInstrumentMarket(BaseModel):
    instrument_id: int
    symbol: str
    company_name: str
    latest_price: Decimal | None = None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    volume: int | None = None
    observed_at: datetime | None = None
    data_status: str | None = None
    source: str | None = None


class WatchlistMarketResponse(BaseModel):
    watchlist_id: int
    watchlist_name: str
    items: list[WatchlistInstrumentMarket]
