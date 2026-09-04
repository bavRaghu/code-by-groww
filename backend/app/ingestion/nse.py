import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from app.db.session import AsyncSessionLocal
from app.ingestion.service import IngestionService
from app.providers.nse import NSEHistoricalProvider

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def run_ingestion(file_path: str, date_str: str | None = None) -> None:
    path = Path(file_path)
    if not path.exists():
        logger.error("File does not exist: %s", file_path)
        sys.exit(1)

    date_override = None
    if date_str:
        try:
            date_override = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            logger.error("Invalid date format '%s'. Use YYYY-MM-DD.", date_str)
            sys.exit(1)

    provider = NSEHistoricalProvider()
    service = IngestionService(provider=provider)

    async with AsyncSessionLocal() as session:
        result = await service.ingest_file(
            session=session,
            file_path=path,
            date_override=date_override,
        )

    logger.info("Ingestion completed:")
    logger.info("  Total rows in file: %d", result.total_rows)
    logger.info("  Parsed observations: %d", result.parsed_observations)
    logger.info("  Persisted observations: %d", result.persisted_observations)
    if result.unmatched_symbols:
        logger.info("  Unmatched symbols (%d): %s", len(result.unmatched_symbols), result.unmatched_symbols[:10])
    if result.errors:
        logger.warning("  Errors/warnings (%d): %s", len(result.errors), result.errors[:5])


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NSE CM-UDiFF Bhavcopy market data.")
    parser.add_argument("--file", "-f", required=True, help="Path to the Bhavcopy CSV file")
    parser.add_argument("--date", "-d", required=False, help="Optional trade date override (YYYY-MM-DD)")

    args = parser.parse_args()
    asyncio.run(run_ingestion(file_path=args.file, date_str=args.date))


if __name__ == "__main__":
    main()
