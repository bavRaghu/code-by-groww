from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict


class WatchlistCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    watchlist_id: int
    checked_at: datetime
    number_of_instruments: int
    number_with_market_data: int
    number_without_market_data: int
    last_checked_at: datetime


class DetectedChangeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument_id: int
    symbol: str
    company_name: str
    change_type: str
    magnitude: Decimal | None = None
    detected_at: datetime
    observation_start: datetime
    observation_end: datetime
    baseline_observation_id: int
    baseline_price: Decimal | None = None
    current_observation_id: int
    current_price: Decimal | None = None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    evidence: dict[str, Any] | None = None
    source: str = "NSE"
    data_status: str = "final"
    review_status: str = "surfaced"
    reviewed_at: datetime | None = None


class InstrumentStatusItem(BaseModel):
    instrument_id: int
    symbol: str
    company_name: str
    baseline_observation_id: int | None = None
    baseline_observed_at: datetime | None = None
    current_observation_id: int | None = None
    current_observed_at: datetime | None = None
    status: str
    diagnostics: dict[str, Any] = {}


class ChangesSummary(BaseModel):
    total_instruments: int
    instruments_with_changes: int
    total_candidate_changes: int
    has_unseen_changes: bool


class WatchlistChangesResponse(BaseModel):
    watchlist_id: int
    watchlist_name: str
    last_checked_at: datetime | None = None
    changes: list[DetectedChangeItem]
    instrument_statuses: list[InstrumentStatusItem]
    summary: ChangesSummary
