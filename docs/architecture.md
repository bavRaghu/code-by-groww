# Architecture – Smart Market Watchlist

> High-level system design for the Code, by Groww 2026 submission.

---

## Product Thesis

Traditional watchlists show users _what_ their stocks are doing.

This product instead answers:

> **"What meaningfully changed since I last checked?"**

The system acts as an **attention filter** – surfacing only the changes that genuinely deserve a user's attention and explaining why, rather than overwhelming them with every price tick.

---

## Conceptual Data Model

The system recognises three distinct layers of information:

```
External world
    │
    ▼
RAW DATA
  ├─ Market observations  (prices, volumes, OHLC)
  ├─ Market events        (earnings, dividends, splits)
  └─ Financial news

    │
    ▼
DERIVED INTELLIGENCE
  ├─ Detected changes     (what moved)
  ├─ Significance scores  (does it matter?)
  ├─ Market context       (sector moves, macro)
  └─ Explanations         (why it might matter)

    │
    ▼
USER STATE
  ├─ Watchlists           (which instruments the user tracks)
  ├─ Last-seen state      (what the user has already reviewed)
  └─ Reviewed changes     (audit trail)
```

The frontend consumes **Derived Intelligence** and **User State** via the backend API.  
It never talks directly to external data providers.

---

## System Layers

```
┌──────────────────────────────────────┐
│           React Frontend             │  Vite dev server / Vercel
│   (Vite + React + JavaScript)        │
└───────────────┬──────────────────────┘
                │  REST / JSON
                ▼
┌──────────────────────────────────────┐
│           FastAPI Backend            │  Uvicorn / Render / Railway
│                                      │
│  ┌─────────────────────────────┐     │
│  │  API layer  (routers)       │     │
│  └──────────────┬──────────────┘     │
│                 │                    │
│  ┌──────────────▼──────────────┐     │
│  │  Application / domain       │     │
│  │  services  (to be built)    │     │
│  └──────────────┬──────────────┘     │
│                 │                    │
│  ┌──────────────▼──────────────┐     │
│  │  Persistence layer          │     │
│  │  SQLAlchemy + Alembic       │     │
│  └──────────────┬──────────────┘     │
│                 │                    │
│  ┌──────────────▼──────────────┐     │
│  │  External integration       │     │
│  │  boundaries (to be built)   │     │
│  └─────────────────────────────┘     │
└───────────────┬──────────────────────┘
                │
        ┌───────▼────────┐     ┌────────────────────┐
        │  PostgreSQL    │     │  External providers │
        │  (managed)     │     │  Twelve Data /      │
        └────────────────┘     │  Marketaux / etc.   │
                               └────────────────────┘
```

---

## Key Design Principles

| Principle | Implication |
|---|---|
| Signal over noise | Change detection must distinguish meaningful moves from noise |
| Attention quality | The ranked feed surfaces what matters most first |
| Context over raw numbers | A 5% move means different things in different contexts |
| Explanation over alarm | Show *why* something may matter, not just *that* it moved |
| Transparency over false certainty | Avoid unsupported causal claims |
| User state is first-class | Last-seen state drives what counts as "new" |
| Reliability over features | Stale, missing, or conflicting data must be handled explicitly |

---

## External Integration Strategy

External market and news providers are accessed exclusively through **backend integration boundaries**.

The rest of the application (API layer, services, persistence) must not depend directly on any specific provider.

This allows providers to be swapped without cascading changes.

Providers under consideration:

- **Market data** – Twelve Data, Groww API (if available), NSE data sources
- **Financial news** – Marketaux

These integrations are **not yet implemented**.

---

## Background Processing (Future)

Periodic market-data polling and change detection will eventually run as background jobs managed by **APScheduler** within the backend process.

No message queue (Kafka, RabbitMQ, Celery) will be added unless the workload demonstrably requires it.

---

## Deployment Targets (Future)

| Component | Target |
|---|---|
| Frontend | Vercel |
| Backend | Render or Railway |
| Database | Managed PostgreSQL (Render / Neon / Supabase) |

---

## Current State

The repository currently contains only the **project skeleton**:

- Runnable React + Vite frontend
- Runnable FastAPI backend with a health-check endpoint
- PostgreSQL running via Docker Compose

No domain models, business logic, or external integrations exist yet.
