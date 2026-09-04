import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    total_rows: int
    parsed_observations: int
    persisted_observations: int
    unmatched_symbols: list[str]
    errors: list[str]


class IngestionService:
    """
    Coordinates ingestion from any MarketDataProvider into PostgreSQL.
    Maintains relational integrity, resolves symbols to Instruments,
    reports unmatched symbols, and guarantees idempotent persistence.
    """

    def __init__(self, provider: MarketDataProvider):
        self.provider = provider

    async def ingest_file(
        self,
        session: AsyncSession,
        file_path: str | Path,
        date_override: datetime | None = None,
    ) -> IngestionResult:
        parse_result = self.provider.parse_file(file_path, date_override=date_override)

        # Preload known instruments into symbol -> instrument_id map
        stmt = select(Instrument.id, Instrument.nse_symbol)
        result = await session.execute(stmt)
        symbol_map = {row.nse_symbol.upper(): row.id for row in result.all()}

        unmatched: set[str] = set()
        persisted_count = 0

        for obs in parse_result.observations:
            inst_id = symbol_map.get(obs.symbol.upper())
            if not inst_id:
                unmatched.add(obs.symbol)
                continue

            insert_stmt = (
                pg_insert(MarketObservation)
                .values(
                    instrument_id=inst_id,
                    price=obs.price,
                    open=obs.open,
                    high=obs.high,
                    low=obs.low,
                    close=obs.close,
                    volume=obs.volume,
                    observed_at=obs.observed_at,
                    received_at=datetime.now(timezone.utc),
                    source=obs.source,
                    data_status=obs.data_status,
                )
                .on_conflict_do_update(
                    constraint="uq_market_obs_instrument_observed_source",
                    set_={
                        "price": obs.price,
                        "open": obs.open,
                        "high": obs.high,
                        "low": obs.low,
                        "close": obs.close,
                        "volume": obs.volume,
                        "received_at": datetime.now(timezone.utc),
                        "data_status": obs.data_status,
                    },
                )
            )
            await session.execute(insert_stmt)
            persisted_count += 1

        await session.commit()

        if unmatched:
            logger.warning("Ingestion found %d unmatched symbols: %s", len(unmatched), sorted(unmatched))

        return IngestionResult(
            total_rows=parse_result.total_rows,
            parsed_observations=len(parse_result.observations),
            persisted_observations=persisted_count,
            unmatched_symbols=sorted(unmatched),
            errors=parse_result.errors,
        )
