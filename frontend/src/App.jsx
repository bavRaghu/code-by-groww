import { useState, useEffect, useCallback } from 'react';
import './App.css';
import {
  fetchWatchlists,
  createWatchlist,
  deleteWatchlist,
  fetchWatchlistMarket,
  searchInstruments,
  addInstrumentToWatchlist,
  removeInstrumentFromWatchlist,
  checkWatchlist,
  fetchWatchlistChanges,
  fetchWatchlistAttention,
  refreshWatchlistMarket,
  reviewChange,
  reviewInstrumentChanges,
  reviewAllWatchlistChanges,
  fetchStockDetail,
} from './api';

function formatDateTime(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    return d.toLocaleString('en-IN', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return isoString;
  }
}

function getAttentionLevelMeta(level) {
  switch (level) {
    case 'HIGH':
      return { label: 'High Attention', badgeClass: 'attention-badge--high', cardClass: 'attention-card--high' };
    case 'MEDIUM':
      return { label: 'Medium Attention', badgeClass: 'attention-badge--medium', cardClass: 'attention-card--medium' };
    case 'LOW':
      return { label: 'Low Attention', badgeClass: 'attention-badge--low', cardClass: 'attention-card--low' };
    default:
      return { label: level, badgeClass: '', cardClass: '' };
  }
}

function getEvidenceCompletenessMeta(completeness) {
  if (!completeness) return null;
  switch (completeness.level) {
    case 'STRONG':
      return { label: 'Strong Evidence', badgeClass: 'evidence-badge--strong', summary: completeness.summary };
    case 'MODERATE':
      return { label: 'Moderate Evidence', badgeClass: 'evidence-badge--moderate', summary: completeness.summary };
    case 'LIMITED':
      return { label: 'Limited Context', badgeClass: 'evidence-badge--limited', summary: completeness.summary };
    default:
      return null;
  }
}

function getChangeTypeMeta(type) {
  switch (type) {
    case 'PRICE_MOVE':
      return { label: 'Price Movement', badgeClass: 'change-badge--price' };
    case 'ABNORMAL_RETURN':
      return { label: 'Unusual Movement', badgeClass: 'change-badge--abnormal' };
    case 'RELATIVE_PERFORMANCE':
      return { label: 'Relative Performance', badgeClass: 'change-badge--relative' };
    case 'VOLUME_ANOMALY':
      return { label: 'Volume Anomaly', badgeClass: 'change-badge--volume' };
    case 'MATERIAL_EVENT':
      return { label: 'Material Event', badgeClass: 'change-badge--event' };
    default:
      return { label: type, badgeClass: 'change-badge--price' };
  }
}

