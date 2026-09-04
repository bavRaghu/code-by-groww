from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class NormalizedObservation:
    symbol: str
    price: Decimal
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: int | None
    observed_at: datetime
    source: str
    data_status: str


@dataclass
class ParseResult:
    observations: list[NormalizedObservation]
    errors: list[str]
    total_rows: int


class MarketDataProvider(ABC):
    """
    Abstract interface for market-data providers.
    Shields the rest of the application from vendor-specific file formats,
    APIs, and naming conventions.
    """

    @abstractmethod
    def parse_file(
        self,
        file_path: str | Path,
        date_override: datetime | None = None,
    ) -> ParseResult:
        """
        Parses a market-data file into normalized market observations.
        """
        raise NotImplementedError
