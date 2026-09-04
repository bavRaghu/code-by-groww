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
} from './api';

function App() {
  const [watchlists, setWatchlists] = useState([]);
  const [activeWatchlistId, setActiveWatchlistId] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [loading, setLoading] = useState(false);
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

  // Initial load
  useEffect(() => {
    loadWatchlists();
  }, [loadWatchlists]);

  // Whenever active watchlist changes, load its market data
  useEffect(() => {
    if (activeWatchlistId) {
      loadMarketData(activeWatchlistId);
    }
  }, [activeWatchlistId, loadMarketData]);

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
      await loadMarketData(activeWatchlistId);
      await loadWatchlists(activeWatchlistId);
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
      await loadMarketData(activeWatchlistId);
      await loadWatchlists(activeWatchlistId);
    } catch (err) {
      setError(err.message || 'Failed to remove instrument.');
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
          <section aria-label="Active watchlist view">
            <div className="section-header">
              <h2 className="section-title">{activeWatchlist.name}</h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => loadMarketData(activeWatchlist.id)}
                  disabled={loading}
                >
                  {loading ? 'Refreshing...' : 'Refresh Market Data'}
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

            {/* Add Instrument Search Bar */}
            <div style={{ marginTop: '1.25rem', marginBottom: '1.25rem' }}>
              <div className="search-box">
                <input
                  type="text"
                  className="input-text"
                  placeholder="Search NSE symbol or company name (e.g., TCS, RELIANCE)..."
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

            {/* Market Observations Table */}
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
                                <div>{new Date(item.observed_at).toLocaleString()}</div>
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
        ) : (
          <div className="empty-state">
            <h3>No watchlist selected</h3>
            <p style={{ marginTop: '0.5rem' }}>Create a watchlist above to begin tracking instruments.</p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="footer">
        Smart Market Watchlist &mdash; Core Foundation Milestone &mdash; Market data powered by NSE CM-UDiFF
      </footer>
    </div>
  );
}

export default App;
