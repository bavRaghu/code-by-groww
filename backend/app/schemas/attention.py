from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict


class ComponentScores(BaseModel):
    magnitude: Decimal | None = None
    abnormality: Decimal | None = None
    relative_performance: Decimal | None = None
    volume: Decimal | None = None
    event: Decimal | None = None


class AttentionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: int
    symbol: str
    company_name: str
    significance_level: str  # HIGH, MEDIUM, LOW, NONE
    overall_score: Decimal
    component_scores: ComponentScores
    explanation: str
    evidence: dict[str, Any]
    constituent_change_types: list[str]
    baseline_observation_id: int
    baseline_price: Decimal | None = None
    baseline_observed_at: datetime | None = None
    current_observation_id: int
    current_price: Decimal | None = None
    current_observed_at: datetime | None = None
    source: str = "NSE"
    data_status: str = "final"


class AttentionSummary(BaseModel):
    total_instruments: int
    instruments_with_changes: int
    instruments_with_meaningful_changes: int
    instruments_without_meaningful_changes: int
    high_count: int
    medium_count: int
    low_count: int


class WatchlistAttentionResponse(BaseModel):
    watchlist_id: int
    watchlist_name: str
    last_checked_at: datetime | None = None
    attention_items: list[AttentionItem]
    summary: AttentionSummary
