# Attention Model - Smart Market Watchlist

> Design, scoring mechanics, deduplication, and ranking principles for Milestone 4: Attention Feed & User-Facing Explanations.

---

## 1. Product Thesis: Attention Filter

Traditional market watchlists act like raw firehoses: they dump tables of percentage ticks, red/green colors, and real-time noise on the user.

The Smart Market Watchlist acts as an **Attention Filter**:
- **Not a stock predictor**: Does not forecast prices or direction.
- **Not investment advice**: Never answers *"Should I buy or sell?"*.
- **The Core Question**: *"Since you last checked, what meaningfully changed, and how much attention does this change deserve based on the available evidence?"*

The user experience communicates:
> **"3 stocks deserve your attention."**  
> rather than:  
> *"Here are 20 stocks and their daily percentages."*

---

## 2. Pipeline: From Market Data to Ranked Attention

```
[ MarketObservation (NSE EOD / Historical) ]
                    │
                    ▼
[ DetectedChange Candidates ]
  - PRICE_MOVE
  - ABNORMAL_RETURN
  - RELATIVE_PERFORMANCE
  - VOLUME_ANOMALY
                    │
                    ▼
[ Significance Assessment ]
  - Magnitude Score (35%)
  - Abnormality Score (30%)
  - Relative Performance (20%)
  - Volume Anomaly (15%)
  - Material Events (10%)
                    │
                    ▼
[ Episode Grouping & Deduplication ]
  - (user, instrument, baseline_obs, current_obs) -> Single AttentionItem
                    │
                    ▼
[ Deterministic Multi-Criteria Ranking ]
  1. overall_score DESC
  2. significance_level (HIGH > MEDIUM > LOW)
  3. corroborating signals count DESC
  4. symbol ASC (deterministic tie-breaker)
                    │
                    ▼
[ Attention Feed Output ]
  - Primary Feed (HIGH, MEDIUM, LOW items)
  - Quiet Stocks Panel (NONE / within normal variance)
  - Diagnostic Panel (insufficient baseline / history)
```

---

## 3. Episode Grouping & Deduplication

In earlier pipeline stages, multiple candidate detections can trigger for the same stock over the same tracking interval:
- A price drop of 4.5% triggers `PRICE_MOVE`.
- The move corresponds to a 2.3 standard deviation outlier, triggering `ABNORMAL_RETURN`.
- The move occurred alongside 2.1x median volume, triggering `VOLUME_ANOMALY`.
- The move underperformed the benchmark by 3.8%, triggering `RELATIVE_PERFORMANCE`.

Surfacing 4 separate cards for the same event confuses the user and creates alert fatigue.

### Grouping Rule
All candidate detections sharing the unique episode tuple:
`Tuple(user_id, instrument_id, baseline_observation_id, current_observation_id)`
are grouped into a **single, unified `AttentionItem`**.

The `AttentionItem` captures:
1. The combined **`overall_score`** and **`significance_level`**.
2. Net observed movement (baseline price -> current price, absolute change, percentage change).
3. The list of **`constituent_change_types`** for full auditability.
4. Component score weights and raw evidence metrics.

---

## 4. Multi-Criteria Deterministic Ranking

When a user views their attention feed, items appear in a strictly deterministic, defensible order:

1. **`overall_score` (Descending)**: Continuous normalized score in [0.0, 1.0]. The strongest aggregate signal ranks highest.
2. **`significance_level` (HIGH > MEDIUM > LOW)**: Explicit categorical tiering to maintain strict bracket consistency.
3. **Corroborating Signal Count (Descending)**: A move supported by multiple independent components (price abnormality + volume surge + benchmark divergence) ranks above a move supported by magnitude alone.
4. **Symbol (Ascending)**: Deterministic, stable alphabetical tie-breaker ensuring reproducible feed order across requests.

---

## 5. Filtering: Meaningful Changes vs Quiet Stocks vs Insufficient Data

To keep the primary feed focused on what matters, the system divides watchlist instruments into three explicit categories:

| Category | Significance Score | Action in UI | User Communication |
| :--- | :--- | :--- | :--- |
| **Primary Feed** | >= 0.20 (`HIGH`, `MEDIUM`, `LOW`) | Surfaced prominently with structured explanation and evidence bullets | *"3 stocks deserve your attention"* |
| **Quiet Stocks** | < 0.20 (`NONE` or no change) | Excluded from primary feed; summarized and listed in collapsible drawer | *"17 stocks had no meaningful changes"* |
| **Insufficient Data** | Missing baseline or missing history | Separated from quiet stocks into transparent diagnostic drawer | *"1 stock lacks baseline data (Click 'Mark as Checked')"* |

### Why NONE is Excluded from Primary Feed
If every stock that changed by 0.01% appeared in the primary attention feed, the product would devolve into a conventional price table. Excluding `NONE` while explicitly reporting the count ensures high attention density while maintaining full transparency.

---

## 6. Deterministic, Evidence-Based Explanations

The attention feed does not rely on nondeterministic LLMs or external hallucination-prone text generation. Every surfaced item includes a `structured_explanation` constructed directly from verified database records:

### Structure
- **`what_happened`**: Factual price movement, net rupees, and direction.  
  *Example*: `"TCS moved +4.27% (+₹170.80) since you last checked."`
- **`why_it_stands_out`**: Primary context explaining why the item was surfaced.  
  *Example*: `"The move was unusually large relative to TCS's recent history."`
- **`supporting_evidence`**: Bulleted list of corroborating signals.  
  *Examples*:
  - `"Trading volume was approximately 2.2x its recent median."`
  - `"The stock outperformed NIFTY 50 by 3.10 percentage points."`
  - `"The move was unusually large relative to recent return distribution (z = +2.45)."`
- **`missing_data_notes`**: Explicit disclosures when data components were unavailable.  
  *Examples*: `"Benchmark comparison unavailable"`, `"Insufficient history for statistical abnormality calculation"`.

### Strict Non-Causality Rules
Per project guidelines, the system **never implies unsupported causality**:
- Never uses *"caused by"*, *"because of"*, or *"due to earnings"*.
- Uses strictly correlational and observational language: *"accompanied by"*, *"coincided with"*, *"was observed alongside"*.

---

## 7. Data Provenance & Freshness

To prevent user confusion regarding market data timing:
- The system never calls historical or end-of-day data *"live"*.
- Every attention card displays a clear freshness note:  
  *"Based on NSE market data through Sep 02, 2026, 03:30 PM IST."*
- Tracking intervals display the exact baseline timestamp and current observation timestamp.

---

## 8. Known Limitations & Roadmap

1. **Intraday Streaming**: The current implementation operates over NSE end-of-day official bhavcopy snapshots. Intraday tick streaming is out of scope for V1 and will be introduced when real-time feeds are integrated.
2. **Corporate Actions & News Feeds**: The event scoring engine (`WEIGHT_EVENT = 0.10`) is architected and tested, but returns neutral scores in V1 until a verified corporate action provider is configured.
