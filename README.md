# BEACON — Smart Market Watchlist

> **"Know what deserves your attention."**
> 
> *Beacon turns your watchlist into an attention filter — surfacing meaningful changes, explaining why they matter, and showing the context around them.*

## Overview

Traditional financial watchlists primarily display static snapshots of current prices and arbitrary percentage movements. Users returning to their watchlists are forced to scan rows of raw numbers to determine whether any change is meaningful.

**Beacon** serves as an attention filter built around a concrete user lifecycle:

```
Watch -> Leave -> Market changes -> Return -> Understand what changed -> Investigate
```

The system evaluates changes relative to each user's personalized, historical observation point rather than an arbitrary rolling window. Surfaced changes are evaluated across multiple quantitative evidence dimensions to answer:

> "What changed, and how much attention does this change deserve based on the evidence available?"

This application is an information and attention-prioritization tool. It is not an automated trading system, stock prediction engine, or investment advisory service.

## Key Features

- Multi-watchlist management: Create, rename, reorder, and delete isolated watchlists.
- NSE instrument discovery: Search authoritative National Stock Exchange equity instruments by symbol or company name.
- Market data ingestion: Automated ingestion of standardized NSE CM-UDiFF Common Bhavcopy end-of-day observations with full idempotency.
- Persistent user observation state: Explicit tracking of each user's last-checked observation point across distinct user sessions.
- Candidate change detection: Compares the current market state against the user's specific baseline without advancing the baseline prematurely.
- Multi-component significance scoring: Transparent evaluation combining magnitude, historical abnormality (z-score/percentile), relative performance against benchmark (NIFTY 50), volume surge, and corporate actions.
- Deterministic attention ranking: Surfaces High, Medium, and Low attention items while filtering out sub-threshold market noise.
- Non-causal structured explanations: Plain-language, evidence-based descriptions stating what was observed without asserting unproven causality.
- Stock detail and change timeline: Comprehensive view featuring "since you last checked" delta, component evidence breakdown, chronological change episodes, and historical charts.
- Relevant Marketaux news context: Bounded supplementary context showing up to 3 temporally relevant news articles for surfaced moves without influencing quantitative scoring.
- Change review tracking: Audit log allowing users to mark changes as reviewed individually, by instrument, or watchlist-wide.
- Secure authentication and authorization: Scrypt password hashing, stateless HS256 JWT tokens, and strict per-user database query scoping preventing cross-user access.

## Architecture

The system follows a strict layered architecture that decouples external raw vendor data, derived analytical intelligence, and user-specific state:

```mermaid
flowchart TD
    subgraph ExternalSources["External Data Sources"]
        NSE["NSE CM-UDiFF Bhavcopy"]
        MarketauxAPI["Marketaux News API"]
    end

    subgraph ProviderLayer["Provider Abstraction Layer"]
        NSEProvider["NSEHistoricalProvider"]
        NewsProvider["MarketauxNewsProvider"]
    end

    subgraph NormalizedPersistence["Normalized Persistent Data"]
        Instruments["instruments"]
        Observations["market_observations"]
        News["news_articles"]
    end

    subgraph IntelligenceLayer["Derived Intelligence Layer"]
        ChangeDetection["Change Detection Engine"]
        Significance["Significance Scoring Engine"]
        AttentionFilter["Attention Prioritization"]
    end

    subgraph UserState["User State Layer"]
        Users["users"]
        Watchlists["watchlists & items"]
        UserObs["user_observations (Baseline)"]
        Reviews["change_reviews"]
    end

    subgraph APILayer["FastAPI Backend (Port 8000)"]
        AuthRouter["/api/v1/auth"]
        WatchlistsRouter["/api/v1/watchlists"]
        InstrumentsRouter["/api/v1/instruments"]
        MarketRouter["/api/v1/market"]
    end

    subgraph ClientLayer["React Frontend (Port 5173)"]
        UI["Vite + React SPA"]
    end

    NSE --> NSEProvider
    MarketauxAPI --> NewsProvider
    NSEProvider --> Observations
    NSEProvider --> Instruments
    NewsProvider --> News

    Observations --> ChangeDetection
    UserObs --> ChangeDetection
    ChangeDetection --> Significance
    Significance --> AttentionFilter

    AttentionFilter --> WatchlistsRouter
    Watchlists --> WatchlistsRouter
    Reviews --> WatchlistsRouter
    Users --> AuthRouter
    Instruments --> InstrumentsRouter
    Observations --> MarketRouter

    AuthRouter --> UI
    WatchlistsRouter --> UI
    InstrumentsRouter --> UI
    MarketRouter --> UI
```

### Distinction of Architectural Layers

