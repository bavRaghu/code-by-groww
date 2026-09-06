import { useState, useEffect, useCallback } from 'react';
import {
  ArrowLeft,
  Check,
  TrendingUp,
  TrendingDown,
  Clock,
  Shield,
  Layers,
  ExternalLink,
  Info,
  Activity,
  Sparkles,
  BarChart2,
  BookOpen,
} from 'lucide-react';
import StockChart from './StockChart';
import { fetchStockDetail } from '../api';

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
      return { label: level || 'Routine', badgeClass: 'attention-badge--none', cardClass: '' };
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

export default function StockDetailView({ instrumentId, watchlistId, onBack, onReview }) {
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
      <div className="stock-detail-loading" role="status">
        <div className="beacon-spinner" />
        <span>Loading stock intelligence for #{instrumentId}...</span>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="stock-detail-error" role="alert">
        <div className="alert alert-error">{error || 'Instrument intelligence not found.'}</div>
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          <ArrowLeft size={14} style={{ marginRight: '6px' }} />
          Back to Watchlist
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
    <div className="stock-detail-shell" aria-label={`Detail view for ${nse_symbol}`}>
      {/* Top Navigation & Stock Header */}
      <div className="stock-detail-top-nav">
        <button type="button" className="btn-back" onClick={onBack}>
          <ArrowLeft size={16} />
          <span>Back to Watchlist</span>
        </button>
      </div>

      <div className="stock-detail-header">
        <div className="stock-header-main">
          <div className="stock-identity">
            <span className="stock-symbol-badge">{nse_symbol}</span>
            <div className="stock-title-wrap">
              <h1 className="stock-company-name">{company_name}</h1>
              <div className="stock-meta-tags">
                <span className="meta-tag">{exchange || 'NSE'}</span>
                {sector && <span className="meta-tag">{sector}</span>}
                {isin && <span className="meta-tag meta-tag--mono">{isin}</span>}
              </div>
            </div>
          </div>

          <div className="stock-price-block">
            <div className="price-primary">
              {currentPrice !== null ? `₹${currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'}
            </div>
            {sessionPct !== null && (
              <div className={`price-delta ${sessionIsUp ? 'val-positive' : sessionIsDown ? 'val-negative' : 'val-neutral'}`}>
                {sessionIsUp ? <TrendingUp size={14} /> : sessionIsDown ? <TrendingDown size={14} /> : null}
                <span>
                  {sessionIsUp ? '+' : ''}{sessionPct.toFixed(2)}%
                  {sessionAbs !== null ? ` (${sessionIsUp ? '+' : ''}₹${sessionAbs.toFixed(2)})` : ''}
                </span>
                <span className="price-delta-context">today</span>
              </div>
            )}
            <div className="data-freshness-meta">
              <Clock size={11} />
              <span>{freshness_note || `Updated ${formatDateTime(current_observation?.observed_at)} · ${source || 'NSE'} (${data_status || 'verified'})`}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Since You Last Checked & Market Context */}
      <div className="stock-detail-grid">
        {/* Card: Since You Last Checked */}
        <div className="stock-detail-card syc-card">
          <div className="stock-detail-card__header">
            <div className="stock-detail-card__title">
              <Sparkles size={16} className="card-header-icon" />
              <span>Since You Last Checked</span>
            </div>
            <div className="stock-detail-card__actions">
              {since_last_checked?.is_reviewed ? (
                <span className="review-status-badge review-status-badge--reviewed">
                  <Check size={12} style={{ marginRight: '4px' }} />
                  Reviewed
                </span>
              ) : since_last_checked?.has_baseline ? (
                <button
                  type="button"
                  className="btn btn-review-sm"
                  onClick={handleReview}
                  disabled={reviewing}
                >
                  <Check size={13} style={{ marginRight: '4px' }} />
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
                    <span className="syc-point__label">Your Baseline State</span>
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
                      Significance: {Number(since_last_checked.overall_score || 0).toFixed(2)} / 1.00
                    </span>
                  </div>
                  <div className="syc-score-banner__status">
                    {since_last_checked.is_reviewed ? (
                      <span className="val-positive">
                        Acknowledged {since_last_checked.reviewed_at ? `on ${formatDateTime(since_last_checked.reviewed_at)}` : ''}
                      </span>
                    ) : (
                      <span className="unreviewed-tag">
                        Unreviewed movement since baseline
                      </span>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="syc-empty">
                <Info size={18} style={{ color: 'var(--beacon-gold)', marginBottom: '8px' }} />
                <strong>No user baseline recorded.</strong>
                <p>
                  You haven&apos;t established a baseline for this watchlist yet. Mark the watchlist as checked
                  to record your reference baseline for {nse_symbol}.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Card: Why This Was Flagged / Evidence Breakdown */}
      <div className="stock-detail-card evidence-card">
        <div className="stock-detail-card__header">
          <div className="stock-detail-card__title">
            <Shield size={16} className="card-header-icon" />
            <span>Why This Deserves Attention — Evidence Breakdown</span>
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
                  <div className="evidence-bullets-box__title">Corroborating Statistical Signals:</div>
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
                  <div className="evidence-components__title">Multi-Factor Weight Decomposition:</div>
                  <div className="evidence-components__grid">
                    <div className="component-pill">
                      <span className="component-pill__name">Magnitude</span>
                      <span className="component-pill__score">{Number(evidence.component_scores.magnitude ?? 0).toFixed(2)}</span>
                      <span className="component-pill__weight">25%</span>
                    </div>
                    <div className="component-pill">
                      <span className="component-pill__name">Abnormality</span>
                      <span className="component-pill__score">{Number(evidence.component_scores.abnormality ?? 0).toFixed(2)}</span>
                      <span className="component-pill__weight">25%</span>
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
                      <span className="component-pill__weight">15%</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Missing Data Disclosures */}
              {evidence.missing_data_notes && evidence.missing_data_notes.length > 0 && (
                <div className="evidence-missing-notes">
                  <div className="evidence-missing-notes__title">Data Completeness Disclosures:</div>
                  <div className="evidence-missing-tags">
                    {evidence.missing_data_notes.map((note, idx) => (
                      <span key={idx} className="missing-note-pill">
                        <Info size={11} style={{ marginRight: '4px' }} />
                        {note}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="evidence-quiet-state">
              <p>
                <strong>No abnormal movements detected for {nse_symbol}.</strong>
              </p>
              <p>
                Price and volume action remained within normal historical variance relative to your baseline.
                The significance score did not exceed the attention filter threshold (&lt; 0.20).
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Card: Supporting News Context (Marketaux) */}
      <div className="stock-detail-card news-card">
        <div className="stock-detail-card__header">
          <div className="stock-detail-card__title">
            <BookOpen size={16} className="card-header-icon" />
            <span>Supporting Contextual News</span>
          </div>
          <span className="status-badge status-badge--final">Marketaux News</span>
        </div>

        <div className="stock-detail-card__body">
          <div className="news-disclaimer">
            <Info size={13} style={{ marginRight: '6px', verticalAlign: '-1px' }} />
            <strong>Contextual Only:</strong> External news published around this market window. News provides qualitative context and does not constitute financial advice.
          </div>

          {detail.relevant_news?.articles && detail.relevant_news.articles.length > 0 ? (
            <div className="news-articles-list">
              {detail.relevant_news.articles.map((art, idx) => (
                <div key={art.id || art.provider_article_id || idx} className="news-article-item">
                  <div className="news-article-item__main">
                    <a
                      href={art.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="news-article-title"
                      title="Open original article in new tab"
                    >
                      <span>{art.headline}</span>
                      <ExternalLink size={12} className="link-icon" />
                    </a>
                    {art.summary && (
                      <div className="news-article-summary">{art.summary}</div>
                    )}
                    <div className="news-article-meta">
                      <span className="news-source">{art.source}</span>
                      <span>•</span>
                      <span className="news-time">{formatDateTime(art.published_at)}</span>
                      {art.relevance_summary && (
                        <>
                          <span>•</span>
                          <span className="news-rel-pill">{art.relevance_summary}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="news-empty-state">
              {detail.relevant_news?.note || 'No contextual news found around this observation window.'}
            </div>
          )}
        </div>
      </div>

      {/* Card: Price & Volume Trajectory */}
      <div className="stock-detail-card chart-card">
        <div className="stock-detail-card__header">
          <div className="stock-detail-card__title">
            <BarChart2 size={16} className="card-header-icon" />
            <span>Price &amp; Volume Trajectory</span>
          </div>
          <span className="status-badge">{historical_series?.length || 0} Historical Sessions</span>
        </div>

        <div className="stock-detail-card__body">
          <StockChart
            series={historical_series}
            baselinePrice={since_last_checked?.baseline_price}
            symbol={nse_symbol}
          />
        </div>
      </div>

      {/* Card: Change Episodes & Timeline */}
      <div className="stock-detail-card timeline-card-section">
        <div className="stock-detail-card__header">
          <div className="stock-detail-card__title">
            <Layers size={16} className="card-header-icon" />
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
                            <Check size={11} style={{ marginRight: '3px' }} />
                            Reviewed
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
