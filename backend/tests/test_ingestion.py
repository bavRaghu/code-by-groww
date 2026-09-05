from pathlib import Path
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.service import IngestionService
from app.models.market_observation import MarketObservation
from app.providers.nse import NSEHistoricalProvider

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.asyncio
async def test_nse_provider_parse_valid_fixture():
    provider = NSEHistoricalProvider()
    valid_file = FIXTURES_DIR / "bhavcopy_valid.csv"
    res = provider.parse_file(valid_file)

    assert res.total_rows == 7
    assert len(res.observations) == 7
    assert len(res.errors) == 0

    symbols = [o.symbol for o in res.observations]
    assert "TCS" in symbols
    assert "RELIANCE" in symbols
    assert "INFY" in symbols
    assert "UNTRACKEDCO" in symbols

    # Check parsed fields for TCS
    tcs = next(o for o in res.observations if o.symbol == "TCS")
    assert tcs.price == 4225.00
    assert tcs.open == 4200.00
    assert tcs.high == 4250.00
    assert tcs.low == 4180.00
    assert tcs.close == 4220.00
    assert tcs.volume == 1250000
    assert tcs.source == "NSE"
    assert tcs.data_status == "final"


@pytest.mark.asyncio
async def test_ingest_service_persists_valid_observations_and_reports_unmatched(db_session: AsyncSession):
    provider = NSEHistoricalProvider()
    service = IngestionService(provider=provider)
    valid_file = FIXTURES_DIR / "bhavcopy_valid.csv"

    result = await service.ingest_file(db_session, valid_file)

    assert result.total_rows == 7
    assert result.parsed_observations == 7
    # 6 seed instruments matched, 1 untracked was reported
    assert result.persisted_observations == 6
    assert "UNTRACKEDCO" in result.unmatched_symbols
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_repeated_ingestion_is_idempotent(db_session: AsyncSession):
    provider = NSEHistoricalProvider()
    service = IngestionService(provider=provider)
    valid_file = FIXTURES_DIR / "bhavcopy_valid.csv"

    # Ingest first time
    res1 = await service.ingest_file(db_session, valid_file)
    count_before = await db_session.scalar(select(func.count(MarketObservation.id)))

    # Ingest second time
    res2 = await service.ingest_file(db_session, valid_file)
    count_after = await db_session.scalar(select(func.count(MarketObservation.id)))

    # No duplicate observations created
    assert count_before == count_after
    assert res2.persisted_observations == res1.persisted_observations


@pytest.mark.asyncio
async def test_ingestion_handles_malformed_and_missing_data(db_session: AsyncSession):
    provider = NSEHistoricalProvider()
    service = IngestionService(provider=provider)
    malformed_file = FIXTURES_DIR / "bhavcopy_malformed.csv"

    result = await service.ingest_file(db_session, malformed_file)

    assert result.total_rows == 4
    # Only 1 row is valid (HDFCBANK)
    assert result.parsed_observations == 1
    assert result.persisted_observations == 1
    # 3 errors recorded for the malformed rows
    assert len(result.errors) == 3
    assert any("Missing ticker symbol" in e for e in result.errors)
    assert any("Price must be positive" in e for e in result.errors)
    assert any("Invalid price" in e for e in result.errors)


@pytest.mark.asyncio
async def test_date_override_canonical_timestamp_and_idempotency(db_session: AsyncSession):
    from datetime import datetime, timezone, timedelta
    from app.models.instrument import Instrument

    provider = NSEHistoricalProvider()
    service = IngestionService(provider=provider)
    valid_file = FIXTURES_DIR / "bhavcopy_valid.csv"

    # Ingest without date override (uses TradDt: 2026-09-01)
    await service.ingest_file(db_session, valid_file)

    tcs_stmt = select(Instrument).where(Instrument.nse_symbol == "TCS")
    tcs = (await db_session.execute(tcs_stmt)).scalar_one()

    obs_stmt = select(MarketObservation).where(MarketObservation.instrument_id == tcs.id)
    tcs_obs = (await db_session.execute(obs_stmt)).scalars().all()
    assert len(tcs_obs) == 1
    # Canonical timestamp is 15:30 IST
    ist_offset = timezone(timedelta(hours=5, minutes=30))
    expected_dt = datetime(2026, 9, 1, 15, 30, 0, tzinfo=ist_offset)
    assert tcs_obs[0].observed_at == expected_dt

    count_before = await db_session.scalar(select(func.count(MarketObservation.id)))

    # Ingest same file with --date override (e.g. 2026-09-01 at 00:00)
    cli_override_date = datetime(2026, 9, 1, 0, 0, 0)
    await service.ingest_file(db_session, valid_file, date_override=cli_override_date)

    count_after = await db_session.scalar(select(func.count(MarketObservation.id)))
    # Must NOT create duplicate observation for the same trading day
    assert count_after == count_before

    tcs_obs_after = (await db_session.execute(obs_stmt)).scalars().all()
    assert len(tcs_obs_after) == 1
    assert tcs_obs_after[0].observed_at == expected_dt


@pytest.mark.asyncio
async def test_nse_series_filtering_ignores_non_eq_series(db_session: AsyncSession):
    provider = NSEHistoricalProvider()
    service = IngestionService(provider=provider)
    series_file = FIXTURES_DIR / "bhavcopy_series.csv"

    # Provider parse: only EQ series must be parsed
    parse_res = provider.parse_file(series_file)
    assert parse_res.total_rows == 3
    assert len(parse_res.observations) == 1
    obs = parse_res.observations[0]
    assert obs.symbol == "TCS"
    assert obs.price == 4225.00  # The EQ row price, not BE (4125.00) or SM (4025.00)

    # Ingestion persists only the EQ observation
    result = await service.ingest_file(db_session, series_file)
    assert result.parsed_observations == 1
    assert result.persisted_observations == 1