1. Raw Data: Historical observations, traded volume, and news articles ingested via vendor-neutral providers.
2. Derived Intelligence: Candidate changes and significance assessment calculations computed deterministically from market observations.
3. User State: Personalized watchlist membership, baseline observation records (`user_observations`), and acknowledged change reviews (`change_reviews`).
4. API Layer: FastAPI REST interface handling authentication, parameter validation, and authorization boundaries.
5. Frontend: React single-page application built with Vite.

### Core Technology Stack

- Frontend: React 18, Vite, Plain CSS
- Backend: Python 3.12, FastAPI, Pydantic v2
- Database: PostgreSQL 16
- Persistence & Migrations: SQLAlchemy 2.0 (asyncpg), Alembic
- External Providers: NSE CM-UDiFF Bhavcopy, Marketaux REST API

## Intelligence Pipeline

The intelligence pipeline processes observations into prioritized attention cards:

```
MarketObservation -> DetectedChange -> SignificanceAssessment -> Attention Feed
```

### V1 Significance Model

Significance scoring evaluates an observed price move across 5 components. Each component is normalized to a value between `0.0` and `1.0`:

| Component | Weight | Description |
| :--- | :--- | :--- |
| Magnitude | 0.30 | Move size relative to instrument's historical absolute returns distribution. Uses empirical percentile rank when >= 3 historical observations exist; linear fallback otherwise. |
| Abnormality | 0.25 | Statistical deviation from mean return using historical z-score (`min(abs(z) / 3.0, 1.0)`). |
| Relative Performance | 0.20 | Excess return compared against market benchmark (NIFTY 50) over the same period. |
| Volume Surge | 0.15 | Current trading volume divided by trailing average volume. |
| Material Events | 0.10 | Corporate actions, earnings releases, or regulatory filings during the window. |

### Available Evidence Re-weighting

If certain components lack data (for example, missing volume or benchmark series), the pipeline does not penalize the stock. It normalizes weights across available components:

$$\text{Overall Score} = \frac{\sum_{i \in \text{Available}} (S_i \times W_i)}{\sum_{i \in \text{Available}} W_i}$$

### Attention Levels

- High Attention: Overall score >= `0.70`
- Medium Attention: Overall score >= `0.40`
- Low Attention: Overall score >= `0.20`
- No Meaningful Change: Overall score < `0.20` (filtered out of primary attention feed)

The weights and thresholds represent a calibrated V1 heuristic for filtering market noise, not an immutable law of finance.

## Data Model

Key relational database entities managed via PostgreSQL:

- `User`: Identity record storing unique email, scrypt-hashed password, name, and active status.
- `Watchlist`: Named list of instruments owned by a specific user (`user_id`).
- `WatchlistItem`: Membership join table with `position` sequence and a composite unique constraint `UNIQUE(watchlist_id, instrument_id)`.
- `Instrument`: Authoritative security record with unique `nse_symbol`, company name, and exchange.
- `MarketObservation`: Historical end-of-day price (`open`, `high`, `low`, `close`, `price`), volume, and timestamp with `UNIQUE(instrument_id, observed_at, source)`.
- `MarketEvent`: Corporate actions and dividend announcements linked to instruments.
- `NewsArticle`: Cached news articles with external provider article ID and composite unique constraint `UNIQUE(provider, provider_article_id, instrument_id)`.
- `UserObservation`: Records the baseline observation ID when a user explicitly checks their watchlist with `UNIQUE(user_id, watchlist_id, instrument_id)`.
- `DetectedChange`: Detected price/volume change record between a user's baseline observation and current observation.
- `SignificanceAssessment`: Calculated component scores, overall score, attention level, and structured explanation for a detected change.
- `ChangeReview`: Acknowledgment record indicating a user has reviewed a change with `UNIQUE(user_id, detected_change_id)`.

## Data Sources and Freshness

- Market Data: Consumes authoritative National Stock Exchange (NSE) CM-UDiFF (Capital Market Unified Distributable File Format) Bhavcopy CSV files. Data represents official End-of-Day (EOD) settled sessions. The application does not claim or fabricate live streaming tick feeds.
- Freshness Transparency: Every price display and API response reports source, data status (`HISTORICAL`, `FINAL`, or `UNAVAILABLE`), and observation timestamp.
- Contextual News: Integrated with Marketaux REST API to query recent financial headlines matching instrument symbols within a 72-hour window of detected moves.

## News Context

Marketaux news is integrated as a supplementary context layer. It never modifies, scales, or replaces the quantitative significance calculation.

- Non-Causal Presentation: News is presented under the heading *"Potentially relevant news around this move"* with temporal proximity notes (e.g., *"Published within hours of the detected move"*). The application never states that an article caused a market movement.
- Relevance Ranking: Articles are ranked by entity match score, direct ticker match, and temporal closeness to the change event, capped at a maximum of 3 articles.
- Fallback: When no qualifying articles exist, the system displays: *"No relevant news found around this change."*

