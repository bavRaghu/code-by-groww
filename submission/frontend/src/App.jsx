import { useState, useEffect, useCallback } from 'react';
import './App.css';
import {
  Sparkles,
  Clock,
  Activity,
  TrendingUp,
  TrendingDown,
  Search,
  RefreshCw,
  Check,
  Trash2,
  Plus,
  LogOut,
  ExternalLink,
  AlertCircle,
  Shield,
  ArrowUpRight,
  Filter,
  CheckCircle2,
  ChevronRight,
  BookOpen,
  Info,
} from 'lucide-react';
import LandingPage from './components/LandingPage';
import AuthView from './components/AuthView';
import StockDetailView from './components/StockDetailView';
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
  loginUser,
  fetchCurrentUser,
  logoutUser,
  getAuthToken,
  clearAuthToken,
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



function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authViewOpen, setAuthViewOpen] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState(null);

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

  // Attention feed filter
  const [attentionFilter, setAttentionFilter] = useState('all'); // 'all' | 'high' | 'unreviewed'

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

  // Check auth session on startup
  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      setAuthLoading(false);
      return;
    }
    fetchCurrentUser()
      .then((user) => {
        setCurrentUser(user);
      })
      .catch(() => {
        clearAuthToken();
        setCurrentUser(null);
      })
      .finally(() => {
        setAuthLoading(false);
      });

    const onUnauthorized = () => {
      clearAuthToken();
      setCurrentUser(null);
    };
    window.addEventListener('auth:unauthorized', onUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', onUnauthorized);
  }, []);

  const handleLogout = async () => {
    try {
      await logoutUser();
    } catch {
      clearAuthToken();
    }
    setCurrentUser(null);
    setWatchlists([]);
    setActiveWatchlistId(null);
    setSelectedStockId(null);
    setMarketData(null);
    setChangesData(null);
    setAttentionData(null);
    setAuthViewOpen(false);
  };

  const handleDemoLogin = async () => {
    setDemoLoading(true);
    setDemoError(null);
    try {
      const data = await loginUser('dev@example.com', 'password123');
      setCurrentUser(data.user);
      setAuthViewOpen(false);
    } catch (err) {
      setDemoError(err.message || 'Demo login failed. Make sure the backend server is running.');
    } finally {
      setDemoLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    if (currentUser) {
      loadWatchlists();
    }
  }, [currentUser, loadWatchlists]);

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
      setSearchResults([]);
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

  // Unauthenticated loading
  if (authLoading) {
    return (
      <div className="beacon-loading-shell">
        <div className="beacon-spinner" />
        <p className="beacon-loading-text">Resolving session...</p>
      </div>
    );
  }

  // Unauthenticated visitor view
  if (!currentUser) {
    if (authViewOpen) {
      return (
        <AuthView
          initialMode={authMode}
          onLoginSuccess={(user) => {
            setCurrentUser(user);
            setAuthViewOpen(false);
          }}
          onBackToLanding={() => setAuthViewOpen(false)}
        />
      );
    }
    return (
      <LandingPage
        onOpenAuth={(mode) => {
          setAuthMode(mode || 'login');
          setAuthViewOpen(true);
        }}
        onDemoLogin={handleDemoLogin}
        demoLoading={demoLoading}
        demoError={demoError}
      />
    );
  }

  // Filter items for attention feed
  const rawAttentionItems = attentionData?.items || attentionData?.attention_items || [];
  const filteredAttentionItems = rawAttentionItems.filter((item) => {
    if (attentionFilter === 'high') {
      return item.significance_level === 'HIGH';
    }
    if (attentionFilter === 'unreviewed') {
      return !item.is_reviewed;
    }
    return true;
  });

  return (
    <div className="beacon-app-shell">
      {/* Beacon Brand Header */}
      <header className="beacon-header">
        <div className="beacon-header__brand">
          <div className="beacon-brand-mark" aria-hidden="true">
            <span className="beacon-brand-dot" />
          </div>
          <div className="brand-text-wrap">
            <span className="beacon-wordmark">BEACON</span>
            <span className="beacon-header-tagline">Know what deserves your attention.</span>
          </div>
        </div>

        <div className="beacon-header__user-block">
          <div className="beacon-user-pill" title="Current authenticated account">
            <span className="user-dot" />
            <span className="user-label">{currentUser.name || currentUser.email}</span>
          </div>
          <button
            type="button"
            className="beacon-btn beacon-btn--ghost-sm"
            onClick={handleLogout}
            title="Log out of current session"
          >
            <LogOut size={13} style={{ marginRight: '5px' }} />
            <span>Log Out</span>
          </button>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="beacon-main">
        {/* Error notification banner */}
        {error && (
          <div className="beacon-alert beacon-alert--error" role="alert">
            <AlertCircle size={16} className="alert-icon" />
            <span>{error}</span>
          </div>
        )}

        {/* Watchlist Bar: Tabs & Create Form */}
        <section className="beacon-watchlist-bar" aria-label="Watchlist management">
          <div className="beacon-watchlist-tabs" role="tablist" aria-label="Available watchlists">
            {watchlists.length === 0 ? (
              <span className="val-neutral">No watchlists created yet. Create one to get started.</span>
            ) : (
              watchlists.map((wl) => (
                <button
                  key={wl.id}
                  role="tab"
                  aria-selected={wl.id === activeWatchlistId}
                  className={`beacon-wl-tab ${wl.id === activeWatchlistId ? 'beacon-wl-tab--active' : ''}`}
                  onClick={() => setActiveWatchlistId(wl.id)}
                >
                  <span className="wl-name">{wl.name}</span>
                  <span className="wl-count">{wl.item_count}</span>
                </button>
              ))
            )}
          </div>

          <form className="beacon-create-form" onSubmit={handleCreateWatchlist}>
            <input
              type="text"
              className="beacon-input beacon-input--sm"
              placeholder="New watchlist name..."
              value={newWatchlistName}
              onChange={(e) => setNewWatchlistName(e.target.value)}
              aria-label="New watchlist name"
            />
            <button
              type="submit"
              className="beacon-btn beacon-btn--primary-sm"
              disabled={!newWatchlistName.trim()}
            >
              <Plus size={13} style={{ marginRight: '4px' }} />
              <span>Create</span>
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
          <div className="beacon-workspace-stack">
            {/* Active Watchlist Controls Bar */}
            <div className="active-wl-toolbar">
              <div className="toolbar-title-wrap">
                <h2 className="active-wl-title">{activeWatchlist.name}</h2>
                <span className="active-wl-meta">
                  {marketData?.items?.length || 0} securities tracked
                </span>
              </div>

              <div className="toolbar-actions">
                <button
                  type="button"
                  className="beacon-btn beacon-btn--secondary"
                  onClick={handleRefreshMarketData}
                  disabled={refreshing}
                  title="Ingest next sequential market observation session from NSE"
                >
                  <RefreshCw size={14} className={refreshing ? 'beacon-spin' : ''} style={{ marginRight: '6px' }} />
                  <span>{refreshing ? 'Ingesting...' : 'Ingest Market Session'}</span>
                </button>
                <button
                  type="button"
                  className="beacon-btn beacon-btn--secondary"
                  onClick={handleCheckForChanges}
                  disabled={loading}
                  title="Detect changes against your last checked baseline"
                >
                  <Search size={14} style={{ marginRight: '6px' }} />
                  <span>{loading ? 'Evaluating...' : 'Check for Changes'}</span>
                </button>
                <button
                  type="button"
                  className="beacon-btn beacon-btn--check"
                  onClick={handleCheckWatchlist}
                  disabled={checking}
                  title="Advance your observation baseline to the current market snapshot"
                >
                  <Check size={14} style={{ marginRight: '6px' }} />
                  <span>{checking ? 'Advancing...' : 'Advance Baseline'}</span>
                </button>
                <button
                  type="button"
                  className="beacon-btn beacon-btn--danger-icon"
                  onClick={() => handleDeleteWatchlist(activeWatchlist.id)}
                  title="Delete Watchlist"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>

            {/* Refresh / Status Banner */}
            {refreshMessage && (
              <div className={`beacon-alert beacon-alert--${refreshMessage.type}`} role="status">
                <CheckCircle2 size={16} className="alert-icon" />
                <span>{refreshMessage.text}</span>
              </div>
            )}

            {/* FOCAL CARD: "Since You Last Checked" (The Signature Beacon Experience) */}
            <section className="beacon-focal-card" aria-label="Since you last checked focal summary">
              <div className="focal-card-glow" />
              <div className="focal-card-inner">
                <div className="focal-card__top">
                  <div className="focal-badge">
                    <Sparkles size={13} style={{ color: 'var(--beacon-gold)', marginRight: '5px' }} />
                    <span>SINCE YOU LAST CHECKED</span>
                  </div>
                  <div className="focal-timestamps">
                    <div className="focal-time-item">
                      <Clock size={12} style={{ marginRight: '4px' }} />
                      <span>
                        <strong>Baseline:</strong>{' '}
                        {changesData?.last_checked_at
                          ? formatDateTime(changesData.last_checked_at)
                          : 'Not checked yet'}
                      </span>
                    </div>
                    {marketData?.items?.[0]?.observed_at && (
                      <>
                        <span className="time-arrow">→</span>
                        <div className="focal-time-item">
                          <Activity size={12} style={{ marginRight: '4px' }} />
                          <span>
                            <strong>Current Market:</strong>{' '}
                            {formatDateTime(marketData.items[0].observed_at)}
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                <div className="focal-card__stats">
                  <div className="focal-stat-primary">
                    <span className="stat-number">
                      {attentionData?.summary?.attention_count ?? attentionData?.summary?.instruments_with_meaningful_changes ?? 0}
                    </span>
                    <span className="stat-label">
                      {(attentionData?.summary?.attention_count ?? 0) === 1 ? 'stock deserves' : 'stocks deserve'} your attention
                    </span>
                  </div>

                  <div className="focal-stats-secondary">
                    <div className="sec-stat-item">
                      <span className="sec-number">
                        {attentionData?.summary?.no_meaningful_change_count ?? attentionData?.summary?.instruments_without_meaningful_changes ?? 0}
                      </span>
                      <span className="sec-label">stocks quiet / filtered as noise</span>
                    </div>
                    {attentionData?.summary?.unreviewed_count > 0 && (
                      <div className="sec-stat-item sec-stat-item--unreviewed">
                        <span className="sec-number">{attentionData.summary.unreviewed_count}</span>
                        <span className="sec-label">unreviewed signals</span>
                      </div>
                    )}
                    {(attentionData?.summary?.insufficient_data_count ?? 0) > 0 && (
                      <div className="sec-stat-item sec-stat-item--insufficient">
                        <span className="sec-number">{attentionData.summary.insufficient_data_count}</span>
                        <span className="sec-label">stocks need baseline</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Filter pills & Mark all reviewed action */}
                <div className="focal-card__filter-bar">
                  <div className="focal-filters" role="tablist">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={attentionFilter === 'all'}
                      className={`focal-filter-btn ${attentionFilter === 'all' ? 'focal-filter-btn--active' : ''}`}
                      onClick={() => setAttentionFilter('all')}
                    >
                      <Filter size={12} style={{ marginRight: '4px' }} />
                      <span>All Deserving Attention ({rawAttentionItems.length})</span>
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={attentionFilter === 'high'}
                      className={`focal-filter-btn ${attentionFilter === 'high' ? 'focal-filter-btn--active' : ''}`}
                      onClick={() => setAttentionFilter('high')}
                    >
                      <span>High Priority ({attentionData?.summary?.high_count || 0})</span>
                    </button>
                    {attentionData?.summary?.unreviewed_count > 0 && (
                      <button
                        type="button"
                        role="tab"
                        aria-selected={attentionFilter === 'unreviewed'}
                        className={`focal-filter-btn ${attentionFilter === 'unreviewed' ? 'focal-filter-btn--active' : ''}`}
                        onClick={() => setAttentionFilter('unreviewed')}
                      >
                        <span>Unreviewed Only ({attentionData.summary.unreviewed_count})</span>
                      </button>
                    )}
                  </div>

                  {attentionData?.summary?.unreviewed_count > 0 && (
                    <button
                      type="button"
                      className="beacon-btn beacon-btn--ghost-sm btn-mark-all"
                      onClick={handleReviewAll}
                      title="Mark all surfaced changes across this watchlist as reviewed"
                    >
                      <Check size={13} style={{ marginRight: '4px' }} />
                      <span>Mark all as reviewed</span>
                    </button>
                  )}
                </div>
              </div>
            </section>

            {/* SECTION: Ranked Attention Feed */}
            <section className="beacon-attention-feed" aria-label="Prioritized attention feed">
              <div className="section-eyebrow">
                <Shield size={14} style={{ marginRight: '6px' }} />
                <span>WHAT DESERVES YOUR ATTENTION (RANKED BY EVIDENCE)</span>
              </div>

              {filteredAttentionItems.length > 0 ? (
                <div className="attention-feed-cards">
                  {filteredAttentionItems.map((item) => {
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
                    const instId = item.instrument_id || item.instrument?.id;

                    return (
                      <div key={instId} className={`beacon-attention-card ${meta.cardClass}`}>
                        {/* Top Header: Symbol, Badges, Review */}
                        <div className="card-top-row">
                          <div className="stock-identity-group">
                            <button
                              type="button"
                              className="symbol-link-btn"
                              onClick={() => setSelectedStockId(instId)}
                              title="Click to view full stock detail and change timeline"
                            >
                              <span className="symbol-text">{item.symbol}</span>
                              <ArrowUpRight size={14} className="arrow-icon" />
                            </button>
                            <span className="company-text">{item.company_name}</span>
                          </div>

                          <div className="card-badges-group">
                            <span className={`attention-badge ${meta.badgeClass}`}>{meta.label}</span>
                            {evidenceMeta && (
                              <span className={`evidence-badge ${evidenceMeta.badgeClass}`} title={evidenceMeta.summary}>
                                {evidenceMeta.label}
                              </span>
                            )}
                            <span className="score-chip" title="Multi-factor Significance Score (0.0 to 1.0)">
                              Score: {Number(item.overall_score).toFixed(2)}
                            </span>

                            {item.is_reviewed ? (
                              <span className="review-tag review-tag--reviewed" title="Reviewed">
                                <Check size={11} style={{ marginRight: '3px' }} />
                                Reviewed
                              </span>
                            ) : (
                              <button
                                type="button"
                                className="beacon-btn beacon-btn--review-sm"
                                onClick={() => handleReviewInstrument(instId)}
                                title="Mark all changes for this stock as reviewed"
                              >
                                <Check size={12} style={{ marginRight: '3px' }} />
                                <span>Mark Reviewed</span>
                              </button>
                            )}

                            <button
                              type="button"
                              className="beacon-btn beacon-btn--inspect-sm"
                              onClick={() => setSelectedStockId(instId)}
                              title="Inspect full details, timeline, and evidence"
                            >
                              <span>Inspect</span>
                              <ChevronRight size={13} />
                            </button>
                          </div>
                        </div>

                        {/* Price & Movement Row */}
                        <div className="card-metrics-row">
                          <div className="metric-box">
                            <span className="metric-box__label">Current Price</span>
                            <span className="metric-box__val">₹{Number(item.current_price).toFixed(2)}</span>
                          </div>
                          <div className="metric-box">
                            <span className="metric-box__label">Change Since Check</span>
                            <span className={`metric-box__val ${isUp ? 'val-positive' : isDown ? 'val-negative' : 'val-neutral'}`}>
                              {isUp ? <TrendingUp size={13} style={{ marginRight: '3px', verticalAlign: '-1px' }} /> : isDown ? <TrendingDown size={13} style={{ marginRight: '3px', verticalAlign: '-1px' }} /> : null}
                              {pct !== null ? `${isUp ? '+' : ''}${pct.toFixed(2)}%` : '—'}
                              {abs !== null ? ` (${isUp ? '+' : ''}₹${abs.toFixed(2)})` : ''}
                            </span>
                          </div>
                          <div className="metric-box">
                            <span className="metric-box__label">Baseline Price</span>
                            <span className="metric-box__val val-muted">₹{Number(item.baseline_price).toFixed(2)}</span>
                          </div>
                        </div>

                        {/* "Why This Matters" Explanation */}
                        <div className="card-explanation-box">
                          <div className="explanation-headline">
                            <Sparkles size={13} style={{ color: 'var(--beacon-gold)', marginRight: '5px' }} />
                            <strong>Why this deserves attention:</strong>
                          </div>
                          <p className="explanation-paragraph">
                            {item.structured_explanation?.what_happened || item.explanation || item.why_it_matters}
                          </p>
                          {item.structured_explanation?.why_it_stands_out && (
                            <p className="explanation-stands-out">
                              {item.structured_explanation.why_it_stands_out}
                            </p>
                          )}

                          {item.evidence_bullets && item.evidence_bullets.length > 0 && (
                            <ul className="evidence-bullet-list">
                              {item.evidence_bullets.map((b, bIdx) => (
                                <li key={bIdx}>{b}</li>
                              ))}
                            </ul>
                          )}
                        </div>

                        {/* Contextual Marketaux News Preview if available */}
                        {item.relevant_news?.articles && item.relevant_news.articles.length > 0 && (
                          <div className="card-news-context">
                            <div className="news-context-head">
                              <BookOpen size={12} style={{ marginRight: '5px' }} />
                              <span>Relevant Marketaux News Context</span>
                            </div>
                            <div className="news-articles-wrap">
                              {item.relevant_news.articles.slice(0, 2).map((art, aIdx) => (
                                <div key={aIdx} className="news-item-row">
                                  <a
                                    href={art.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="news-item-link"
                                    title="Read article on original publisher"
                                  >
                                    <span>{art.headline}</span>
                                    <ExternalLink size={11} className="ext-icon" />
                                  </a>
                                  <div className="news-item-meta">
                                    <span>{art.source}</span>
                                    <span>•</span>
                                    <span>{formatDateTime(art.published_at)}</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Collapsible Provenance & Diagnostic Accordion */}
                        <details className="card-details-accordion">
                          <summary className="accordion-summary">
                            <span>Diagnostic Breakdown &amp; Provenance</span>
                          </summary>
                          <div className="accordion-body">
                            <div className="provenance-metric-grid">
                              <div className="prov-item">
                                <span className="prov-label">Magnitude Factor (35%)</span>
                                <span className="prov-val">{Number(item.component_scores?.magnitude ?? 0).toFixed(2)}</span>
                              </div>
                              <div className="prov-item">
                                <span className="prov-label">Abnormality Factor (30%)</span>
                                <span className="prov-val">{Number(item.component_scores?.abnormality ?? 0).toFixed(2)}</span>
                              </div>
                              <div className="prov-item">
                                <span className="prov-label">Relative Perf (20%)</span>
                                <span className="prov-val">{Number(item.component_scores?.relative_performance ?? 0).toFixed(2)}</span>
                              </div>
                              <div className="prov-item">
                                <span className="prov-label">Volume Anomaly (15%)</span>
                                <span className="prov-val">{Number(item.component_scores?.volume ?? 0).toFixed(2)}</span>
                              </div>
                            </div>

                            {item.changes && item.changes.length > 0 && (
                              <div className="underlying-signals-section">
                                <div className="signals-title">Underlying Signals Grouped in Episode:</div>
                                <div className="signals-grid">
                                  {item.changes.map((ch) => (
                                    <div key={ch.id} className="signal-chip-row">
                                      <span className="signal-badge">{ch.change_type}</span>
                                      {ch.review_status === 'reviewed' ? (
                                        <span className="review-tag review-tag--reviewed">Reviewed</span>
                                      ) : (
                                        <button
                                          type="button"
                                          className="beacon-btn beacon-btn--review-xs"
                                          onClick={() => handleReviewChange(ch.id)}
                                        >
                                          Review
                                        </button>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            <div className="prov-footer">
                              <span>Tracking: {formatDateTime(item.baseline_timestamp || item.baseline_observed_at)} → {formatDateTime(item.current_timestamp || item.current_observed_at)}</span>
                              <span>Source: {item.source || 'NSE'} &bull; Status: {item.data_status || 'verified'}</span>
                            </div>
                          </div>
                        </details>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="beacon-empty-card">
                  <CheckCircle2 size={24} style={{ color: 'var(--beacon-gold)', marginBottom: '8px' }} />
                  {attentionFilter === 'high' ? (
                    <div>
                      <strong>No high-priority attention items.</strong> All detected movements in this watchlist are medium, low, or within expected variance.
                    </div>
                  ) : attentionFilter === 'unreviewed' ? (
                    <div>
                      <strong>All caught up!</strong> Every surfaced signal across this watchlist has been reviewed.
                    </div>
                  ) : attentionData?.last_checked_at ? (
                    <div>
                      <strong>No attention needed.</strong> All {attentionData?.summary?.total_instruments || 'active'} stocks in this watchlist remained within normal variance since you last checked ({formatDateTime(attentionData.last_checked_at)}).
                    </div>
                  ) : (
                    <div>
                      <strong>No baseline established yet.</strong> Click <strong>&quot;Advance Baseline&quot;</strong> above to record your market reference state.
                    </div>
                  )}
                </div>
              )}

              {/* Quiet Stocks Disclosure */}
              {((attentionData?.summary?.no_meaningful_change_count ?? attentionData?.summary?.instruments_without_meaningful_changes) > 0) && (
                <details className="beacon-quiet-panel">
                  <summary className="quiet-summary">
                    <span>Quiet stocks ({attentionData.summary.no_meaningful_change_count ?? attentionData.summary.instruments_without_meaningful_changes} stocks with changes below 0.20 threshold)</span>
                  </summary>
                  <div className="quiet-content">
                    <p className="quiet-explainer">
                      These stocks were evaluated against your baseline. Their movements were either nonexistent or well within normal statistical variance. Beacon suppressed them to protect your focus.
                    </p>
                    {attentionData.quiet_instruments && attentionData.quiet_instruments.length > 0 && (
                      <div className="quiet-tags-list">
                        {attentionData.quiet_instruments.map((q) => (
                          <button
                            key={q.instrument_id}
                            type="button"
                            className="quiet-tag-btn"
                            onClick={() => setSelectedStockId(q.instrument_id)}
                            title={`${q.reason} — Click to inspect detail`}
                          >
                            <span>{q.symbol}</span>
                            <ArrowUpRight size={11} />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </details>
              )}

              {/* Insufficient Data Disclosure */}
              {(attentionData?.summary?.insufficient_data_count > 0) && (
                <details className="beacon-insufficient-panel">
                  <summary className="insufficient-summary">
                    <Info size={13} style={{ marginRight: '6px', color: 'var(--beacon-gold)' }} />
                    <span>Insufficient data ({attentionData.summary.insufficient_data_count} stocks need baseline or data)</span>
                  </summary>
                  <div className="insufficient-content">
                    <p className="quiet-explainer">
                      These instruments lack a recorded user observation baseline or sufficient historical data. Click &quot;Advance Baseline&quot; above to establish a baseline for tracking.
                    </p>
                    {attentionData.insufficient_data_instruments && attentionData.insufficient_data_instruments.length > 0 && (
                      <ul className="insufficient-list">
                        {attentionData.insufficient_data_instruments.map((ins) => (
                          <li key={ins.instrument_id}>
                            <button
                              type="button"
                              className="symbol-text-btn"
                              onClick={() => setSelectedStockId(ins.instrument_id)}
                            >
                              {ins.symbol}
                            </button>{' '}
                            <span className="ins-name">({ins.company_name})</span>: {ins.reason}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </details>
              )}
            </section>

            {/* SECTION: Compact Watchlist Table */}
            <section className="beacon-table-section" aria-label="Current watchlist market snapshot">
              <div className="table-section-head">
                <div className="section-eyebrow">
                  <Activity size={14} style={{ marginRight: '6px' }} />
                  <span>WATCHLIST INSTRUMENTS ({marketData?.items?.length || 0})</span>
                </div>

                {/* Search & Add Bar */}
                <div className="table-search-bar">
                  <Search size={14} className="search-icon" />
                  <input
                    type="text"
                    className="beacon-input beacon-input--search"
                    placeholder="Search 1,200+ NSE stocks (e.g. TATAMOTORS, BHARTIARTL, ITC)..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    aria-label="Search NSE instruments"
                  />
                  {searchResults.length > 0 && (
                    <div className="search-results-dropdown" role="listbox">
                      {searchResults.map((inst) => {
                        const alreadyInList = marketData?.items?.some(
                          (it) => it.instrument_id === inst.id
                        );
                        return (
                          <div
                            key={inst.id}
                            className="search-dropdown-item"
                            onClick={() => !alreadyInList && handleAddInstrument(inst)}
                          >
                            <div className="item-details">
                              <span className="item-symbol">{inst.nse_symbol}</span>
                              <span className="item-name">{inst.company_name}</span>
                            </div>
                            {alreadyInList ? (
                              <span className="status-badge">Added</span>
                            ) : (
                              <button
                                type="button"
                                className="beacon-btn beacon-btn--primary-xs"
                              >
                                <Plus size={11} style={{ marginRight: '2px' }} />
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

              {/* Scannable Compact Table */}
              <div className="beacon-table-wrap">
                {marketData?.items && marketData.items.length > 0 ? (
                  <table className="beacon-market-table">
                    <thead>
                      <tr>
                        <th>Instrument</th>
                        <th>Latest Price</th>
                        <th>Session Change</th>
                        <th>% Change</th>
                        <th>Session Volume</th>
                        <th>Observation Time</th>
                        <th style={{ textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {marketData.items.map((item) => {
                        const hasPrice = item.latest_price !== null && item.latest_price !== undefined;
                        const hasChange = item.absolute_change !== null && item.absolute_change !== undefined;
                        const isUp = hasChange && Number(item.absolute_change) > 0;
                        const isDown = hasChange && Number(item.absolute_change) < 0;

                        return (
                          <tr key={item.instrument_id} className="table-row-interactive">
                            <td>
                              <button
                                type="button"
                                className="table-symbol-btn"
                                onClick={() => setSelectedStockId(item.instrument_id)}
                                title="Click to view full detail"
                              >
                                <strong>{item.symbol}</strong>
                                <ArrowUpRight size={11} className="arrow-icon" />
                              </button>
                              <div className="table-company-name">{item.company_name}</div>
                            </td>
                            <td>
                              {hasPrice ? (
                                <span className="price-bold">
                                  ₹{Number(item.latest_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                </span>
                              ) : (
                                <span className="val-neutral">—</span>
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
                                <span className={`table-pct-badge ${isUp ? 'pct-badge--up' : isDown ? 'pct-badge--down' : ''}`}>
                                  {isUp ? '+' : ''}{Number(item.percentage_change).toFixed(2)}%
                                </span>
                              ) : (
                                <span className="val-neutral">—</span>
                              )}
                            </td>
                            <td>
                              {item.volume !== null && item.volume !== undefined ? (
                                <span className="vol-text">{Number(item.volume).toLocaleString('en-IN')}</span>
                              ) : (
                                <span className="val-neutral">—</span>
                              )}
                            </td>
                            <td>
                              {item.observed_at ? (
                                <div className="table-obs-time">
                                  <div>{formatDateTime(item.observed_at)}</div>
                                  <span className="status-badge status-badge--final">
                                    {item.source}
                                  </span>
                                </div>
                              ) : (
                                <span className="val-neutral">No data</span>
                              )}
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              <div className="table-actions-cell">
                                <button
                                  type="button"
                                  className="beacon-btn beacon-btn--ghost-xs"
                                  onClick={() => setSelectedStockId(item.instrument_id)}
                                  title="Inspect full details and timeline"
                                >
                                  Inspect
                                </button>
                                <button
                                  type="button"
                                  className="beacon-btn beacon-btn--danger-xs"
                                  onClick={() => handleRemoveInstrument(item.instrument_id)}
                                  title="Remove from watchlist"
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
                  <div className="beacon-empty-table">
                    <p>No instruments in this watchlist.</p>
                    <p className="empty-sub">
                      Use the search bar above to add stocks (e.g. TATAMOTORS, TCS, RELIANCE, INFY).
                    </p>
                  </div>
                )}
              </div>
            </section>
          </div>
        ) : (
          <div className="beacon-empty-card">
            <h3>No watchlist selected</h3>
            <p style={{ marginTop: '0.5rem', color: 'var(--color-text-muted)' }}>
              Create a watchlist above to begin tracking instruments.
            </p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="beacon-app-footer">
        <div className="footer-content">
          <span>BEACON &bull; Know what deserves your attention &bull; Multi-Factor Market Intelligence</span>
          <span className="footer-provenance">NSE Historical Bhavcopy &bull; Marketaux Context</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
