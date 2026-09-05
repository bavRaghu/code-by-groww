from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class RelevantNewsItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    provider_article_id: str
    headline: str
    source: str
    url: str
    published_at: datetime
    summary: str | None = None
    relevance_score: float | None = None
    match_score: float | None = None
    sentiment_score: float | None = None
    temporal_relation: str = "Published around the time of the detected move"
    relevance_summary: str = ""


class RelevantNewsContext(BaseModel):
    status: str = "available"  # "available" | "none_found" | "unavailable"
    disclaimer: str = "Potentially relevant news around this move. News context does not imply causality."
    articles: list[RelevantNewsItem] = Field(default_factory=list)
    note: str = ""
