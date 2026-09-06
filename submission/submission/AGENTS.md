# Engineering Constitution

## 1. Project

This repository contains the Smart Market Watchlist project for the Groww engineering challenge.

The product is an attention-filtering market watchlist.

Its purpose is to help a user understand what has meaningfully changed in the stocks they follow since they last checked.

The core loop is:

Watch → Leave → Market changes → Return → Understand what changed → Decide what to investigate.

This is NOT:
- a trading recommendation system
- a stock prediction system
- a portfolio optimizer
- a generic financial news feed
- a replacement for a trading terminal

The system should surface information and context, not tell users what to buy or sell.

---

## 2. Engineering Priorities

When making engineering decisions, prioritize in this order:

1. Correctness
2. Data integrity
3. Reliability
4. Security
5. Simplicity
6. Maintainability
7. Testability
8. Performance where it is actually justified
9. Feature breadth

A smaller system that is correct and explainable is preferable to a larger system that is fragile.

Do not add complexity merely because it is technically interesting.

---

## 3. Architecture

The intended high-level architecture is:

Frontend
→ FastAPI backend
→ Application/domain logic
→ PostgreSQL

External market-data and news providers must be isolated behind provider boundaries so that the intelligence layer does not depend directly on a specific vendor.

The conceptual data flow is:

External data
→ normalized persistent data
→ derived intelligence
→ user state
→ frontend

Keep raw external facts separate from derived intelligence and from user-specific state.

Do not introduce microservices unless there is a demonstrated requirement.

Do not introduce Kafka, RabbitMQ, Celery, Kubernetes, Redis, WebSockets, or other infrastructure without a concrete problem that the infrastructure solves.

---

## 4. Product Principles

### Signal over noise

The system should help users focus on meaningful changes rather than surface every available data point.

### Attention quality over attention quantity

More alerts, more cards, or more information do not automatically make the product better.

### Material information over raw price movement

Price movement alone is often insufficient context.

Where available, company events, earnings, corporate actions, filings, relevant news, volume, and market/sector context should help determine whether a change deserves attention.

### Context over isolated numbers

A stock's movement should be interpreted relative to an appropriate benchmark, sector, historical behavior, or relevant event where possible.

### Explain, don't alarm

Every important surfaced change should have an understandable reason for why it was considered meaningful.

Avoid language that implies certainty when the evidence does not support it.

### Information, not investment advice

The system should surface information and evidence. It should not make unsupported recommendations to buy, sell, or hold.

### Transparency over false certainty

Data freshness, missing data, delayed data, conflicting sources, and uncertainty must be represented honestly.

Never fabricate precision.

### User state matters

The system must distinguish between:
- what is currently true
- what changed since the user's previous observation
- what the user has already reviewed

Background refreshes must not silently reset the user's observation point.

---

## 5. Engineering Behaviour

Before changing code:

1. Inspect the relevant existing code and structure.
2. Understand the current architecture and conventions.
3. State the implementation approach.
4. Identify important edge cases and failure modes.
5. Implement the smallest solution that satisfies the requirement.

Do not silently redesign unrelated parts of the system.

Do not rewrite working code merely for stylistic preference.

Do not introduce dependencies without justification.

Do not invent APIs, data fields, provider behavior, test results, or system capabilities.

Do not claim something was tested unless the test was actually run.

Do not expose, commit, or hard-code secrets.

---

## 6. Data Integrity and Reliability

Whenever relevant, consider:

- input validation
- database constraints
- foreign-key integrity
- uniqueness constraints
- duplicate requests
- idempotency
- transaction boundaries
- concurrent updates
- stale data
- delayed data
- missing data
- conflicting data
- external API failures
- timeouts
- retries
- rate limits
- provider outages
- provenance and source tracking

Do not hide data-quality problems from the user by silently substituting fabricated or stale values.

External provider failures should degrade gracefully where practical.

---

## 7. Market Intelligence

The intelligence layer should remain explainable.

Meaningfulness may consider factors such as:

- magnitude of movement
- abnormality relative to historical behavior
- relative performance versus a benchmark
- abnormal volume
- material company events
- persistence
- user relevance

These are engineering concepts, not universal formulas.

Do not invent arbitrary thresholds or weights and present them as objectively correct.

If a scoring model is introduced, document:
- what each component represents
- why it exists
- how it is normalized
- why the chosen thresholds or weights are reasonable
- what its limitations are

Never claim that an event caused a price movement unless causality is actually established.

Prefer evidence-based language such as "coincided with" or "potentially relevant event."

---

## 8. External Data Providers

Market data must be accessed through a provider abstraction.

The application should not become tightly coupled to one market-data vendor.

Potential providers may include:
- Groww
- Twelve Data
- NSE-related sources where appropriate

News may be obtained through Marketaux.

Provider-specific response formats must be normalized before entering the core domain/intelligence layer.

Do not use undocumented/private endpoints when an official interface is available.

Treat external data as untrusted input.

---

## 9. Database

PostgreSQL is the primary database.

Use SQLAlchemy for persistence and Alembic for schema migrations.

Prefer relational integrity and explicit constraints over application-only assumptions.

Important invariants should be enforced at the database level where appropriate.

Do not use the database as a dumping ground for unstructured external responses when a normalized domain model is appropriate.

---

## 10. API Design

FastAPI is the backend framework.

API endpoints should:
- validate input
- return predictable response shapes
- use appropriate HTTP semantics
- handle invalid references explicitly
- avoid leaking internal implementation details
- enforce authorization once authentication exists
- remain reasonably backwards-compatible as the frontend evolves

Keep HTTP concerns separate from domain/application logic and persistence concerns.

---

## 11. Frontend

The frontend uses:

- React
- JavaScript
- Vite

Do not introduce TypeScript unless explicitly decided later.

The UI should prioritize:
- clarity
- information hierarchy
- understandable explanations
- freshness/data status
- useful context
- low cognitive load

Do not add UI elements merely to make the application appear feature-rich.

---

## 12. Testing

Critical behavior should eventually have automated coverage.

Tests should prioritize:
- business rules
- data integrity
- API behavior
- edge cases
- failure handling
- regression-prone behavior
- integration between important components

A passing test suite does not automatically mean the implementation is correct.

Do not weaken or delete tests simply to make an implementation pass.

When reporting test status, distinguish between:
- tests actually executed
- tests that exist but were not executed
- known limitations

---

## 13. Complexity

Default to the simplest architecture that satisfies the requirement.

Complexity must earn its place.

Before adding infrastructure, abstraction, asynchronous processing, caching, event queues, ML models, or distributed components, identify the concrete problem they solve.

Prefer:
- modular monolith
- clear boundaries
- explicit data flow
- boring technology
- deterministic behavior
- observable failure modes

over premature distributed architecture.

---

## 14. Git and Changes

Keep changes focused.

Do not modify unrelated files.

Do not commit or push automatically unless explicitly requested.

Before a commit, verify:
- intended files changed
- tests/checks were run
- no secrets were added
- no debugging artifacts remain
- migrations are included where required

Commit messages should describe the actual change.

---

## 15. Agent Responsibility

Agents are implementation and review tools.

They do not own product direction.

When requirements are ambiguous, agents should identify the ambiguity and make the smallest reasonable assumption rather than silently expanding scope.

Major architectural or product decisions should be surfaced to the human engineer.

The human remains responsible for:
- product decisions
- architectural decisions
- trade-offs
- scope
- final acceptance
- what gets committed
