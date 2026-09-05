# Smart Market Watchlist

> **Code, by Groww 2026** – Engineering Challenge Submission (Milestone 1: Core Foundation)

A market watchlist application designed to help users understand what has meaningfully changed in the stocks they follow since they last checked.

---

## 1. Project Overview

Traditional market watchlists flood users with every price fluctuation and continuous noise. The **Smart Market Watchlist** serves as an attention filter:

$$\text{Watch} \longrightarrow \text{Leave} \longrightarrow \text{Market changes} \longrightarrow \text{Return} \longrightarrow \text{Understand what changed}$$

This milestone establishes the **core foundation end-to-end**:
- **User & Watchlist domain models** with relational integrity and uniqueness constraints.
- **Authoritative instruments catalog** seeded with key NSE equities.
- **Market Data Provider Abstraction** isolating vendor-specific file formats from core domain logic.
- **NSE CM-UDiFF Common Bhavcopy Ingestion Engine** supporting local file inputs, validation, and idempotent upserts.
- **FastAPI REST API** supporting watchlist CRUD, item reordering, instrument search, and market observation retrieval with price change calculations.
- **React + Vite Frontend** allowing interactive watchlist creation, instrument addition/removal, and market data visualization.
- **Comprehensive automated test suite** covering DB constraints, migrations, seed idempotency, ingestion validation, and API contracts.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│              React Frontend (Vite + JS)                 │
│  - Watchlist management (tabs, create, delete)          │
│  - Stock search & addition/removal                      │
│  - Market data table with price & percentage changes    │
└────────────────────────────┬────────────────────────────┘
                             │  REST / JSON
                             ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Backend                      │
│  - /api/v1/health                                       │
│  - /api/v1/instruments (search & listing)               │
│  - /api/v1/watchlists (CRUD, membership, reordering)   │
│  - /api/v1/watchlists/{id}/market (price calculations)  │
└──────────────┬───────────────────────────┬──────────────┘
               │                           │
               ▼                           ▼
┌──────────────────────────────┐  ┌───────────────────────────────────┐
│      Persistence Layer       │  │      Market Data Abstraction      │
│  SQLAlchemy 2.0 (Async)      │  │                                   │
│  Alembic Migrations          │  │  MarketDataProvider (Interface)   │
│  PostgreSQL 16               │  │    ├── NSEHistoricalProvider       │
│  - users                     │  │    │   (CM-UDiFF Common Bhavcopy)  │
│  - instruments               │  │    └── INDstocksProvider (future)  │
│  - watchlists                │  └───────────────────────────────────┘
│  - watchlist_items           │
│  - market_observations      │
└──────────────────────────────┘
```

---

## 3. Database Entities

1. **`User` (`users`)**
   - `id`: Integer primary key (Deterministic dev user `id=1`).
   - `created_at`, `updated_at`: UTC timestamps.
   - Relationship: `1 → N` with `Watchlist` (cascade delete).

2. **`Instrument` (`instruments`)**
   - `id`: Integer primary key.
   - `nse_symbol`: String, **unique constraint**, indexed.
   - `company_name`: String, required.
   - `exchange`: Default `"NSE"`.
   - `isin`, `bse_code`, `sector`: Nullable metadata (never fabricated).
   - `created_at`, `updated_at`: UTC timestamps.

3. **`Watchlist` (`watchlists`)**
   - `id`: Integer primary key.
   - `user_id`: Foreign key to `users.id` (cascade delete).
   - `name`: String(100).
   - `created_at`, `updated_at`: UTC timestamps.
   - Relationship: `1 → N` with `WatchlistItem`.

4. **`WatchlistItem` (`watchlist_items`)**
   - `id`: Integer primary key.
   - `watchlist_id`: Foreign key to `watchlists.id` (cascade delete).
   - `instrument_id`: Foreign key to `instruments.id` (cascade delete).
   - `position`: Integer (order sequence within watchlist).
   - `added_at`: UTC timestamp.
   - Constraint: `UNIQUE(watchlist_id, instrument_id)` ensures no duplicates.

5. **`MarketObservation` (`market_observations`)**
   - `id`: Integer primary key.
   - `instrument_id`: Foreign key to `instruments.id` (cascade delete).
   - `price`: Decimal/Numeric(14, 4), required.
   - `open`, `high`, `low`, `close`: Decimal/Numeric(14, 4), nullable.
   - `volume`: BigInteger, nullable.
   - `observed_at`: Timezone-aware UTC timestamp.
   - `received_at`: Timezone-aware UTC timestamp.
   - `source`: String(50), e.g. `"NSE"`.
   - `data_status`: String(20), e.g. `"final"`.
   - Indexes & Constraints:
     - Composite index `(instrument_id, observed_at)`.
     - Unique constraint `UNIQUE(instrument_id, observed_at, source)` ensures persistence is completely idempotent.

---

## 4. Market Data Architecture & Provider Boundary

Market data ingestion is strictly isolated behind the `MarketDataProvider` abstract base class:

```python
class MarketDataProvider(ABC):
    @abstractmethod
    def parse_file(self, file_path: str | Path, date_override: datetime | None = None) -> ParseResult:
        ...