function StockChart({ series, symbol }) {
  const [hoverIndex, setHoverIndex] = useState(null);

  if (!series || series.length === 0) {
    return (
      <div className="stock-chart-empty">
        <span>No historical observation series available for charting.</span>
      </div>
    );
  }

  const width = 760;
  const height = 280;
  const margin = { top: 30, right: 35, bottom: 40, left: 65 };
  const plotWidth = width - margin.left - margin.right;
  const priceHeight = 140;
  const volumeGap = 20;
  const volumeHeight = 50;
  const volumeTop = margin.top + priceHeight + volumeGap;

  const prices = series.map((p) => Number(p.price));
  const minRawPrice = Math.min(...prices);
  const maxRawPrice = Math.max(...prices);
  const priceRange = maxRawPrice - minRawPrice;
  const paddingPrice = priceRange === 0 ? (maxRawPrice * 0.05 || 1) : priceRange * 0.1;
  const minPrice = Math.max(0, minRawPrice - paddingPrice);
  const maxPrice = maxRawPrice + paddingPrice;

  const volumes = series.map((p) => p.volume || 0);
  const maxVolume = Math.max(...volumes, 1);

  const getX = (i) => {
    if (series.length === 1) return margin.left + plotWidth / 2;
    return margin.left + (i / (series.length - 1)) * plotWidth;
  };

  const getY = (price) => {
    if (maxPrice === minPrice) return margin.top + priceHeight / 2;
    return margin.top + (1 - (price - minPrice) / (maxPrice - minPrice)) * priceHeight;
  };

  const linePoints = series.map((pt, i) => `${getX(i)},${getY(Number(pt.price))}`).join(' ');
  const areaPoints = series.length > 1
    ? `${getX(0)},${margin.top + priceHeight} ${linePoints} ${getX(series.length - 1)},${margin.top + priceHeight}`
    : '';

  const activePoint = hoverIndex !== null && hoverIndex >= 0 && hoverIndex < series.length
    ? series[hoverIndex]
    : null;

  return (
    <div className="stock-chart-container">
      <div className="stock-chart-legend">
        <div className="legend-item">
          <span className="legend-swatch legend-swatch--line" />
          <span>NSE Price Series</span>
        </div>
        <div className="legend-item">
          <span className="legend-swatch legend-swatch--baseline" />
          <span>Baseline Observation (Last Checked)</span>
        </div>
        <div className="legend-item">
          <span className="legend-swatch legend-swatch--current" />
          <span>Current Observation</span>
        </div>
        <div className="legend-item">
          <span className="legend-swatch legend-swatch--volume" />
          <span>Session Volume</span>
        </div>
      </div>

      {activePoint && (
        <div className="chart-hover-indicator">
          <span className="hover-date">{formatDateTime(activePoint.observed_at)}</span>
          <span className="hover-price">₹{Number(activePoint.price).toFixed(2)}</span>
          {activePoint.volume && (
            <span className="hover-vol">Vol: {Number(activePoint.volume).toLocaleString('en-IN')}</span>
          )}
          {activePoint.is_baseline && (
            <span className="hover-tag hover-tag--baseline">★ Baseline</span>
          )}
          {activePoint.is_current && (
            <span className="hover-tag hover-tag--current">● Current</span>
          )}
        </div>
      )}

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="stock-chart-svg"
        onMouseLeave={() => setHoverIndex(null)}
      >
        <defs>
          <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#58a6ff" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#58a6ff" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Grid lines & price labels */}
        {[0, 0.5, 1].map((pct, idx) => {
          const pVal = minPrice + (1 - pct) * (maxPrice - minPrice);
          const yPos = margin.top + pct * priceHeight;
          return (
            <g key={idx}>
              <line
                x1={margin.left}
                y1={yPos}
                x2={width - margin.right}
                y2={yPos}
                stroke="rgba(255, 255, 255, 0.08)"
                strokeDasharray="2 4"
              />
              <text
                x={margin.left - 8}
                y={yPos + 4}
                fill="var(--color-text-muted)"
                fontSize="11"
                textAnchor="end"
              >
                ₹{pVal.toFixed(1)}
              </text>
            </g>
          );
        })}

        {/* Volume baseline */}
        <line
          x1={margin.left}
          y1={volumeTop + volumeHeight}
          x2={width - margin.right}
          y2={volumeTop + volumeHeight}
          stroke="rgba(255, 255, 255, 0.15)"
        />
        <text
          x={margin.left - 8}
          y={volumeTop + volumeHeight}
          fill="var(--color-text-muted)"
          fontSize="10"
          textAnchor="end"
        >
          Vol 0
        </text>
        <text
          x={margin.left - 8}
          y={volumeTop + 12}
          fill="var(--color-text-muted)"
          fontSize="10"
          textAnchor="end"
        >
          {maxVolume > 1000000 ? `${(maxVolume / 1000000).toFixed(1)}M` : `${(maxVolume / 1000).toFixed(0)}k`}
        </text>

        {/* Volume Bars */}
        {series.map((pt, i) => {
          const v = pt.volume || 0;
          const vH = (v / maxVolume) * volumeHeight;
          const barW = Math.max(4, Math.min(18, (plotWidth / series.length) * 0.55));
          const bx = getX(i) - barW / 2;
          const by = volumeTop + (volumeHeight - vH);
          const isHov = hoverIndex === i;
          return (
            <rect
              key={`vol-${i}`}
              x={bx}
              y={by}
              width={barW}
              height={vH}
              rx="1"
              fill={isHov ? '#58a6ff' : 'rgba(88, 166, 255, 0.28)'}
            />
          );
        })}

        {/* Area fill under curve */}
        {series.length > 1 && (
          <polygon points={areaPoints} fill="url(#priceGradient)" />
        )}

        {/* Price curve */}
        {series.length > 1 ? (
          <polyline
            points={linePoints}
            fill="none"
            stroke="#58a6ff"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : (
          <circle
            cx={getX(0)}
            cy={getY(Number(series[0].price))}
            r="5"
            fill="#58a6ff"
          />
        )}

        {/* Highlight Circles for Baseline & Current */}
        {series.map((pt, i) => {
          const cx = getX(i);
          const cy = getY(Number(pt.price));

          if (pt.is_baseline) {
            return (
              <g key={`marker-base-${i}`}>
                <circle cx={cx} cy={cy} r="9" fill="rgba(210, 153, 34, 0.25)" />
                <circle cx={cx} cy={cy} r="5" fill="#d29922" stroke="#161b22" strokeWidth="2" />
                <rect
                  x={cx - 30}
                  y={cy - 24}
                  width="60"
                  height="16"
                  rx="3"
                  fill="#2d2206"
                  stroke="#d29922"
                  strokeWidth="1"
                />
                <text
                  x={cx}
                  y={cy - 12}
                  fill="#f0883e"
                  fontSize="9"
                  fontWeight="600"
                  textAnchor="middle"
                >
                  Baseline
                </text>
              </g>
            );
          }

          if (pt.is_current) {
            return (
              <g key={`marker-curr-${i}`}>
                <circle cx={cx} cy={cy} r="9" fill="rgba(88, 166, 255, 0.25)" />
                <circle cx={cx} cy={cy} r="5" fill="#58a6ff" stroke="#161b22" strokeWidth="2" />
                <rect
                  x={cx - 28}
                  y={cy - 24}
                  width="56"
                  height="16"
                  rx="3"
                  fill="#03224c"
                  stroke="#58a6ff"
                  strokeWidth="1"
                />
                <text
                  x={cx}
                  y={cy - 12}
                  fill="#58a6ff"
                  fontSize="9"
                  fontWeight="600"
                  textAnchor="middle"
                >
                  Current
                </text>
              </g>
            );
          }
          return null;
        })}

        {/* Hover Crosshair */}
        {hoverIndex !== null && (
          <line
            x1={getX(hoverIndex)}
            y1={margin.top}
            x2={getX(hoverIndex)}
            y2={volumeTop + volumeHeight}
            stroke="rgba(255, 255, 255, 0.4)"
            strokeDasharray="3 3"
          />
        )}

        {/* Interactive Mouse Hover Targets */}
        {series.map((pt, i) => {
          const colWidth = plotWidth / series.length;
          const tx = getX(i) - colWidth / 2;
          return (
            <rect
              key={`hit-${i}`}
              x={tx}
              y={margin.top}
              width={colWidth}
              height={priceHeight + volumeGap + volumeHeight}
              fill="transparent"
              style={{ cursor: 'crosshair' }}
              onMouseEnter={() => setHoverIndex(i)}
            />
          );
        })}
      </svg>
    </div>
  );
}

function StockDetailView({ instrumentId, watchlistId, onBack, onReview }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState(null);

  const loadDetail = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchStockDetail(instrumentId, watchlistId);
      setDetail(data);
    } catch (err) {
      setError(err.message || 'Failed to load stock detail.');
    } finally {
      setLoading(false);
    }
  }, [instrumentId, watchlistId]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  const handleReview = async () => {
    if (!watchlistId || !instrumentId) return;
    setReviewing(true);
    try {
      await onReview(instrumentId);
      await loadDetail();
    } catch (err) {
      setError(err.message || 'Failed to review stock changes.');
    } finally {
      setReviewing(false);
    }
  };

  if (loading) {
    return (
      <div className="stock-detail-loading">
        <div className="loading-spinner" />
        <span>Loading stock detail for #{instrumentId}...</span>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="stock-detail-error">
        <div className="alert alert-error">{error || 'Instrument not found.'}</div>
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          ← Back to Watchlist
        </button>
      </div>
    );
  }

  const {
    nse_symbol,
    company_name,
    exchange,
    isin,
    sector,
    current_observation,
    since_last_checked,
    evidence,
    market_context,
    timeline,
    historical_series,
    freshness_note,
    source,
    data_status,
  } = detail;

  const currentPrice = current_observation?.price !== null && current_observation?.price !== undefined
    ? Number(current_observation.price)
    : null;
  const sessionAbs = current_observation?.session_absolute_change !== null && current_observation?.session_absolute_change !== undefined
    ? Number(current_observation.session_absolute_change)
    : null;
  const sessionPct = current_observation?.session_percentage_change !== null && current_observation?.session_percentage_change !== undefined
    ? Number(current_observation.session_percentage_change)
    : null;
  const sessionIsUp = sessionPct !== null && sessionPct > 0;
  const sessionIsDown = sessionPct !== null && sessionPct < 0;

  const sycPct = since_last_checked?.percentage_change !== null && since_last_checked?.percentage_change !== undefined
    ? Number(since_last_checked.percentage_change)
    : null;
  const sycAbs = since_last_checked?.absolute_change !== null && since_last_checked?.absolute_change !== undefined
    ? Number(since_last_checked.absolute_change)
    : null;
  const sycIsUp = sycPct !== null && sycPct > 0;
  const sycIsDown = sycPct !== null && sycPct < 0;

  const sycMeta = getAttentionLevelMeta(since_last_checked?.significance_level || 'NONE');
  const evidenceMeta = getEvidenceCompletenessMeta(evidence?.evidence_completeness);

  return (
    <div className="stock-detail-view" aria-label={`Detail view for ${nse_symbol}`}>
      {/* Top Navigation Bar */}
      <div className="stock-detail-nav">
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          ← Back to Watchlist
        </button>
        <div className="stock-detail-nav__tags">
          <span className="status-badge">{exchange}</span>
          {sector && <span className="status-badge status-badge--sector">{sector}</span>}
          {isin && <span className="status-badge status-badge--isin">ISIN: {isin}</span>}
        </div>
      </div>

      {/* Stock Hero Section */}
      <div className="stock-detail-hero">
        <div className="stock-detail-hero__main">
          <div className="stock-detail-hero__symbol-wrap">
            <h1 className="stock-detail-hero__symbol">{nse_symbol}</h1>
            <span className="stock-detail-hero__company">{company_name}</span>
          </div>
          <div className="stock-detail-hero__price-wrap">
            <div className="stock-detail-hero__price">
              {currentPrice !== null ? `₹${currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'}
            </div>
            {sessionPct !== null && (
              <div className={`stock-detail-hero__session-change ${sessionIsUp ? 'val-positive' : sessionIsDown ? 'val-negative' : 'val-neutral'}`}>
                {sessionIsUp ? '+' : ''}{sessionAbs?.toFixed(2)} ({sessionIsUp ? '+' : ''}{sessionPct?.toFixed(2)}%)
                <span className="session-label">Session Move</span>
              </div>
            )}
          </div>
        </div>

        <div className="stock-detail-hero__meta">
          <div className="hero-meta-item">
            <span className="hero-meta-label">Observation Date</span>
            <span className="hero-meta-val">{formatDateTime(current_observation?.observed_at)}</span>
          </div>
          {current_observation?.volume && (
            <div className="hero-meta-item">
              <span className="hero-meta-label">Session Volume</span>
              <span className="hero-meta-val">{Number(current_observation.volume).toLocaleString('en-IN')} shares</span>
            </div>
          )}
          <div className="hero-meta-item">
            <span className="hero-meta-label">Data Provenance</span>
            <span className="hero-meta-val">
              <span className="status-badge status-badge--final">{source} • {data_status}</span>
            </span>
          </div>
        </div>

        {freshness_note && (
          <div className="stock-detail-hero__provenance-note">
            ℹ {freshness_note}
          </div>
        )}
      </div>

      {/* Main Grid: Since You Last Checked & Market Context */}
      <div className="stock-detail-grid">
        {/* Card: Since You Last Checked */}
        <div className="stock-detail-card syc-card">
          <div className="stock-detail-card__header">
            <div className="stock-detail-card__title">
              <span>👁️</span>
              <span>Since You Last Checked</span>
            </div>
            <div className="stock-detail-card__actions">
              {since_last_checked?.is_reviewed ? (
                <span className="review-status-badge review-status-badge--reviewed">
                  ✓ Reviewed
                </span>
              ) : since_last_checked?.has_baseline ? (
                <button
                  type="button"
                  className="btn btn-review-sm"
                  onClick={handleReview}
                  disabled={reviewing}
                >
                  {reviewing ? 'Updating...' : 'Mark as Reviewed'}
                </button>
              ) : null}
            </div>
          </div>

          <div className="stock-detail-card__body">
            {since_last_checked?.has_baseline ? (
              <>
                <div className="syc-comparison-grid">
                  <div className="syc-point">
                    <span className="syc-point__label">Your Baseline Observation</span>
                    <span className="syc-point__price">₹{Number(since_last_checked.baseline_price).toFixed(2)}</span>
                    <span className="syc-point__time">{formatDateTime(since_last_checked.baseline_observed_at)}</span>
                  </div>
                  <div className="syc-arrow">→</div>
                  <div className="syc-point">
                    <span className="syc-point__label">Current Market State</span>
                    <span className="syc-point__price">₹{Number(since_last_checked.current_price).toFixed(2)}</span>
                    <span className="syc-point__time">{formatDateTime(since_last_checked.current_observed_at)}</span>
                  </div>
                  <div className="syc-point syc-point--change">
                    <span className="syc-point__label">Cumulative Movement</span>
                    <span className={`syc-point__price ${sycIsUp ? 'val-positive' : sycIsDown ? 'val-negative' : 'val-neutral'}`}>
                      {sycPct !== null ? `${sycIsUp ? '+' : ''}${sycPct.toFixed(2)}%` : '—'}
                      {sycAbs !== null ? ` (${sycIsUp ? '+' : ''}₹${sycAbs.toFixed(2)})` : ''}
                    </span>
                    <span className="syc-point__time">{since_last_checked.tracking_note}</span>
                  </div>
                </div>

                <div className="syc-score-banner">
                  <div className="syc-score-banner__level">
                    <span className={`attention-badge ${sycMeta.badgeClass}`}>
                      {sycMeta.label}
                    </span>
                    <span className="attention-score-chip">
                      Significance Score: {Number(since_last_checked.overall_score || 0).toFixed(2)} / 1.00
                    </span>
                  </div>
                  <div className="syc-score-banner__status">
                    {since_last_checked.is_reviewed ? (
                      <span className="val-positive">
                        Acknowledged {since_last_checked.reviewed_at ? `on ${formatDateTime(since_last_checked.reviewed_at)}` : ''}
                      </span>
                    ) : (
                      <span className="unreviewed-tag">
                        Unreviewed changes since baseline
                      </span>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="syc-empty">
                <strong>No user baseline recorded.</strong>
                <p>
                  You haven&apos;t marked this watchlist as checked yet. Return to the watchlist and click
                  &quot;Mark as Checked&quot; to establish your reference baseline for {nse_symbol}.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Card: Market & Benchmark Context */}
        <div className="stock-detail-card market-context-card">
          <div className="stock-detail-card__header">
            <div className="stock-detail-card__title">
              <span>📊</span>
              <span>Broad Market Context</span>
            </div>
            <span className="status-badge status-badge--final">{market_context?.benchmark_symbol}</span>
          </div>

          <div className="stock-detail-card__body">
            <div className="market-context-grid">
              <div className="context-metric">
                <span className="context-metric__label">{nse_symbol} Return</span>
                <span className={`context-metric__val ${sycIsUp ? 'val-positive' : sycIsDown ? 'val-negative' : 'val-neutral'}`}>
                  {market_context?.stock_return !== null && market_context?.stock_return !== undefined
                    ? `${market_context.stock_return > 0 ? '+' : ''}${market_context.stock_return.toFixed(2)}%`
                    : '—'}
                </span>
              </div>
              <div className="context-metric">
                <span className="context-metric__label">{market_context?.benchmark_symbol} Return</span>
                <span className="context-metric__val val-neutral">
                  {market_context?.benchmark_return !== null && market_context?.benchmark_return !== undefined
                    ? `${market_context.benchmark_return > 0 ? '+' : ''}${market_context.benchmark_return.toFixed(2)}%`
                    : 'Unavailable'}
                </span>
              </div>
              <div className="context-metric">
                <span className="context-metric__label">Relative Excess Return</span>
                <span className={`context-metric__val ${
                  market_context?.excess_return && market_context.excess_return > 0 ? 'val-positive' :
                  market_context?.excess_return && market_context.excess_return < 0 ? 'val-negative' : 'val-neutral'
                }`}>
                  {market_context?.excess_return !== null && market_context?.excess_return !== undefined
                    ? `${market_context.excess_return > 0 ? '+' : ''}${market_context.excess_return.toFixed(2)} pts`
                    : '—'}
                </span>
              </div>
            </div>

            <div className="market-context-summary">
              {market_context?.context_summary}
            </div>
          </div>
        </div>
      </div>

      {/* Card: Why This Was Flagged / Evidence Breakdown */}
      <div className="stock-detail-card evidence-card">
        <div className="stock-detail-card__header">
          <div className="stock-detail-card__title">
            <span>🔬</span>
            <span>Why This Was Flagged — Evidence Breakdown</span>
          </div>
          {evidenceMeta && (
            <span className={`evidence-badge ${evidenceMeta.badgeClass}`} title={evidenceMeta.summary}>
              {evidenceMeta.label}
            </span>
          )}
        </div>

        <div className="stock-detail-card__body">
          {evidence ? (
            <div className="evidence-body">
              {/* Structured Narrative */}
              <div className="evidence-narrative">
                <div className="evidence-narrative__what">
                  <strong>What Occurred:</strong> {evidence.structured_explanation?.what_happened || evidence.why_it_matters}
                </div>
                {evidence.structured_explanation?.why_it_stands_out && (
                  <div className="evidence-narrative__stands-out">
                    <strong>Why It Stands Out:</strong> {evidence.structured_explanation.why_it_stands_out}
                  </div>
                )}
              </div>

              {/* Supporting Evidence Bullets */}
              {evidence.structured_explanation?.supporting_evidence && evidence.structured_explanation.supporting_evidence.length > 0 && (
                <div className="evidence-bullets-box">
                  <div className="evidence-bullets-box__title">Corroborating Market Evidence:</div>
                  <ul className="evidence-bullets-list">
                    {evidence.structured_explanation.supporting_evidence.map((bullet, idx) => (
                      <li key={idx}>{bullet}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Component Score Contributions */}
              {evidence.component_scores && (
                <div className="evidence-components">
                  <div className="evidence-components__title">Significance Formula Decomposition:</div>
                  <div className="evidence-components__grid">
                    <div className="component-pill">
                      <span className="component-pill__name">Magnitude</span>
                      <span className="component-pill__score">{Number(evidence.component_scores.magnitude ?? 0).toFixed(2)}</span>
                      <span className="component-pill__weight">35%</span>
                    </div>
                    <div className="component-pill">
                      <span className="component-pill__name">Abnormality</span>
                      <span className="component-pill__score">{Number(evidence.component_scores.abnormality ?? 0).toFixed(2)}</span>
                      <span className="component-pill__weight">30%</span>
                    </div>
                    <div className="component-pill">
                      <span className="component-pill__name">Relative Perf</span>
                      <span className="component-pill__score">{Number(evidence.component_scores.relative_performance ?? 0).toFixed(2)}</span>
                      <span className="component-pill__weight">20%</span>
                    </div>
                    <div className="component-pill">
                      <span className="component-pill__name">Volume</span>
                      <span className="component-pill__score">{Number(evidence.component_scores.volume ?? 0).toFixed(2)}</span>
                      <span className="component-pill__weight">15%</span>
                    </div>
                    <div className="component-pill">
                      <span className="component-pill__name">Event</span>
                      <span className="component-pill__score">{Number(evidence.component_scores.event ?? 0).toFixed(2)}</span>
                      <span className="component-pill__weight">10%</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Transparent Missing Data Disclosures */}
              {evidence.missing_data_notes && evidence.missing_data_notes.length > 0 && (
                <div className="evidence-missing-notes">
                  <div className="evidence-missing-notes__title">Data Completeness & Disclosures:</div>
                  <div className="evidence-missing-tags">
                    {evidence.missing_data_notes.map((note, idx) => (
                      <span key={idx} className="missing-note-pill">
                        ℹ {note}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="evidence-quiet-state">
              <p>
                <strong>No unusual signals detected for {nse_symbol}.</strong>
              </p>
              <p>
                Price and volume action remained within normal historical variance relative to your baseline.
                The significance score did not exceed the attention threshold (&lt; 0.20).
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Card: Price & Volume Chart */}
      <div className="stock-detail-card chart-card">
        <div className="stock-detail-card__header">
          <div className="stock-detail-card__title">
            <span>📈</span>
            <span>Price &amp; Volume Trajectory</span>
          </div>
          <span className="status-badge">{historical_series?.length || 0} Historical Sessions</span>
        </div>

        <div className="stock-detail-card__body">
          <StockChart series={historical_series} symbol={nse_symbol} />
        </div>
      </div>

      {/* Card: Change Timeline (Episodes) */}
      <div className="stock-detail-card timeline-card-section">
        <div className="stock-detail-card__header">
          <div className="stock-detail-card__title">
            <span>⏱️</span>
            <span>Change Episodes &amp; Signal History</span>
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
            {timeline?.length || 0} Episode{timeline?.length === 1 ? '' : 's'}
          </span>
        </div>

        <div className="stock-detail-card__body">
          {timeline && timeline.length > 0 ? (
            <div className="timeline-episodes-list">
              {timeline.map((ep) => {
                const epMeta = getAttentionLevelMeta(ep.significance_level);
                const epPct = ep.percentage_change !== null && ep.percentage_change !== undefined
                  ? Number(ep.percentage_change)
                  : null;
                const epIsUp = epPct !== null && epPct > 0;
                const epIsDown = epPct !== null && epPct < 0;

                return (
                  <div key={ep.id} className={`episode-row ${ep.is_reviewed ? 'episode-row--reviewed' : ''}`}>
                    <div className="episode-row__time">
                      <div className="episode-time-end">{formatDateTime(ep.observation_end)}</div>
                      {ep.observation_start && (
                        <div className="episode-time-start">from {formatDateTime(ep.observation_start)}</div>
                      )}
                    </div>

                    <div className="episode-row__content">
                      <div className="episode-row__badges">
                        <span className={`attention-badge ${epMeta.badgeClass}`}>{epMeta.label}</span>
                        {ep.constituent_change_types.map((type, idx) => {
                          const typeMeta = getChangeTypeMeta(type);
                          return (
                            <span key={idx} className={`change-badge ${typeMeta.badgeClass}`}>
                              {typeMeta.label}
                            </span>
                          );
                        })}
                        <span className="attention-score-chip">
                          Score: {Number(ep.overall_score || 0).toFixed(2)}
                        </span>
                        {ep.is_reviewed ? (
                          <span className="review-status-badge review-status-badge--reviewed">
                            ✓ Reviewed
                          </span>
                        ) : (
                          <span className="unreviewed-tag">Surfaced</span>
                        )}
                      </div>

                      <div className="episode-row__prices">
                        <span>
                          ₹{Number(ep.baseline_price || 0).toFixed(2)} → ₹{Number(ep.current_price || 0).toFixed(2)}
                        </span>
                        {epPct !== null && (
                          <span className={`episode-change-tag ${epIsUp ? 'val-positive' : epIsDown ? 'val-negative' : 'val-neutral'}`}>
                            {epIsUp ? '+' : ''}{epPct.toFixed(2)}%
                          </span>
                        )}
                        {ep.volume && (
                          <span className="episode-vol-tag">
                            Vol: {Number(ep.volume).toLocaleString('en-IN')}
                          </span>
                        )}
                      </div>

                      {ep.evidence_bullets && ep.evidence_bullets.length > 0 && (
                        <ul className="episode-row__bullets">
                          {ep.evidence_bullets.map((b, bIdx) => (
                            <li key={bIdx}>{b}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="timeline-empty">
              <span>No change episodes recorded for {nse_symbol} yet.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function App() {
  const [watchlists, setWatchlists] = useState([]);
  const [activeWatchlistId, setActiveWatchlistId] = useState(null);
  const [selectedStockId, setSelectedStockId] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [changesData, setChangesData] = useState(null);
  const [attentionData, setAttentionData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState(null);
  const [error, setError] = useState(null);

  // New watchlist creation state
  const [newWatchlistName, setNewWatchlistName] = useState('');

  // Instrument search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  // Load all watchlists
  const loadWatchlists = useCallback(async (selectId = null) => {
    try {
      setError(null);
      const data = await fetchWatchlists();
      setWatchlists(data);
      if (data.length > 0) {
        if (selectId && data.some((w) => w.id === selectId)) {
          setActiveWatchlistId(selectId);
        } else if (!activeWatchlistId || !data.some((w) => w.id === activeWatchlistId)) {
          setActiveWatchlistId(data[0].id);
        }
      } else {
        setActiveWatchlistId(null);
        setMarketData(null);
        setChangesData(null);
        setAttentionData(null);
      }
    } catch (err) {
      setError(err.message || 'Failed to load watchlists.');
    }
  }, [activeWatchlistId]);

  // Load market data for the active watchlist
  const loadMarketData = useCallback(async (wlId) => {
    if (!wlId) {
      setMarketData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWatchlistMarket(wlId);
      setMarketData(data);
    } catch (err) {
      setError(err.message || 'Failed to load market data.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load detected changes for the active watchlist
  const loadChangesData = useCallback(async (wlId) => {
    if (!wlId) {
      setChangesData(null);
      return;
    }
    try {
      const data = await fetchWatchlistChanges(wlId);
      setChangesData(data);
    } catch (err) {
      console.error('Failed to load candidate changes:', err);
    }
  }, []);

  // Load ranked attention feed for the active watchlist
  const loadAttentionData = useCallback(async (wlId) => {
    if (!wlId) {
      setAttentionData(null);
      return;
    }
    try {
      const data = await fetchWatchlistAttention(wlId);
      setAttentionData(data);
    } catch (err) {
      console.error('Failed to load attention feed:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadWatchlists();
  }, [loadWatchlists]);

  // Whenever active watchlist changes, load market data, changes, and attention
  useEffect(() => {
    if (activeWatchlistId) {
      loadMarketData(activeWatchlistId);
      loadChangesData(activeWatchlistId);
      loadAttentionData(activeWatchlistId);
    }
  }, [activeWatchlistId, loadMarketData, loadChangesData, loadAttentionData]);

  // Handle instrument search
  useEffect(() => {
    const trimmed = searchQuery.trim();
    if (!trimmed) {
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const results = await searchInstruments(trimmed);
        setSearchResults(results);
      } catch (err) {
        console.error('Search error:', err);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Action: Create watchlist
  const handleCreateWatchlist = async (e) => {
    e.preventDefault();
    if (!newWatchlistName.trim()) return;
    try {
      setError(null);
      const created = await createWatchlist(newWatchlistName.trim());
      setNewWatchlistName('');
      await loadWatchlists(created.id);
    } catch (err) {
      setError(err.message || 'Failed to create watchlist.');
    }
  };

  // Action: Delete watchlist
  const handleDeleteWatchlist = async (wlId) => {
    if (!window.confirm('Delete this watchlist?')) return;
    try {
      setError(null);
      await deleteWatchlist(wlId);
      await loadWatchlists();
    } catch (err) {
      setError(err.message || 'Failed to delete watchlist.');
    }
  };

  // Action: Add instrument
  const handleAddInstrument = async (instrument) => {
    if (!activeWatchlistId) return;
    try {
      setError(null);
      await addInstrumentToWatchlist(activeWatchlistId, instrument.id);
      setSearchQuery('');
      setSearchResults([]);
      await Promise.all([
        loadMarketData(activeWatchlistId),
        loadChangesData(activeWatchlistId),
        loadAttentionData(activeWatchlistId),
        loadWatchlists(activeWatchlistId),
      ]);
    } catch (err) {
      setError(err.message || 'Failed to add instrument.');
    }
  };

  // Action: Remove instrument
  const handleRemoveInstrument = async (instrumentId) => {
    if (!activeWatchlistId) return;
    try {
      setError(null);
      await removeInstrumentFromWatchlist(activeWatchlistId, instrumentId);
      await Promise.all([
        loadMarketData(activeWatchlistId),
        loadChangesData(activeWatchlistId),
        loadAttentionData(activeWatchlistId),
        loadWatchlists(activeWatchlistId),
      ]);
    } catch (err) {
      setError(err.message || 'Failed to remove instrument.');
    }
  };

  // Action: Mark Watchlist as Checked (advances baseline to current market snapshot)
  const handleCheckWatchlist = async () => {
    if (!activeWatchlistId) return;
    setChecking(true);
    setError(null);
    try {
      await checkWatchlist(activeWatchlistId);
      setRefreshMessage({
        type: 'info',
        text: 'Baseline updated to current market observation. All changes acknowledged.',
      });
      setTimeout(() => setRefreshMessage(null), 4000);
      await Promise.all([
        loadMarketData(activeWatchlistId),
        loadChangesData(activeWatchlistId),
        loadAttentionData(activeWatchlistId),
        loadWatchlists(activeWatchlistId),
      ]);
    } catch (err) {
      setError(err.message || 'Failed to record observation check.');
    } finally {
      setChecking(false);
    }
  };

  // Action: Ingest next sequential market observation session from NSE provider
  const handleRefreshMarketData = async () => {
    if (!activeWatchlistId) return;
    setRefreshing(true);
    setError(null);
    try {
      const res = await refreshWatchlistMarket(activeWatchlistId);
      setRefreshMessage({
        type: res.status === 'up_to_date' ? 'info' : 'success',
        text: res.message,
      });
      setTimeout(() => {
        setRefreshMessage(null);
      }, 6000);
      await Promise.all([
        loadMarketData(activeWatchlistId),
        loadChangesData(activeWatchlistId),
        loadAttentionData(activeWatchlistId),
      ]);
    } catch (err) {
      setError(err.message || 'Failed to refresh market data.');
    } finally {
      setRefreshing(false);
    }
  };

  // Action: Check for changes against current baseline without advancing baseline
  const handleCheckForChanges = async () => {
    if (!activeWatchlistId) return;
    setLoading(true);
    setError(null);
    try {
      await Promise.all([
        loadMarketData(activeWatchlistId),
        loadChangesData(activeWatchlistId),
        loadAttentionData(activeWatchlistId),
      ]);
    } catch (err) {
      setError(err.message || 'Failed to evaluate changes.');
    } finally {
      setLoading(false);
    }
  };

  // Action: Review single detected change
  const handleReviewChange = async (changeId) => {
    if (!activeWatchlistId) return;
    try {
      await reviewChange(activeWatchlistId, changeId);
      await Promise.all([
        loadAttentionData(activeWatchlistId),
        loadChangesData(activeWatchlistId),
      ]);
    } catch (err) {
      setError(err.message || 'Failed to review change.');
    }
  };

  // Action: Review all changes for an instrument
  const handleReviewInstrument = async (instrumentId) => {
    if (!activeWatchlistId) return;
    try {
      await reviewInstrumentChanges(activeWatchlistId, instrumentId);
      await Promise.all([
        loadAttentionData(activeWatchlistId),
        loadChangesData(activeWatchlistId),
      ]);
    } catch (err) {
      setError(err.message || 'Failed to review instrument changes.');
    }
  };

  // Action: Review all changes in the watchlist
  const handleReviewAll = async () => {
    if (!activeWatchlistId) return;
    try {
      await reviewAllWatchlistChanges(activeWatchlistId);
      setRefreshMessage({
        type: 'info',
        text: 'All surfaced changes marked as reviewed.',
      });
      setTimeout(() => setRefreshMessage(null), 3000);
      await Promise.all([
        loadAttentionData(activeWatchlistId),
        loadChangesData(activeWatchlistId),
      ]);
    } catch (err) {
      setError(err.message || 'Failed to review all changes.');
    }
  };

  const activeWatchlist = watchlists.find((w) => w.id === activeWatchlistId);

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="header">
        <div className="header__logo" aria-hidden="true">W</div>
        <span className="header__title">Smart Market Watchlist</span>
        <span className="header__badge">Dev User #1</span>
      </header>

      {/* Main workspace */}
      <main className="main-content">
        {/* Error notification */}
        {error && (
          <div className="alert alert-error" role="alert">
            {error}
          </div>
        )}

        {/* Watchlist Bar: Tabs & Create Form */}
        <section className="watchlist-bar" aria-label="Watchlist management">
          <div className="watchlist-tabs" role="tablist" aria-label="Available watchlists">
            {watchlists.length === 0 ? (
              <span className="val-neutral">No watchlists created yet. Create one to get started.</span>
            ) : (
              watchlists.map((wl) => (
                <button
                  key={wl.id}
                  role="tab"
                  aria-selected={wl.id === activeWatchlistId}
                  className={`tab-button ${wl.id === activeWatchlistId ? 'tab-button--active' : ''}`}
                  onClick={() => setActiveWatchlistId(wl.id)}
                >
                  {wl.name} ({wl.item_count})
                </button>
              ))
            )}
          </div>

          <form className="create-form" onSubmit={handleCreateWatchlist}>
            <input
              type="text"
              className="input-text"
              placeholder="New watchlist name..."
              value={newWatchlistName}
              onChange={(e) => setNewWatchlistName(e.target.value)}
              aria-label="New watchlist name"
            />
            <button type="submit" className="btn btn-primary" disabled={!newWatchlistName.trim()}>
              Create
            </button>
          </form>
        </section>

        {/* Stock Detail View OR Active Watchlist Details */}
        {selectedStockId ? (
          <StockDetailView
            instrumentId={selectedStockId}
            watchlistId={activeWatchlistId}
            onBack={() => {
              setSelectedStockId(null);
              if (activeWatchlistId) {
                loadAttentionData(activeWatchlistId);
                loadChangesData(activeWatchlistId);
                loadMarketData(activeWatchlistId);
              }
            }}
            onReview={async (instId) => {
              await handleReviewInstrument(instId);
            }}
          />
        ) : activeWatchlist ? (
          <section aria-label="Active watchlist view" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            {/* Header with Title and Actions */}
            <div className="section-header">
              <div>
                <h2 className="section-title">{activeWatchlist.name}</h2>
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleRefreshMarketData}
                  disabled={refreshing}
                  title="Ingest next chronological market observation session from NSE provider"
                >
                  {refreshing ? '🔄 Ingesting...' : '🔄 Refresh Market Data'}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleCheckForChanges}
                  disabled={loading}
                  title="Detect changes and evaluate attention against your last checked baseline"
                >
                  {loading ? '🔍 Evaluating...' : '🔍 Check for Changes'}
                </button>
                <button
                  type="button"
                  className="btn btn-check"
                  onClick={handleCheckWatchlist}
                  disabled={checking}
                  title="Acknowledge current market snapshot and advance baseline"
                >
                  {checking ? 'Updating...' : '✓ Mark as Checked'}
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => handleDeleteWatchlist(activeWatchlist.id)}
                >
                  Delete Watchlist
                </button>
              </div>
            </div>

            {/* Refresh / Status Alert Banner */}
            {refreshMessage && (
              <div className={`alert alert-${refreshMessage.type}`} role="status">
                {refreshMessage.text}
              </div>
            )}

            {/* Last Checked Persisted State Banner */}
            <div className="last-checked-banner">
              <div className="last-checked-banner__info">
                <span className={`last-checked-dot ${changesData?.last_checked_at ? '' : 'last-checked-dot--none'}`} />
                <span>
                  {changesData?.last_checked_at ? (
                    <>
                      <strong>Last checked:</strong> {formatDateTime(changesData.last_checked_at)}
                    </>
                  ) : (
                    <span className="val-neutral">
                      <strong>Last checked:</strong> Not checked yet (Click "Mark as Checked" to establish baseline)
                    </span>
                  )}
                </span>
              </div>
              {changesData?.summary && (
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                  {changesData.summary.instruments_with_changes} of {changesData.summary.total_instruments} instruments have candidate changes
                </div>
              )}
            </div>

            {/* SECTION: Ranked Attention Feed (Milestone 3 Core) */}
            <section className="attention-container" aria-label="Attention feed section">
              <div className="attention-header">
                <div className="attention-title">
                  <span>🎯</span>
                  <span>What Deserves Your Attention</span>
                </div>
                {attentionData?.summary && (
                  <div className="attention-pills">
                    {attentionData.summary.high_count > 0 && (
                      <span className="pill-count pill-count--high">
                        {attentionData.summary.high_count} High
                      </span>
                    )}
                    {attentionData.summary.medium_count > 0 && (
                      <span className="pill-count pill-count--medium">
                        {attentionData.summary.medium_count} Medium
                      </span>
                    )}
                    {attentionData.summary.low_count > 0 && (
                      <span className="pill-count pill-count--low">
                        {attentionData.summary.low_count} Low
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Attention Summary Bar */}
              {attentionData?.summary && (
                <div className="attention-summary-bar">
                  <div className="attention-summary-bar__main">
                    <strong>{attentionData.summary.attention_count ?? attentionData.summary.instruments_with_meaningful_changes}</strong> of{' '}
                    <strong>{attentionData.summary.total_instruments}</strong> stocks deserve your attention based on market evidence.
                    {attentionData.summary.unreviewed_count > 0 ? (
                      <span className="unreviewed-tag">
                        ({attentionData.summary.unreviewed_count} unreviewed)
                      </span>
                    ) : (attentionData.summary.attention_count > 0) ? (
                      <span className="all-reviewed-tag">
                        (✓ All reviewed)
                      </span>
                    ) : null}
                  </div>
                  <div className="attention-summary-bar__sub">
                    {(attentionData.summary.no_meaningful_change_count ?? attentionData.summary.instruments_without_meaningful_changes) > 0 && (
                      <span className="summary-quiet-text">
                        {attentionData.summary.no_meaningful_change_count ?? attentionData.summary.instruments_without_meaningful_changes}{' '}
                        {(attentionData.summary.no_meaningful_change_count ?? attentionData.summary.instruments_without_meaningful_changes) === 1 ? 'stock quiet' : 'stocks quiet'} (&lt; 0.20)
                      </span>
                    )}
                    {(attentionData.summary.insufficient_data_count ?? 0) > 0 && (
                      <span className="summary-insufficient-text">
                        ⚠️ {attentionData.summary.insufficient_data_count} {attentionData.summary.insufficient_data_count === 1 ? 'stock lacks' : 'stocks lack'} baseline or data
                      </span>
                    )}
                    {attentionData.summary.unreviewed_count > 0 && (
                      <button
                        type="button"
                        className="btn btn-review-all"
                        onClick={handleReviewAll}
                        title="Mark all surfaced changes across this watchlist as reviewed"
                      >
                        ✓ Mark all as reviewed
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Attention Items Grid */}
              {((attentionData?.items && attentionData.items.length > 0) || (attentionData?.attention_items && attentionData.attention_items.length > 0)) ? (
                <div className="attention-feed-grid">
                  {(attentionData.items || attentionData.attention_items).map((item) => {
                    const meta = getAttentionLevelMeta(item.significance_level);
                    const evidenceMeta = getEvidenceCompletenessMeta(item.evidence_completeness);
                    const pct = item.percentage_change !== undefined && item.percentage_change !== null
                      ? Number(item.percentage_change)
                      : (item.evidence?.price?.percentage_change !== undefined && item.evidence.price.percentage_change !== null
                        ? Number(item.evidence.price.percentage_change)
                        : null);
                    const abs = item.absolute_change !== undefined && item.absolute_change !== null
                      ? Number(item.absolute_change)
                      : (item.evidence?.price?.absolute_change !== undefined && item.evidence.price.absolute_change !== null
                        ? Number(item.evidence.price.absolute_change)
                        : null);
                    const isUp = pct !== null ? pct > 0 : false;
                    const isDown = pct !== null ? pct < 0 : false;
                    const structured = item.structured_explanation;

                    return (
                      <div key={item.instrument_id || item.instrument?.id} className={`attention-card ${meta.cardClass}`}>
                        <div className="attention-card__top">
                          <div>
                            <div
                              className="attention-card__symbol clickable-symbol"
                              onClick={() => setSelectedStockId(item.instrument_id || item.instrument?.id)}
                              title="Click to view detailed stock analysis, timeline, and evidence"
                            >
                              {item.symbol} ↗
                            </div>
                            <div className="attention-card__company">{item.company_name}</div>
                          </div>
                          <div className="attention-card__badges">
                            <button
                              type="button"
                              className="btn btn-secondary btn-detail-sm"
                              onClick={() => setSelectedStockId(item.instrument_id || item.instrument?.id)}
                              title="Inspect full details, timeline, and evidence"
                            >
                              Inspect
                            </button>
                            <span className={`attention-badge ${meta.badgeClass}`}>{meta.label}</span>
                            {evidenceMeta && (
                              <span
                                className={`evidence-badge ${evidenceMeta.badgeClass}`}
                                title={evidenceMeta.summary}
                              >
                                {evidenceMeta.label}
                              </span>
                            )}
                            <span className="attention-score-chip" title="Overall Significance Score (0.0 to 1.0)">
                              Score: {Number(item.overall_score).toFixed(2)}
                            </span>
                            {item.is_reviewed ? (
                              <span
                                className="review-status-badge review-status-badge--reviewed"
                                title={item.reviewed_at ? `Reviewed on ${formatDateTime(item.reviewed_at)}` : 'Reviewed'}
                              >
                                ✓ Reviewed
                              </span>
                            ) : (
                              <button
                                type="button"
                                className="btn btn-review-sm"
                                onClick={() => handleReviewInstrument(item.instrument_id || item.instrument?.id)}
                                title="Mark changes for this stock as reviewed"
                              >
                                Mark as reviewed
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Structured Explanation: What Happened & Why it Stands Out */}
                        <div className="attention-narrative">
                          <div className="attention-what-happened">
                            {structured?.what_happened || item.explanation}
                          </div>
                          {structured?.why_it_stands_out && (
                            <div className="attention-why-stands-out">
                              {structured.why_it_stands_out}
                            </div>
                          )}
                        </div>

                        {/* Supporting Evidence Bullets */}
                        {structured?.supporting_evidence && structured.supporting_evidence.length > 0 && (
                          <div className="attention-evidence-block">
                            <div className="attention-evidence-block__title">Corroborating Evidence:</div>
                            <ul className="attention-evidence-list">
                              {structured.supporting_evidence.map((bullet, idx) => (
                                <li key={idx} className="attention-evidence-bullet">
                                  {bullet}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Missing Data Disclosures */}
                        {structured?.missing_data_notes && structured.missing_data_notes.length > 0 && (
                          <div className="attention-missing-notes">
                            {structured.missing_data_notes.map((note, idx) => (
                              <span key={idx} className="missing-note-pill">
                                ℹ {note}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Collapsible Details & Provenance Accordion */}
                        <details className="attention-details">
                          <summary className="attention-details__summary">
                            <span>Why did this surface? / Details &amp; Provenance</span>
                          </summary>
                          <div className="attention-details__content">
                            {/* Baseline vs Current */}
                            <div className="details-metrics-row">
                              <div className="details-metric">
                                <span className="details-metric__label">Baseline Observation</span>
                                <span className="details-metric__val">₹{Number(item.baseline_price).toFixed(2)}</span>
                                <span className="details-metric__sub">{formatDateTime(item.baseline_timestamp || item.baseline_observed_at)}</span>
                              </div>
                              <div className="details-metric-arrow">→</div>
                              <div className="details-metric">
                                <span className="details-metric__label">Current Observation</span>
                                <span className="details-metric__val">₹{Number(item.current_price).toFixed(2)}</span>
                                <span className="details-metric__sub">{formatDateTime(item.current_timestamp || item.current_observed_at)}</span>
                              </div>
                              <div className="details-metric">
                                <span className="details-metric__label">Net Change</span>
                                <span className={`details-metric__val ${isUp ? 'val-positive' : isDown ? 'val-negative' : 'val-neutral'}`}>
                                  {pct !== null ? `${isUp ? '+' : ''}${pct.toFixed(2)}%` : '—'}
                                  {abs !== null ? ` (${isUp ? '+' : ''}₹${abs.toFixed(2)})` : ''}
                                </span>
                              </div>
                            </div>

                            {/* Component Score Contributions */}
                            <div className="component-scores-row">
                              <span style={{ fontWeight: '600', color: 'var(--color-text-primary)' }}>Component Scores:</span>
                              <span className="component-score-tag">
                                Magnitude: {item.component_scores?.magnitude !== null && item.component_scores?.magnitude !== undefined ? Number(item.component_scores.magnitude).toFixed(2) : 'N/A'} (w=35%)
                              </span>
                              <span className="component-score-tag">
                                Abnormality: {item.component_scores?.abnormality !== null && item.component_scores?.abnormality !== undefined ? Number(item.component_scores.abnormality).toFixed(2) : 'N/A'} (w=30%)
                              </span>
                              <span className="component-score-tag">
                                Relative: {item.component_scores?.relative_performance !== null && item.component_scores?.relative_performance !== undefined ? Number(item.component_scores.relative_performance).toFixed(2) : 'N/A'} (w=20%)
                              </span>
                              <span className="component-score-tag">
                                Volume: {item.component_scores?.volume !== null && item.component_scores?.volume !== undefined ? Number(item.component_scores.volume).toFixed(2) : 'N/A'} (w=15%)
                              </span>
                              <span className="component-score-tag">
                                Event: {item.component_scores?.event !== null && item.component_scores?.event !== undefined ? Number(item.component_scores.event).toFixed(2) : '0.00'} (w=10%)
                              </span>
                            </div>

                            {/* Underlying Candidate Changes with Individual Review */}
                            {item.changes && item.changes.length > 0 && (
                              <div className="details-changes-block">
                                <div style={{ fontWeight: '600', fontSize: '0.75rem', color: 'var(--color-text-primary)' }}>
                                  Underlying Signals Grouped in Episode:
                                </div>
                                <div className="details-changes-grid">
                                  {item.changes.map((ch) => (
                                    <div key={ch.id} className="underlying-change-row">
                                      <span className="constituent-tag">{ch.change_type}</span>
                                      <span className="underlying-change-status">
                                        {ch.review_status === 'reviewed' ? (
                                          <span className="val-positive" style={{ fontSize: '0.7rem', fontWeight: '600' }}>✓ Reviewed</span>
                                        ) : (
                                          <button
                                            type="button"
                                            className="btn btn-review-xs"
                                            onClick={() => handleReviewChange(ch.id)}
                                            title="Mark this signal as reviewed"
                                          >
                                            Review
                                          </button>
                                        )}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Freshness & Provenance */}
                            <div className="details-freshness">
                              {item.freshness_note || `Based on ${item.source || 'NSE'} market data through ${formatDateTime(item.current_timestamp || item.current_observed_at)}.`}
                            </div>
                          </div>
                        </details>

                        {/* Card Footer */}
                        <div className="attention-card__footer">
                          <div>
                            Tracking period: {formatDateTime(item.baseline_timestamp || item.baseline_observed_at)} to {formatDateTime(item.current_timestamp || item.current_observed_at)}
                          </div>
                          <span className="status-badge status-badge--final">
                            {item.source} • {item.data_status}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="changes-empty">
                  {attentionData?.last_checked_at ? (
                    <div>
                      <strong>All caught up!</strong> None of the stocks in this watchlist showed meaningful changes since you last checked ({formatDateTime(attentionData.last_checked_at)}). Any price movements remained within normal variance.
                    </div>
                  ) : (
                    <div>
                      <strong>No baseline established yet.</strong> Click <strong>"Mark as Checked"</strong> above to record your market observation baseline.
                    </div>
                  )}
                </div>
              )}

              {/* SECTION: Chronological Change Feed / Timeline View */}
              {attentionData?.feed_items && attentionData.feed_items.length > 0 && (
                <div className="timeline-section" aria-label="Chronological changes timeline">
                  <div className="timeline-header">
                    <div className="timeline-title">
                      <span>⏱️</span>
                      <span>Chronological Change Feed</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                      {attentionData.feed_items.length} detected event{attentionData.feed_items.length === 1 ? '' : 's'}
                    </div>
                  </div>

                  <div className="timeline-list">
                    {attentionData.feed_items.map((feedItem) => {
                      const typeMeta = getChangeTypeMeta(feedItem.change_type);
                      const levelMeta = getAttentionLevelMeta(feedItem.significance_level);
                      return (
                        <div key={feedItem.id} className={`timeline-card ${feedItem.is_reviewed ? 'timeline-card--reviewed' : ''}`}>
                          <div className="timeline-card__time">
                            {formatDateTime(feedItem.timestamp)}
                          </div>
                          <div className="timeline-card__body">
                            <div className="timeline-card__top">
                              <div className="timeline-card__stock">
                                <strong
                                  className="clickable-symbol"
                                  onClick={() => setSelectedStockId(feedItem.instrument_id)}
                                  title="Click to view detailed stock analysis"
                                >
                                  {feedItem.symbol} ↗
                                </strong>
                                <span className="timeline-card__company">{feedItem.company_name}</span>
                              </div>
                              <div className="timeline-card__badges">
                                <span className={`change-badge ${typeMeta.badgeClass}`}>{typeMeta.label}</span>
                                <span className={`attention-badge ${levelMeta.badgeClass}`}>{levelMeta.label}</span>
                                <span className="attention-score-chip">Score: {Number(feedItem.overall_score).toFixed(2)}</span>
                                {feedItem.is_reviewed ? (
                                  <span className="review-status-badge review-status-badge--reviewed">
                                    ✓ Reviewed
                                  </span>
                                ) : (
                                  <button
                                    type="button"
                                    className="btn btn-review-xs"
                                    onClick={() => handleReviewChange(feedItem.id)}
                                  >
                                    Mark reviewed
                                  </button>
                                )}
                              </div>
                            </div>

                            <div className="timeline-card__metrics">
                              {feedItem.metrics_summary}
                            </div>

                            {feedItem.explanation && (
                              <div className="timeline-card__explanation">
                                {feedItem.explanation}
                              </div>
                            )}

                            {feedItem.evidence_bullets && feedItem.evidence_bullets.length > 0 && (
                              <ul className="timeline-card__bullets">
                                {feedItem.evidence_bullets.map((b, idx) => (
                                  <li key={idx}>{b}</li>
                                ))}
                              </ul>
                            )}

                            <div className="timeline-card__footer">
                              <span>Tracking: {formatDateTime(feedItem.baseline_observed_at)} → {formatDateTime(feedItem.current_observed_at)}</span>
                              <span>{feedItem.source} • {feedItem.data_status}</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Quiet disclosure: Stocks evaluated without meaningful changes */}
              {((attentionData?.summary?.no_meaningful_change_count ?? attentionData?.summary?.instruments_without_meaningful_changes) > 0) && (
                <details className="quiet-panel">
                  <summary>
                    Quiet stocks ({attentionData.summary.no_meaningful_change_count ?? attentionData.summary.instruments_without_meaningful_changes} stocks had no meaningful changes)
                  </summary>
                  <div className="quiet-panel__content">
                    <p>
                      These stocks were evaluated against your baseline. Their movements were either nonexistent, negligible, or within normal historical variance and did not meet the attention threshold (Score &lt; 0.20).
                    </p>
                    {attentionData.quiet_instruments && attentionData.quiet_instruments.length > 0 && (
                      <div className="quiet-instruments-tags">
                        {attentionData.quiet_instruments.map((q) => (
                          <span
                            key={q.instrument_id}
                            className="quiet-tag clickable-tag"
                            onClick={() => setSelectedStockId(q.instrument_id)}
                            title={`${q.reason} — Click to inspect detail`}
                          >
                            {q.symbol} ↗
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </details>
              )}

              {/* Insufficient Data disclosure */}
              {(attentionData?.summary?.insufficient_data_count > 0) && (
                <details className="insufficient-panel">
                  <summary>
                    ⚠️ Insufficient data ({attentionData.summary.insufficient_data_count} stocks need baseline or data)
                  </summary>
                  <div className="insufficient-panel__content">
                    <p>
                      These instruments lack a recorded user observation baseline or sufficient historical data. Click &quot;Mark as Checked&quot; above to establish a baseline for tracking.
                    </p>
                    {attentionData.insufficient_data_instruments && attentionData.insufficient_data_instruments.length > 0 && (
                      <ul className="insufficient-list">
                        {attentionData.insufficient_data_instruments.map((ins) => (
                          <li key={ins.instrument_id}>
                            <strong
                              className="clickable-symbol"
                              onClick={() => setSelectedStockId(ins.instrument_id)}
                              title="Click to inspect detail"
                            >
                              {ins.symbol} ↗
                            </strong> ({ins.company_name}): {ins.reason}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </details>
              )}
            </section>

            {/* Technical Diagnostics & Candidate Changes Disclosure */}
            {changesData?.changes && changesData.changes.length > 0 && (
              <details className="diagnostics-panel">
                <summary>Underlying candidate detections ({changesData.changes.length} raw changes detected)</summary>
                <div className="changes-grid" style={{ marginTop: 'var(--space-3)' }}>
                  {changesData.changes.map((item) => {
                    const meta = getChangeTypeMeta(item.change_type);
                    return (
                      <div key={item.id} className="change-card">
                        <div className="change-card__head">
                          <div>
                            <div className="change-card__symbol">{item.symbol}</div>
                            <div className="change-card__company">{item.company_name}</div>
                          </div>
                          <span className={`change-badge ${meta.badgeClass}`}>{meta.label}</span>
                        </div>
                        <div className="change-card__comparison">
                          <div>Baseline: ₹{Number(item.baseline_price).toFixed(2)}</div>
                          <div>Current: ₹{Number(item.current_price).toFixed(2)}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </details>
            )}

            {/* Data Freshness & Diagnostics disclosure */}
            {changesData?.instrument_statuses && changesData.instrument_statuses.length > 0 && (
              <details className="diagnostics-panel">
                <summary>Data freshness & detection diagnostics ({changesData.instrument_statuses.length} instruments evaluated)</summary>
                <ul className="diagnostics-list">
                  {changesData.instrument_statuses.map((s) => (
                    <li key={s.instrument_id}>
                      <strong>{s.symbol}</strong>: Status: <code>{s.status}</code>
                      {s.diagnostics?.message && <span> &mdash; {s.diagnostics.message}</span>}
                      {s.diagnostics?.abnormal_return && (
                        <span> (Abnormal return: {s.diagnostics.abnormal_return.status})</span>
                      )}
                      {s.diagnostics?.relative_performance && (
                        <span> (Relative perf: {s.diagnostics.relative_performance.status})</span>
                      )}
                      {s.diagnostics?.volume_anomaly && (
                        <span> (Volume: {s.diagnostics.volume_anomaly.status})</span>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {/* Add Instrument Search Bar */}
            <div>
              <div className="search-box">
                <input
                  type="text"
                  className="input-text"
                  placeholder="Search 30+ NSE stocks (e.g., TATAMOTORS, BHARTIARTL, ITC, TCS)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Search instruments"
                />
                {searchResults.length > 0 && (
                  <div className="search-results" role="listbox">
                    {searchResults.map((inst) => {
                      const alreadyInList = marketData?.items?.some(
                        (it) => it.instrument_id === inst.id
                      );
                      return (
                        <div
                          key={inst.id}
                          className="search-item"
                          onClick={() => !alreadyInList && handleAddInstrument(inst)}
                        >
                          <div>
                            <div className="search-item__symbol">{inst.nse_symbol}</div>
                            <div className="search-item__name">{inst.company_name}</div>
                          </div>
                          {alreadyInList ? (
                            <span className="status-badge">Added</span>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-primary"
                              style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                            >
                              Add
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* SECTION: Current Watchlist Market Snapshot */}
            <section aria-label="Current market snapshot">
              <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: 'var(--space-2)' }}>
                Current Watchlist Snapshot
              </h3>
              <div className="table-container">
                {marketData?.items && marketData.items.length > 0 ? (
                  <table className="market-table">
                    <thead>
                      <tr>
                        <th>Instrument</th>
                        <th>Latest Price</th>
                        <th>Change</th>
                        <th>% Change</th>
                        <th>Volume</th>
                        <th>Observed At / Source</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {marketData.items.map((item) => {
                        const hasPrice = item.latest_price !== null && item.latest_price !== undefined;
                        const hasChange = item.absolute_change !== null && item.absolute_change !== undefined;
                        const isUp = hasChange && Number(item.absolute_change) > 0;
                        const isDown = hasChange && Number(item.absolute_change) < 0;

                        return (
                          <tr key={item.instrument_id}>
                            <td>
                              <div
                                className="stock-symbol clickable-symbol"
                                onClick={() => setSelectedStockId(item.instrument_id)}
                                title="Click to view full stock detail and change timeline"
                              >
                                {item.symbol} ↗
                              </div>
                              <div className="stock-name">{item.company_name}</div>
                            </td>
                            <td>
                              {hasPrice ? (
                                <strong>₹{Number(item.latest_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong>
                              ) : (
                                <span className="val-neutral">— Not observed yet</span>
                              )}
                            </td>
                            <td>
                              {hasChange ? (
                                <span className={isUp ? 'val-positive' : isDown ? 'val-negative' : 'val-neutral'}>
                                  {isUp ? '+' : ''}{Number(item.absolute_change).toFixed(2)}
                                </span>
                              ) : (
                                <span className="val-neutral">—</span>
                              )}
                            </td>
                            <td>
                              {item.percentage_change !== null && item.percentage_change !== undefined ? (
                                <span className={isUp ? 'val-positive' : isDown ? 'val-negative' : 'val-neutral'}>
                                  {isUp ? '+' : ''}{Number(item.percentage_change).toFixed(2)}%
                                </span>
                              ) : (
                                <span className="val-neutral">—</span>
                              )}
                            </td>
                            <td>
                              {item.volume !== null && item.volume !== undefined ? (
                                item.volume.toLocaleString('en-IN')
                              ) : (
                                <span className="val-neutral">—</span>
                              )}
                            </td>
                            <td>
                              {item.observed_at ? (
                                <div>
                                  <div>{formatDateTime(item.observed_at)}</div>
                                  <span className="status-badge status-badge--final">
                                    {item.source} • {item.data_status}
                                  </span>
                                </div>
                              ) : (
                                <span className="val-neutral">No observation</span>
                              )}
                            </td>
                            <td style={{ whiteSpace: 'nowrap' }}>
                              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                                <button
                                  type="button"
                                  className="btn btn-secondary"
                                  style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                                  onClick={() => setSelectedStockId(item.instrument_id)}
                                  title="Inspect full details, timeline, and evidence"
                                >
                                  Detail
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-danger"
                                  style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                                  onClick={() => handleRemoveInstrument(item.instrument_id)}
                                >
                                  Remove
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : (
                  <div className="empty-state">
                    <p>No instruments in this watchlist.</p>
                    <p style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
                      Use the search bar above to add stocks (e.g. TCS, RELIANCE, INFY).
                    </p>
                  </div>
                )}
              </div>
            </section>
          </section>
        ) : (
          <div className="empty-state">
            <h3>No watchlist selected</h3>
            <p style={{ marginTop: '0.5rem' }}>Create a watchlist above to begin tracking instruments.</p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="footer">
        Smart Market Watchlist &mdash; Milestone 6: Stock Detail + Change Timeline + Evidence &mdash; NSE CM-UDiFF Market Data (Historical EOD)
      </footer>
    </div>

  );
}

export default App;
