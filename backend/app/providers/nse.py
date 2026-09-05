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

WELL_KNOWN_COMPANIES: dict[str, str] = {
    "TCS": "Tata Consultancy Services Limited",
    "RELIANCE": "Reliance Industries Limited",
    "INFY": "Infosys Limited",
    "HDFCBANK": "HDFC Bank Limited",
    "SBIN": "State Bank of India",
    "ICICIBANK": "ICICI Bank Limited",
    "TATAMOTORS": "Tata Motors Limited",
    "BHARTIARTL": "Bharti Airtel Limited",
    "ITC": "ITC Limited",
    "KOTAKBANK": "Kotak Mahindra Bank Limited",
    "LT": "Larsen & Toubro Limited",
    "HINDUNILVR": "Hindustan Unilever Limited",
    "AXISBANK": "Axis Bank Limited",
    "BAJFINANCE": "Bajaj Finance Limited",
    "MARUTI": "Maruti Suzuki India Limited",
    "ASIANPAINT": "Asian Paints Limited",
    "TITAN": "Titan Company Limited",
    "SUNPHARMA": "Sun Pharmaceutical Industries Limited",
    "WIPRO": "Wipro Limited",
    "ULTRACEMCO": "UltraTech Cement Limited",
    "NTPC": "NTPC Limited",
    "ONGC": "Oil and Natural Gas Corporation Limited",
    "POWERGRID": "Power Grid Corporation of India Limited",
    "COALINDIA": "Coal India Limited",
    "TATASTEEL": "Tata Steel Limited",
    "M&M": "Mahindra & Mahindra Limited",
    "ADANIENT": "Adani Enterprises Limited",
    "BAJAJFINSV": "Bajaj Finserv Limited",
    "HCLTECH": "HCL Technologies Limited",
    "UNTRACKEDCO": "Untracked Company Limited",
}


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
    COL_ISIN = "ISIN"

    REQUIRED_COLUMNS = {COL_SYMBOL, COL_TRADE_DATE, COL_LAST, COL_CLOSE}

    def __init__(self, data_dir: str | Path | None = None) -> None:
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        else:
            local_data = Path("data")
            if local_data.is_dir():
                self.data_dir = local_data
            else:
                # Resolve relative to project root from backend/app/providers/nse.py
                self.data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data"

    @classmethod
    def lookup_company_name(cls, symbol: str) -> str:
        sym = symbol.upper()
        if sym in WELL_KNOWN_COMPANIES:
            return WELL_KNOWN_COMPANIES[sym]
        return f"{sym} Limited"

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

                # Filter series: restrict to standard equity series 'EQ'
                series = row.get(self.COL_SERIES, "").strip().upper()
                if self.COL_SERIES in row and series != "EQ":
                    continue

                symbol = row.get(self.COL_SYMBOL, "").upper()
                if not symbol:
                    errors.append(f"Line {line_no}: Missing ticker symbol.")
                    continue

                isin = row.get(self.COL_ISIN) or None

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

                # Parse observation timestamp (canonical market close 15:30 IST)
                observed_at: datetime
                if date_override is not None:
                    override_date = date_override.date() if isinstance(date_override, datetime) else date_override
                    observed_at = datetime.combine(override_date, NSE_MARKET_CLOSE_TIME, tzinfo=IST)
                else:
                    date_str = row.get(self.COL_TRADE_DATE, "")
                    try:
                        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        observed_at = datetime.combine(parsed_date, NSE_MARKET_CLOSE_TIME, tzinfo=IST)
                    except ValueError:
                        errors.append(f"Line {line_no} ({symbol}): Invalid date format '{date_str}', expected YYYY-MM-DD.")
                        continue

                company_name = self.lookup_company_name(symbol)

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
                        isin=isin,
                        company_name=company_name,
                    )
                )

        return ParseResult(
            observations=observations,
            errors=errors,
            total_rows=total_rows,
        )

    def get_available_sessions(self) -> list[datetime]:
        """
        Scans data directory for nse_bhavcopy_*.csv files and returns
        sorted list of session observation timestamps.
        """
        if not self.data_dir.is_dir():
            return []

        sessions: set[datetime] = set()
        for f in self.data_dir.glob("nse_bhavcopy_*.csv"):
            parts = f.stem.split("_")
            if len(parts) >= 3:
                date_str = parts[2]
                try:
                    d = datetime.strptime(date_str, "%Y-%m-%d").date()
                    dt = datetime.combine(d, NSE_MARKET_CLOSE_TIME, tzinfo=IST)
                    sessions.add(dt)
                except ValueError:
                    continue
        return sorted(sessions)

    def get_available_instruments(self) -> list[dict[str, str | None]]:
        """
        Extracts available equity instruments from nse_security_master.csv
        and available bhavcopies in the data directory.
        Strictly filters out non-EQ series.
        """
        instruments_by_symbol: dict[str, dict[str, str | None]] = {}

        # 1. Parse security master if present
        sec_master = self.data_dir / "nse_security_master.csv"
        if sec_master.is_file():
            with open(sec_master, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    series = (row.get("SctySrs") or "").strip().upper()
                    if series != "EQ":
                        continue
                    sym = (row.get("TckrSymb") or "").strip().upper()
                    if not sym:
                        continue
                    cname = (row.get("Company") or "").strip() or self.lookup_company_name(sym)
                    isin = (row.get("ISIN") or "").strip() or None
                    instruments_by_symbol[sym] = {
                        "nse_symbol": sym,
                        "company_name": cname,
                        "isin": isin,
                        "exchange": "NSE",
                    }

        # 2. Augment with any EQ stocks from bhavcopies
        if self.data_dir.is_dir():
            for f in sorted(self.data_dir.glob("nse_bhavcopy_*.csv")):
                try:
                    parse_res = self.parse_file(f)
                    for obs in parse_res.observations:
                        if obs.symbol not in instruments_by_symbol:
                            instruments_by_symbol[obs.symbol] = {
                                "nse_symbol": obs.symbol,
                                "company_name": obs.company_name or self.lookup_company_name(obs.symbol),
                                "isin": obs.isin,
                                "exchange": "NSE",
                            }
                except Exception as e:
                    logger.warning("Could not parse %s for instruments: %s", f, e)

        return sorted(instruments_by_symbol.values(), key=lambda x: x["nse_symbol"])

    def get_observations_for_session(
        self, session_time: datetime
    ) -> list[NormalizedObservation]:
        """
        Returns normalized observations for the given session date/time.
        """
        date_str = session_time.strftime("%Y-%m-%d")
        bhav_file = self.data_dir / f"nse_bhavcopy_{date_str}.csv"
        if not bhav_file.is_file():
            return []
        res = self.parse_file(bhav_file)
        return res.observations

    @staticmethod
    def _parse_optional_decimal(val: str | None) -> Decimal | None:
        if not val:
            return None
        try:
            return Decimal(val)
        except InvalidOperation:
            return None
