import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.providers.base import MarketDataProvider, NormalizedObservation

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
    supports security master population, reports unmatched symbols,
    and guarantees idempotent persistence.
    """

    def __init__(self, provider: MarketDataProvider | None = None):
        if provider is None:
            from app.providers.nse import NSEHistoricalProvider
            provider = NSEHistoricalProvider()
        self.provider = provider

    async def import_instruments(
        self,
        session: AsyncSession,
        instruments: list[dict[str, Any]],
    ) -> int:
        """
        Imports or updates instruments idempotently from a list of instrument dicts.
        Returns count of instruments processed.
        """
        if not instruments:
            return 0

        created_or_updated = 0
        for inst_data in instruments:
            sym = (inst_data.get("nse_symbol") or "").strip().upper()
            if not sym:
                continue

            cname = (inst_data.get("company_name") or "").strip() or f"{sym} Limited"
            isin = inst_data.get("isin")
            exchange = inst_data.get("exchange") or "NSE"

            stmt = (
                pg_insert(Instrument)
                .values(
                    nse_symbol=sym,
                    company_name=cname,
                    isin=isin,
                    exchange=exchange,
                )
                .on_conflict_do_update(
                    index_elements=["nse_symbol"],
                    set_={
                        "company_name": func.coalesce(Instrument.company_name, cname),
                        "isin": func.coalesce(Instrument.isin, isin),
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
            )
            await session.execute(stmt)
            created_or_updated += 1

        await session.commit()
        return created_or_updated

    async def sync_provider_instruments(self, session: AsyncSession) -> int:
        """
        Fetches all available instruments from the provider and imports them.
        """
        available = self.provider.get_available_instruments()
        return await self.import_instruments(session, available)

    async def ingest_observations(
        self,
        session: AsyncSession,
        observations: list[NormalizedObservation],
        auto_create_instruments: bool = False,
    ) -> IngestionResult:
        """
        Persists a list of NormalizedObservation objects idempotently.
        """
        # Preload known instruments into symbol -> instrument_id map
        stmt = select(Instrument.id, Instrument.nse_symbol)
        result = await session.execute(stmt)
        symbol_map = {row.nse_symbol.upper(): row.id for row in result.all()}

        unmatched: set[str] = set()
        persisted_count = 0

        for obs in observations:
            sym = obs.symbol.upper()
            inst_id = symbol_map.get(sym)

            if not inst_id:
                if auto_create_instruments:
                    # Auto-create missing instrument
                    cname = obs.company_name or getattr(self.provider, "lookup_company_name", lambda s: f"{s} Limited")(sym)
                    inst_stmt = (
                        pg_insert(Instrument)
                        .values(
                            nse_symbol=sym,
                            company_name=cname,
                            isin=obs.isin,
                            exchange="NSE",
                        )
                        .on_conflict_do_update(
                            index_elements=["nse_symbol"],
                            set_={
                                "isin": func.coalesce(Instrument.isin, obs.isin),
                                "updated_at": datetime.now(timezone.utc),
                            },
                        )
                        .returning(Instrument.id)
                    )
                    inst_res = await session.execute(inst_stmt)
                    inst_id = inst_res.scalar_one()
                    symbol_map[sym] = inst_id
                else:
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
            total_rows=len(observations),
            parsed_observations=len(observations),
            persisted_observations=persisted_count,
            unmatched_symbols=sorted(unmatched),
            errors=[],
        )

    async def ingest_file(
        self,
        session: AsyncSession,
        file_path: str | Path,
        date_override: datetime | None = None,
        auto_create_instruments: bool = False,
    ) -> IngestionResult:
        parse_result = self.provider.parse_file(file_path, date_override=date_override)
        if parse_result.errors and not parse_result.observations:
            return IngestionResult(
                total_rows=parse_result.total_rows,
                parsed_observations=0,
                persisted_observations=0,
                unmatched_symbols=[],
                errors=parse_result.errors,
            )

        ingest_res = await self.ingest_observations(
            session=session,
            observations=parse_result.observations,
            auto_create_instruments=auto_create_instruments,
        )

        return IngestionResult(
            total_rows=parse_result.total_rows,
            parsed_observations=len(parse_result.observations),
            persisted_observations=ingest_res.persisted_observations,
            unmatched_symbols=ingest_res.unmatched_symbols,
            errors=parse_result.errors,
        )


async def import_instruments(
    session: AsyncSession,
    instruments: list[dict[str, Any]],
) -> int:
    service = IngestionService()
    return await service.import_instruments(session, instruments)


async def sync_provider_instruments(
    session: AsyncSession,
    provider: MarketDataProvider | None = None,
) -> dict[str, int]:
    service = IngestionService(provider=provider)
    prev_count_stmt = select(func.count(Instrument.id))
    prev_count = (await session.execute(prev_count_stmt)).scalar() or 0
    await service.sync_provider_instruments(session)
    new_count = (await session.execute(prev_count_stmt)).scalar() or 0
    return {"instruments_created": max(0, new_count - prev_count)}
