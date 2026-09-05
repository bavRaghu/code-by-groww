from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attention import ComponentScores, EvidenceCompleteness, StructuredExplanation


class CurrentObservationDetail(BaseModel):
    price: Decimal | None = None
    observed_at: datetime | None = None
    volume: int | None = None
    source: str = "NSE"
    data_status: str = "final"
    session_absolute_change: Decimal | None = None
    session_percentage_change: Decimal | None = None


class SinceLastCheckedDetail(BaseModel):
    has_baseline: bool = False
    baseline_observation_id: int | None = None
    baseline_price: Decimal | None = None
    baseline_observed_at: datetime | None = None
    current_observation_id: int | None = None
    current_price: Decimal | None = None
    current_observed_at: datetime | None = None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    significance_level: str | None = None
    overall_score: Decimal | None = None
    is_reviewed: bool = False
    review_status: str = "surfaced"
    reviewed_at: datetime | None = None
    tracking_note: str = ""


class MarketContextDetail(BaseModel):
    benchmark_symbol: str = "NIFTY 50"
    stock_return: float | None = None
    benchmark_return: float | None = None
    excess_return: float | None = None
    status: str = "available"  # "available" | "unavailable"
    context_summary: str = ""


class EvidenceDetail(BaseModel):
    significance_level: str
    overall_score: Decimal | None = None
    why_it_matters: str = ""
    evidence_bullets: list[str] = Field(default_factory=list)
    missing_data_notes: list[str] = Field(default_factory=list)
    evidence_completeness: EvidenceCompleteness | None = None
    component_scores: ComponentScores | None = None
    structured_explanation: StructuredExplanation | None = None


class TimelineEpisode(BaseModel):
    id: int
    baseline_observation_id: int | None = None
    current_observation_id: int
    observation_start: datetime | None = None
    observation_end: datetime
    baseline_price: Decimal | None = None
    current_price: Decimal | None = None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    volume: int | None = None
    significance_level: str = "NONE"
    overall_score: Decimal | None = None
    constituent_change_types: list[str] = Field(default_factory=list)
    evidence_bullets: list[str] = Field(default_factory=list)
    review_status: str = "surfaced"
    is_reviewed: bool = False
    reviewed_at: datetime | None = None


class HistoricalSeriesPoint(BaseModel):
    observation_id: int
    observed_at: datetime
    price: Decimal
    volume: int | None = None
    is_baseline: bool = False
    is_current: bool = False


class StockDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nse_symbol: str
    company_name: str
    exchange: str = "NSE"
    isin: str | None = None
    sector: str | None = None

    current_observation: CurrentObservationDetail
    since_last_checked: SinceLastCheckedDetail
    evidence: EvidenceDetail | None = None
    market_context: MarketContextDetail
    timeline: list[TimelineEpisode] = Field(default_factory=list)
    historical_series: list[HistoricalSeriesPoint] = Field(default_factory=list)
    freshness_note: str = ""
    source: str = "NSE"
    data_status: str = "HISTORICAL"
