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
    isin: str | None = None
    company_name: str | None = None


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

    def get_available_sessions(self) -> list[datetime]:
        """
        Returns chronologically sorted list of session timestamps available from this provider.
        """
        return []

    def get_available_instruments(self) -> list[dict[str, str | None]]:
        """
        Returns the list of instruments (nse_symbol, company_name, isin, exchange) available from this provider.
        """
        return []

    def get_observations_for_session(
        self, session_time: datetime
    ) -> list[NormalizedObservation]:
        """
        Returns normalized observations for the given session date/time.
        """
        return []
