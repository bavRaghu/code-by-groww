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

function App() {
  const [watchlists, setWatchlists] = useState([]);
  const [activeWatchlistId, setActiveWatchlistId] = useState(null);
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

        {/* Active Watchlist Details */}
        {activeWatchlist ? (
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
                            <div className="attention-card__symbol">{item.symbol}</div>
                            <div className="attention-card__company">{item.company_name}</div>
                          </div>
                          <div className="attention-card__badges">
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
                                <strong>{feedItem.symbol}</strong>
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
                          <span key={q.instrument_id} className="quiet-tag" title={q.reason}>
                            {q.symbol}
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
                            <strong>{ins.symbol}</strong> ({ins.company_name}): {ins.reason}
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
                              <div className="stock-symbol">{item.symbol}</div>
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
                            <td>
                              <button
                                type="button"
                                className="btn btn-danger"
                                style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                                onClick={() => handleRemoveInstrument(item.instrument_id)}
                              >
                                Remove
                              </button>
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
        Smart Market Watchlist &mdash; Milestone 5: Smart Attention + Change Feed &mdash; NSE CM-UDiFF Market Data (Historical EOD)
      </footer>
    </div>

  );
}

export default App;
