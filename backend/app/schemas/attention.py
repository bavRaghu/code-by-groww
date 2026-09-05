from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class InstrumentReference(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    company_name: str


class StructuredExplanation(BaseModel):
    what_happened: str
    why_it_stands_out: str
    supporting_evidence: list[str] = Field(default_factory=list)
    missing_data_notes: list[str] = Field(default_factory=list)


class EvidenceCompleteness(BaseModel):
    level: str  # "STRONG", "MODERATE", "LIMITED"
    available_signals_count: int
    total_signals_count: int = 5
    summary: str
    available_signals: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)


class UnderlyingChangeSummary(BaseModel):
    id: int
    change_type: str
    magnitude: Decimal | None = None
    evidence: dict[str, Any] | None = None
    detected_at: datetime
    review_status: str = "surfaced"
    reviewed_at: datetime | None = None


class ComponentScores(BaseModel):
    magnitude: Decimal | None = None
    abnormality: Decimal | None = None
    relative_performance: Decimal | None = None
    volume: Decimal | None = None
    event: Decimal | None = None


class AttentionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument: InstrumentReference
    instrument_id: int
    symbol: str
    company_name: str

    significance_level: str  # HIGH, MEDIUM, LOW, NONE
    overall_score: Decimal
    component_scores: ComponentScores

    current_price: Decimal | None = None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None

    baseline_observation_id: int
    baseline_price: Decimal | None = None
    baseline_timestamp: datetime | None = None
    baseline_observed_at: datetime | None = None

    current_observation_id: int
    current_timestamp: datetime | None = None
    current_observed_at: datetime | None = None

    changes: list[UnderlyingChangeSummary] = Field(default_factory=list)
    constituent_change_types: list[str] = Field(default_factory=list)

    evidence: dict[str, Any]
    explanation: str
    structured_explanation: StructuredExplanation
    evidence_completeness: EvidenceCompleteness | None = None
    freshness_note: str = ""

    source: str = "NSE"
    data_status: str = "final"
    review_status: str = "surfaced"  # "surfaced" | "reviewed"
    is_reviewed: bool = False
    reviewed_at: datetime | None = None


class ChangeFeedItem(BaseModel):
    id: int
    instrument_id: int
    symbol: str
    company_name: str
    change_type: str
    significance_level: str
    overall_score: Decimal
    timestamp: datetime
    baseline_observed_at: datetime | None = None
    current_observed_at: datetime | None = None
    baseline_price: Decimal | None = None
    current_price: Decimal | None = None
    percentage_change: Decimal | None = None
    absolute_change: Decimal | None = None
    metrics_summary: str = ""
    explanation: str = ""
    evidence_bullets: list[str] = Field(default_factory=list)
    source: str = "NSE"
    data_status: str = "HISTORICAL"
    review_status: str = "surfaced"  # "surfaced" | "reviewed"
    is_reviewed: bool = False
    reviewed_at: datetime | None = None


class AttentionSummary(BaseModel):
    total_instruments: int
    instruments_evaluated: int
    attention_count: int
    high_count: int
    medium_count: int
    low_count: int
    no_meaningful_change_count: int
    insufficient_data_count: int
    unreviewed_count: int = 0
    reviewed_count: int = 0

    # Backward compatibility aliases
    instruments_with_changes: int = 0
    instruments_with_meaningful_changes: int = 0
    instruments_without_meaningful_changes: int = 0


class InsufficientDataItem(BaseModel):
    instrument_id: int
    symbol: str
    company_name: str
    reason: str


class QuietInstrumentItem(BaseModel):
    instrument_id: int
    symbol: str
    company_name: str
    reason: str


class WatchlistAttentionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    watchlist_id: int
    watchlist_name: str
    last_checked_at: datetime | None = None
    items: list[AttentionItem] = Field(default_factory=list)
    attention_items: list[AttentionItem] = Field(default_factory=list)
    feed_items: list[ChangeFeedItem] = Field(default_factory=list)
    summary: AttentionSummary
    quiet_instruments: list[QuietInstrumentItem] = Field(default_factory=list)
    insufficient_data_instruments: list[InsufficientDataItem] = Field(default_factory=list)


class ChangeReviewResponse(BaseModel):
    change_id: int
    review_status: str
    reviewed_at: datetime


class InstrumentReviewResponse(BaseModel):
    instrument_id: int
    reviewed_changes_count: int
    review_status: str
    reviewed_at: datetime


class WatchlistReviewAllResponse(BaseModel):
    watchlist_id: int
    reviewed_changes_count: int
    review_status: str
    reviewed_at: datetime