```

- **`NSEHistoricalProvider`**:
  - Ingests the current NSE **CM-UDiFF (Capital Market Unified Distributable File Format) Common Bhavcopy Final** CSV format.
  - Required columns parsed: `TckrSymb`, `SctySrs`, `TradDt`, `OpnPric`, `HghPric`, `LwPric`, `ClsPric`, `LastPric`, `TtlTradgVol`, `Src`.
  - Normalizes external columns into internal `NormalizedObservation` representations.
  - NSE-specific column names and quirks remain strictly inside the provider package.
- **Future-Proof**:
  - Future providers (e.g. `INDstocksProvider`, Twelve Data) implement `MarketDataProvider` without touching the application or database layer.

---

## 5. Local Setup & Commands

### Prerequisites

- **Python** ≥ 3.11
- **Node.js** ≥ 18 and **npm** ≥ 9
- **Docker** & **Docker Compose**

---

### Step 1: Start PostgreSQL

```bash
docker compose up -d
```

*(Note: Port mapping is configurable via `POSTGRES_PORT` in `.env`. Default is `5432` or `5433` if port 5432 is in use by a local service).*

---

### Step 2: Run Alembic Migrations

From the repository root (or inside `backend`):

```bash
# Windows PowerShell
.\backend\.venv\Scripts\alembic.exe upgrade head

# Linux / macOS
alembic upgrade head
```

---

### Step 3: Seed Development Data

Seed the deterministic development user (`id=1`) and authoritative instruments (`TCS`, `RELIANCE`, `INFY`, `HDFCBANK`, `SBIN`, `ICICIBANK`):

```bash
# Windows PowerShell
$env:PYTHONPATH="backend"; .\backend\.venv\Scripts\python.exe -m app.seed

# Linux / macOS
PYTHONPATH=backend python -m app.seed
```

*(This command is 100% idempotent and can be safely executed repeatedly without creating duplicates).*

---

### Step 4: Run NSE Bhavcopy Ingestion

Ingest a realistic CM-UDiFF Bhavcopy file using the CLI tool:

```bash
# Ingest Day 1 observations
$env:PYTHONPATH="backend"; .\backend\.venv\Scripts\python.exe -m app.ingestion.nse --file data/nse_bhavcopy_2026-09-01.csv

# Ingest Day 2 observations (demonstrates price change calculations)
$env:PYTHONPATH="backend"; .\backend\.venv\Scripts\python.exe -m app.ingestion.nse --file data/nse_bhavcopy_2026-09-02.csv
```

Features:
- Resolves ticker symbols against existing database `Instrument` records.
- Safely reports unmatched symbols (e.g. `UNTRACKEDCO`) without aborting or corrupting data.
- Handles missing or malformed numeric rows gracefully.
- Idempotent: repeated runs update observations via database constraint `ON CONFLICT DO UPDATE`.

---

### Step 5: Start Backend Server

```bash
cd backend
..\backend\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

- API Base: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/v1/health`

---

### Step 6: Start Frontend Application

```bash
cd frontend
npm install
npm run dev
```

- Web UI: `http://localhost:5173`

---

### Step 7: Run Automated Tests

Run the complete test suite against the live PostgreSQL test database:

```bash
.\backend\.venv\Scripts\pytest.exe backend/tests -v
```

