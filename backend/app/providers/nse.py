import csv
import logging
from datetime import datetime, time, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.providers.base import MarketDataProvider, NormalizedObservation, ParseResult

logger = logging.getLogger(__name__)

# Indian Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))
NSE_MARKET_CLOSE_TIME = time(15, 30, 0)


class NSEHistoricalProvider(MarketDataProvider):
    """
    Consumes NSE Capital Market UDiFF (Unified Distributable File Format) Common Bhavcopy.
    Normalizes NSE-specific data structures into internal NormalizedObservation objects.
    """

    # CM-UDiFF required and expected column names
    COL_SYMBOL = "TckrSymb"
    COL_SERIES = "SctySrs"
    COL_TRADE_DATE = "TradDt"
    COL_OPEN = "OpnPric"
    COL_HIGH = "HghPric"
    COL_LOW = "LwPric"
    COL_CLOSE = "ClsPric"
    COL_LAST = "LastPric"
    COL_VOLUME = "TtlTradgVol"
    COL_SOURCE = "Src"

    REQUIRED_COLUMNS = {COL_SYMBOL, COL_TRADE_DATE, COL_LAST, COL_CLOSE}

    def parse_file(
        self,
        file_path: str | Path,
        date_override: datetime | None = None,
    ) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"NSE bhavcopy file not found at: {path}")

        observations: list[NormalizedObservation] = []
        errors: list[str] = []
        total_rows = 0

        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                errors.append("File contains no header row or is empty.")
                return ParseResult(observations=[], errors=errors, total_rows=0)

            # Strip whitespace from fieldnames
            stripped_fields = {col.strip() for col in reader.fieldnames if col}
            missing_cols = self.REQUIRED_COLUMNS - stripped_fields
            if missing_cols:
                err_msg = f"Missing required CM-UDiFF columns: {sorted(missing_cols)}"
                errors.append(err_msg)
                logger.error(err_msg)
                return ParseResult(observations=[], errors=errors, total_rows=0)

            for line_no, raw_row in enumerate(reader, start=2):
                total_rows += 1
                row = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items() if k}

                # Filter series if present: standard equity series is 'EQ'
                series = row.get(self.COL_SERIES, "")
                if series and series.upper() not in {"EQ", "BE", "SM", "ST"}:
                    continue

                symbol = row.get(self.COL_SYMBOL, "").upper()
                if not symbol:
                    errors.append(f"Line {line_no}: Missing ticker symbol.")
                    continue

                # Parse prices
                last_price_raw = row.get(self.COL_LAST) or row.get(self.COL_CLOSE)
                if not last_price_raw:
                    errors.append(f"Line {line_no} ({symbol}): Missing last/close price.")
                    continue

                try:
                    price = Decimal(last_price_raw)
                    if price <= 0:
                        errors.append(f"Line {line_no} ({symbol}): Price must be positive, got {price}.")
                        continue
                except InvalidOperation:
                    errors.append(f"Line {line_no} ({symbol}): Invalid price '{last_price_raw}'.")
                    continue

                open_price = self._parse_optional_decimal(row.get(self.COL_OPEN))
                high_price = self._parse_optional_decimal(row.get(self.COL_HIGH))
                low_price = self._parse_optional_decimal(row.get(self.COL_LOW))
                close_price = self._parse_optional_decimal(row.get(self.COL_CLOSE)) or price

                # Parse volume
                volume_raw = row.get(self.COL_VOLUME)
                volume: int | None = None
                if volume_raw:
                    try:
                        volume = int(float(volume_raw))
                    except ValueError:
                        errors.append(f"Line {line_no} ({symbol}): Invalid volume '{volume_raw}'.")

                # Parse observation timestamp
                observed_at: datetime
                if date_override is not None:
                    observed_at = date_override if date_override.tzinfo else date_override.replace(tzinfo=IST)
                else:
                    date_str = row.get(self.COL_TRADE_DATE, "")
                    try:
                        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        observed_at = datetime.combine(parsed_date, NSE_MARKET_CLOSE_TIME, tzinfo=IST)
                    except ValueError:
                        errors.append(f"Line {line_no} ({symbol}): Invalid date format '{date_str}', expected YYYY-MM-DD.")
                        continue

                observations.append(
                    NormalizedObservation(
                        symbol=symbol,
                        price=price,
                        open=open_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=volume,
                        observed_at=observed_at,
                        source="NSE",
                        data_status="final",
                    )
                )

        return ParseResult(
            observations=observations,
            errors=errors,
            total_rows=total_rows,
        )

    @staticmethod
    def _parse_optional_decimal(val: str | None) -> Decimal | None:
        if not val:
            return None
        try:
            return Decimal(val)
        except InvalidOperation:
            return None
