from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NewsArticleData:
    provider_article_id: str
    headline: str
    source: str
    url: str
    published_at: datetime
    summary: str | None = None
    relevance_score: float | None = None
    match_score: float | None = None
    sentiment_score: float | None = None
    raw_data: dict[str, Any] | None = field(default_factory=dict)


class NewsProvider(ABC):
    provider_name: str = "unknown"

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the provider has valid credentials configured."""
        pass

    @abstractmethod
    async def fetch_news_for_instrument(
        self,
        symbol: str,
        company_name: str,
        published_after: datetime | None = None,
        published_before: datetime | None = None,
        limit: int = 10,
    ) -> list[NewsArticleData]:
        """Fetch raw candidate articles for an instrument."""
        pass
