import './App.css'

function App() {
  return (
    <div className="app-shell">
      {/* ---- Header ---- */}
      <header className="header">
        <div className="header__logo" aria-hidden="true">W</div>
        <span className="header__title">Smart Market Watchlist</span>
        <span className="header__badge">Skeleton</span>
      </header>

      {/* ---- Hero ---- */}
      <main className="hero">
        <span className="hero__eyebrow">Code, by Groww 2026</span>

        <h1 className="hero__heading">
          Know what <em>meaningfully changed</em>
          <br />since you last checked
        </h1>

        <p className="hero__sub">
          A watchlist that acts as an attention filter — surfacing only the
          changes that deserve your focus and explaining why, so you can
          quickly decide what to investigate.
        </p>

        {/* Project status chips */}
        <div className="hero__status" role="list" aria-label="System status">
          <div className="status-chip" role="listitem">
            <span className="status-chip__dot status-chip__dot--green" aria-hidden="true" />
            Frontend running
          </div>
          <div className="status-chip" role="listitem">
            <span className="status-chip__dot status-chip__dot--yellow" aria-hidden="true" />
            Backend: start <code>uvicorn app.main:app --reload</code>
          </div>
          <div className="status-chip" role="listitem">
            <span className="status-chip__dot status-chip__dot--yellow" aria-hidden="true" />
            Database: start <code>docker compose up -d</code>
          </div>
        </div>
      </main>

      {/* ---- Footer ---- */}
      <footer className="footer">
        Smart Market Watchlist &mdash; initial project skeleton &mdash; no product features yet
      </footer>
    </div>
  )
}

export default App