## Authentication and Security

- Password Hashing: Uses memory-hard scrypt (`hashlib.scrypt`) with unique 16-byte cryptographically secure salts and constant-time digest comparison (`secrets.compare_digest`). Passwords are never stored in plaintext.
- Stateless Tokens: HS256-signed JSON Web Tokens (JWT) containing subject, email, issue time, and expiration.
- Server-Side Authorization: User identity is extracted exclusively from validated bearer tokens. Client-provided user IDs are rejected. Database queries strictly filter by `user_id == current_user.id`. Access attempts to resources owned by other users return `404 Not Found` to prevent resource enumeration.
- Credential Protection: `MARKETAUX_API_TOKEN` and JWT secret keys are loaded from backend configuration and never exposed in API responses or frontend code.
- Sanitized Errors: Unhandled exceptions are logged server-side and returned as generic 500 error responses without leaking SQL statements, table structures, or stack traces.

## API Endpoints

All application routes are versioned under `/api/v1`:

### Authentication
- `POST /api/v1/auth/register`: Register a new user account.
- `POST /api/v1/auth/login`: Authenticate credentials and receive access token.
- `GET /api/v1/auth/me`: Retrieve current authenticated user profile.
- `POST /api/v1/auth/logout`: Terminate session acknowledgment.

### Watchlists
- `GET /api/v1/watchlists`: List all watchlists owned by authenticated user.
- `POST /api/v1/watchlists`: Create a new watchlist.
- `GET /api/v1/watchlists/{id}`: Get watchlist details with ordered items.
- `PATCH /api/v1/watchlists/{id}`: Rename a watchlist.
- `DELETE /api/v1/watchlists/{id}`: Delete a watchlist.
- `POST /api/v1/watchlists/{id}/items`: Add an instrument to a watchlist.
- `DELETE /api/v1/watchlists/{id}/items/{instrument_id}`: Remove an instrument from a watchlist.
- `PATCH /api/v1/watchlists/{id}/items/reorder`: Reorder instruments in a watchlist.

### Instruments
- `GET /api/v1/instruments`: Search and list available NSE instruments.
- `GET /api/v1/instruments/{id}`: Retrieve stock detail, change timeline, and news.

### Market Data
- `GET /api/v1/watchlists/{id}/market`: Get latest market prices and session changes.
- `POST /api/v1/watchlists/{id}/refresh`: Ingest the next chronological market observation.

### Changes and Attention
- `POST /api/v1/watchlists/{id}/check`: Establish or advance user observation baseline.
- `GET /api/v1/watchlists/{id}/changes`: Retrieve detected candidate changes since baseline.
- `GET /api/v1/watchlists/{id}/attention`: Retrieve filtered, ranked attention cards.
- `POST /api/v1/watchlists/{id}/changes/{change_id}/review`: Mark individual change as reviewed.
- `POST /api/v1/watchlists/{id}/instruments/{instrument_id}/review`: Mark all changes for an instrument as reviewed.
- `POST /api/v1/watchlists/{id}/review-all`: Mark all surfaced changes in watchlist as reviewed.

### Health
- `GET /api/v1/health`: System health and status check.

## Local Development

### Prerequisites

- Python >= 3.11
- Node.js >= 18 and npm >= 9
- Docker and Docker Compose
- PostgreSQL 16 (or Docker container)

### Step 1: Start PostgreSQL

From the project root:

```bash
docker compose up -d
```

### Step 2: Configure Environment Variables

Create `backend/.env` based on `backend/.env.example`:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://smw_user:smw_password@localhost:5433/smw_db
TEST_DATABASE_URL=postgresql+asyncpg://smw_user:smw_password@localhost:5433/smw_test_db

# Security
SECRET_KEY=your-secure-random-secret-key-at-least-32-chars
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# External Integrations (Optional)
MARKETAUX_API_TOKEN=your_marketaux_api_token
```

### Step 3: Run Database Migrations

Apply Alembic migrations to set up the database schema:

```bash
# Windows
.\backend\.venv\Scripts\alembic.exe -c backend/alembic.ini upgrade head

# Linux / macOS
alembic -c backend/alembic.ini upgrade head
```

### Step 4: Seed Development Data

Seed the deterministic demo user (`dev@example.com` / `password123`) and initial NSE equities:

```bash
# Windows
$env:PYTHONPATH="backend"; .\backend\.venv\Scripts\python.exe -m app.seed

# Linux / macOS
PYTHONPATH=backend python3 -m app.seed
```

### Step 5: Start Backend Server

```bash
# Windows
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000

# Linux / macOS
cd backend
uvicorn app.main:app --reload --port 8000
```

- API Base: `http://localhost:8000`
- OpenAPI Documentation: `http://localhost:8000/docs`

