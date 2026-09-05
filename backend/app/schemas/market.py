from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class WatchlistInstrumentMarket(BaseModel):
    instrument_id: int
    symbol: str
    company_name: str
    latest_price: Decimal | None = None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    volume: int | None = None
    observed_at: datetime | None = None
    data_status: str = "HISTORICAL"
    source: str = "NSE"
    freshness_note: str | None = None


class WatchlistMarketResponse(BaseModel):
    watchlist_id: int
    watchlist_name: str
    items: list[WatchlistInstrumentMarket]
    latest_observed_at: datetime | None = None
    data_status: str = "HISTORICAL"
    source: str = "NSE"
    freshness_note: str | None = None


class MarketRefreshResponse(BaseModel):
    status: str  # "refreshed" | "up_to_date" | "no_data"
    message: str
    new_observations_count: int = 0
    latest_observed_at: datetime | None = None
    latest_session_date: str | None = None
    has_newer_data: bool = False
    data_status: str = "HISTORICAL"
    source: str = "NSE"