All 20 tests verify:
- Database relational cascading and uniqueness constraints
- Seeding idempotency and required instruments
- Instrument search by symbol and company name
- Watchlist CRUD, membership, reordering, and constraint validation
- NSE CM-UDiFF parsing, malformed row handling, and idempotent upserts
- Market data API price and percentage change calculations

---

## 6. Marketaux News Integration (Milestone 7)

Marketaux is integrated as an **isolated supporting context layer** for detected market changes. It is **not** a generic news feed, **not** an investment advisor, and **never** influences or replaces the quantitative significance scoring pipeline.

### Architectural Principles

```
MarketObservation
      ↓
DetectedChange
      ↓
SignificanceAssessment (Pure Quantitative Scoring)
      ↓
Attention Feed / Stock Detail
      ↓
Supporting News Context (MarketauxNewsProvider — Supplementary Context Only)
```

1. **Strict Non-Causal Wording**:
   The system displays: *"Potentially relevant news around this move"* and explains proximity (*"Published during the observation window"*, *"Published within hours of the detected move"*). It never claims or implies that news "caused" the price movement.
2. **Relevance Ranking & Limits**:
   - Ranked deterministically based on entity match (`match_score` from Marketaux), direct ticker symbol / company name presence, publication recency, and temporal proximity to the detected move.
   - Temporal window: Constrained to news published within 72 hours before the change up to 24 hours after the change.
   - Capped at a maximum of **3** qualifying articles.
   - When no qualifying articles exist, displays: *"No relevant news found around this change."*
3. **Resilience & Graceful Degradation**:
   - News retrieval failures (HTTP 401, 429 rate limit, 5xx server error, network timeout) are caught safely.
   - Market observations, change detection, significance scoring, and the attention feed operate with 100% reliability regardless of news availability.
4. **Token Security**:
   - `MARKETAUX_API_TOKEN` is strictly backend-only.
   - Never logged (HTTP request logger filters out query params and token strings).
   - Never exposed in frontend bundles or API responses.
   - Untrusted third-party article titles and summaries are rendered safely without raw HTML injection.
5. **Idempotent Persistence**:
   - Articles are cached in the PostgreSQL `news_articles` table with a composite constraint `UNIQUE(provider, provider_article_id, instrument_id)`.
   - Repeated queries for the same move query the local database first, minimizing external API calls and rate-limiting.

### Configuration

Add `MARKETAUX_API_TOKEN` to your backend `.env` file or environment variables:

```bash
# In backend/.env
MARKETAUX_API_TOKEN=your_api_token_here
MARKETAUX_BASE_URL=https://api.marketaux.com/v1
MARKETAUX_TIMEOUT_SECONDS=10.0
```

*(If `MARKETAUX_API_TOKEN` is unset or empty, the application runs seamlessly in degraded mode, providing full attention and significance intelligence without external news calls).*

---

## 7. Running Tests

Run the complete 103-test suite across all milestones:

```bash
.\backend\.venv\Scripts\pytest.exe backend/tests -v
```

Test coverage:
- `test_milestone7_marketaux_news.py`: Marketaux response normalization, missing token handling, timeout/5xx resilience, 429 rate limit / 401 handling, idempotent persistence, instrument association, relevance ranking (top 3 limit), temporal proximity, fallback state, unchanged significance calculation, and token security.
- `test_milestone6_stock_detail.py`: Stock detail contract, "since last checked" state, evidence breakdown, change timeline, benchmark context.
- `test_milestone5_attention_feed.py`: Attention feed summaries, signal episodes, ranking, review state persistence, and audit log.
- `test_milestone4_market_freshness.py`: Dynamic instrument discovery, bhavcopy ingestion, multi-session baseline progression.
- Foundation tests (`test_watchlists.py`, `test_user_observation.py`, `test_significance_scoring.py`, `test_ingestion.py`, `test_instruments.py`, `test_seed.py`).

---

## 8. Known Limitations & Follow-ups

- **External Free Tier Quotas**: Marketaux free-tier tokens have daily request limits. The local PostgreSQL news cache and 72-hour windowing mitigate repeated hits, but high-volume watchlists may encounter 429s (handled gracefully by the fallback state).
- **Historical Backfill**: Real-time bhavcopy files represent historical dates; if historical news beyond the provider's free-tier archive window is queried, Marketaux may return empty results, correctly triggering the *"No relevant news found around this change"* fallback.