### Step 6: Start Frontend Application

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

- Web Interface: `http://localhost:5173`

Log in using the demo account credentials:
- Email: `dev@example.com`
- Password: `password123`

## Environment Variables

| Variable | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | String | Yes | Async PostgreSQL connection string for application. |
| `TEST_DATABASE_URL` | String | Yes | Isolated test database connection string. |
| `SECRET_KEY` | String | Yes | Cryptographic secret for signing JWT tokens. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Integer | No | JWT expiration lifetime (default: 10080 / 7 days). |
| `MARKETAUX_API_TOKEN` | String | No | Marketaux API token for contextual news. If omitted, app operates gracefully in degraded mode. |
| `MARKETAUX_BASE_URL` | String | No | Base endpoint for Marketaux API (default: `https://api.marketaux.com/v1`). |
| `MARKETAUX_TIMEOUT_SECONDS` | Float | No | HTTP timeout for external news queries (default: 8.0s). |

## Testing

The project contains a comprehensive automated test suite with 114 test cases spanning unit, integration, security, and end-to-end tests. Tests execute against an isolated test database (`smw_test_db`).

### Running Backend Tests

```bash
# Windows
cd backend
.\.venv\Scripts\pytest.exe tests -v

# Linux / macOS
cd backend
pytest tests -v
```

### Building Frontend

```bash
cd frontend
npm run build
```

## Engineering Decisions and Trade-offs

1. Relational Database over Document Store: Market data, user observations, watchlist memberships, and audit reviews require strict ACID compliance, foreign key cascading, and composite uniqueness invariants. PostgreSQL guarantees that stale observations or orphan items cannot corrupt state.
2. Deterministic Heuristic Scoring over Machine Learning: Financial machine learning models often behave as black boxes that struggle to explain *why* a move matters. A transparent, evidence-weighted model provides auditable reasoning that users can verify against concrete numbers.
3. Attention Prioritization Separate from Financial Significance: A high-significance move that the user has already seen or reviewed does not need repeated alarms. Decoupling mathematical significance from attention state enables an uncluttered attention feed.
4. Persistent Baseline Separation: Background ingestion of new bhavcopies updates the market snapshot without moving the user's baseline. A change is only cleared when the user explicitly reviews it or clicks "Check for changes".
5. Marketaux as Supporting Context: News is treated strictly as qualitative background reading. This avoids the fragility of automated sentiment scoring and prevents external news availability from impacting core market data calculations.
6. Graceful Degradation: If Marketaux returns rate limits (HTTP 429), timeouts, or server errors, the attention feed continues functioning with full quantitative fidelity, displaying clean fallbacks.
7. Lightweight JWT without Heavy Auth Dependencies: Authentication uses standard library `hashlib.scrypt` and RFC 7519 HMAC-SHA256 JWT tokens. This eliminates heavy external dependencies like passlib, bcrypt, or complex auth microservices while adhering to NIST and OWASP standards.

## Limitations and Future Improvements

1. End-of-Day Data Granularity: The current market data provider parses daily NSE CM-UDiFF Bhavcopy files. Intraday minute-by-minute ticks are not currently ingested.
2. Marketaux Free Tier Limits: External news retrieval is constrained by provider daily quota limits. The database cache mitigates repeated calls, but high query frequency may encounter provider throttling.
3. Single Exchange Focus: Ingestion is tailored for the National Stock Exchange of India (NSE). Support for BSE or international exchanges would require additional provider implementations.
4. Single-Factor Benchmark: Relative performance is calculated exclusively against NIFTY 50. Sector-specific indices could provide more localized relative performance context in future iterations.

## Project Structure

```
groww-challenge/
├── AGENTS.md                                # Engineering constitution and operational rules
├── README.md                                # Project documentation
├── docker-compose.yml                       # PostgreSQL multi-database container config
├── backend/
│   ├── alembic/                             # Database migrations
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py                      # Authentication & session dependencies
│   │   │   └── v1/                          # Versioned REST route controllers
│   │   ├── core/
│   │   │   └── security.py                  # Password hashing & JWT token handling
│   │   ├── models/                          # SQLAlchemy database entities
│   │   ├── providers/                       # Market data provider implementations
│   │   ├── schemas/                         # Pydantic validation schemas
│   │   ├── services/                        # Business logic, scoring & news service
│   │   ├── config.py                        # Application settings
│   │   ├── main.py                          # FastAPI application factory
│   │   └── seed.py                          # Idempotent development seed engine
│   └── tests/                               # Comprehensive pytest automated test suite
└── frontend/
    ├── src/
    │   ├── api.js                           # API client with automatic token injection
    │   ├── App.jsx                          # Main React UI component & AuthView
    │   └── App.css                          # Application styling
    ├── index.html
    └── package.json
```
