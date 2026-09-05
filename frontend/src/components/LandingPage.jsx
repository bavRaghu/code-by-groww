import { useState } from 'react';
import {
  ArrowRight,
  ExternalLink,
  Layers,
  Shield,
  Activity,
  Eye,
  Clock,
  BookOpen,
  TrendingUp,
  Database,
  Filter,
  Cpu,
  GitBranch,
  Search,
  CheckCircle2,
  FileText,
} from 'lucide-react';
import FireflyBackground from './FireflyBackground';
import ArchitectureExplorer from './ArchitectureExplorer';

export default function LandingPage({ onOpenAuth, onDemoLogin, demoLoading, demoError }) {
  const [activeBuiltTab, setActiveBuiltTab] = useState('core'); // 'core' | 'further'

  return (
    <div className="landing-shell">
      {/* Ambient Firefly Motif */}
      <FireflyBackground />

      {/* Navigation Header */}
      <header className="landing-nav">
        <div className="landing-nav__left">
          <div className="beacon-brand-mark" aria-hidden="true">
            <span className="beacon-brand-dot" />
          </div>
          <span className="beacon-wordmark">BEACON</span>
        </div>

        <nav className="landing-nav__links">
          <a href="#problem" className="nav-link">The Problem</a>
          <a href="#how-we-got-here" className="nav-link">How We Got Here</a>
          <a href="#architecture" className="nav-link">Architecture</a>
          <a href="#what-we-built" className="nav-link">What We Built</a>
          <a href="#in-action" className="nav-link">See in Action</a>
        </nav>

        <div className="landing-nav__actions">
          <button
            type="button"
            className="beacon-btn beacon-btn--ghost"
            onClick={() => onOpenAuth('login')}
          >
            Sign In
          </button>
          <button
            type="button"
            className="beacon-btn beacon-btn--primary-sm"
            onClick={() => onOpenAuth('register')}
          >
            Get Started
          </button>
          <button
            type="button"
            className="beacon-btn beacon-btn--demo-sm"
            onClick={onDemoLogin}
            disabled={demoLoading}
            title="1-Click Evaluator Login as dev@example.com"
          >
            <span>{demoLoading ? 'Connecting...' : 'Quick Demo'}</span>
          </button>
        </div>
      </header>

      {/* 2. HERO SECTION */}
      <section className="landing-hero" aria-label="Beacon introduction">
        <div className="hero-eyebrow">
          <span>SMART MARKET WATCHLIST</span>
        </div>

        <h1 className="hero-beacon-wordmark">
          BEACON
        </h1>

        <p className="hero-supporting-statement">
          Like a beacon, we draw your attention to what matters without asking you to watch everything.
        </p>

        {demoError && (
          <div className="hero-demo-error" role="alert">
            {demoError}
          </div>
        )}

        <div className="hero-actions">
          <button
            type="button"
            className="beacon-btn beacon-btn--primary hero-btn-main"
            onClick={() => onOpenAuth('login')}
          >
            <span>Launch Beacon</span>
            <ArrowRight size={16} />
          </button>
          <a
            href="#architecture"
            className="beacon-btn beacon-btn--secondary hero-btn-demo"
          >
            <span>Explore Architecture</span>
          </a>
        </div>

        <div className="hero-trust-bar">
          <div className="trust-item">
            <Shield size={14} className="trust-icon" />
            <span>Multi-factor deterministic scoring</span>
          </div>
          <div className="trust-divider" />
          <div className="trust-item">
            <Activity size={14} className="trust-icon" />
            <span>NSE Bhavcopy market observations</span>
          </div>
          <div className="trust-divider" />
          <div className="trust-item">
            <CheckCircle2 size={14} className="trust-icon" />
            <span>Information &amp; attention filter — not trading advice</span>
          </div>
        </div>
      </section>

      {/* 4. PROBLEM SECTION */}
      <section id="problem" className="landing-problem" aria-label="The problem and contrast">
        <div className="section-container">
          <div className="section-header text-center">
            <span className="section-eyebrow">THE PROBLEM &amp; THE CONTRAST</span>
            <h2 className="section-headline">
              The problem isn&apos;t seeing change. It&apos;s knowing which change deserves a second look.
            </h2>
          </div>

          <div className="problem-contrast-grid">
            {/* Column A: Traditional Watchlist */}
            <div className="contrast-card contrast-card--traditional">
              <div className="contrast-card__header">
                <span className="contrast-badge">Traditional Watchlist</span>
                <h3 className="contrast-card__title">A raw stream of price ticks</h3>
              </div>
              <p className="contrast-card__core">
                Tells users <strong>what changed</strong> in raw percentage terms.
              </p>
              <ul className="contrast-card__list">
                <li>Treats every 3% move the same, ignoring baseline, volume, and sector backdrop.</li>
                <li>Forces users to manually scan dozens of rows to guess if anything actually matters.</li>
                <li>Relies on arbitrary rolling 24h windows disconnected from when you last looked.</li>
                <li>Induces alert fatigue, visual overload, and reactive impulses.</li>
              </ul>
            </div>

            {/* Column B: Beacon's Approach */}
            <div className="contrast-card contrast-card--beacon">
              <div className="contrast-card__header">
                <span className="contrast-badge contrast-badge--beacon">Beacon Attention Filter</span>
                <h3 className="contrast-card__title">An intelligent evidence filter</h3>
              </div>
              <p className="contrast-card__core">
                Tells users <strong>which changes deserve attention</strong> based on evidence.
              </p>
              <ul className="contrast-card__list">
                <li>Anchors evaluations strictly to your personal last-checked observation baseline.</li>
                <li>Quantifies magnitude against historical volatility, volume surge, and benchmark spread.</li>
                <li>Explicitly filters sub-threshold noise so quiet stocks stay quiet.</li>
                <li>Provides non-causal structured explanations with bounded contextual news.</li>
              </ul>
            </div>
          </div>

          {/* Conceptual Statement Callout */}
          <div className="conceptual-statement-banner">
            <p className="conceptual-statement-text">
              &ldquo;A large move is not automatically meaningful. A quiet move can become important in context. Beacon treats price movement as a starting signal—not a conclusion.&rdquo;
            </p>
          </div>
        </div>
      </section>

      {/* 5. HOW WE GOT HERE */}
      <section id="how-we-got-here" className="landing-research" aria-label="Research foundation">
        <div className="section-container">
          <div className="section-header text-center">
            <span className="section-eyebrow">RESEARCH FOUNDATIONS</span>
            <h2 className="section-headline">HOW WE GOT HERE</h2>
            <p className="section-intro">
              Our research gave us a useful lens for deciding what Beacon should surface—and what it should leave alone.
            </p>
          </div>

          <div className="research-grid">
            {/* Paper A: DellaVigna & Pollet */}
            <div className="research-card">
              <div className="research-card__meta">
                <span className="research-topic">Investor Attention &amp; Inattention</span>
                <span className="research-venue">NBER Working Paper No. 11453</span>
              </div>
              <h3 className="research-paper-title">
                Investor Inattention, Firm Reaction, and Friday Earnings Announcements
              </h3>
              
              <div className="research-card__body">
                <div className="research-block">
                  <div className="research-block__label">1. What we found</div>
                  <p className="research-block__content">
                    When investors face multiple concurrent announcements or review delays, bounded attention produces cognitive friction and delayed absorption for subtle, high-materiality events.
                  </p>
                </div>

                <div className="research-block">
                  <div className="research-block__label">2. What we took from it</div>
                  <p className="research-block__content">
                    Change detection must be decoupled from arbitrary market close times or alert spam. Beacon anchors evaluation strictly to each user&apos;s personal observation baseline so returning users evaluate changes across their actual absence window.
                  </p>
                </div>
              </div>

              <div className="research-card__footer">
                <a
                  href="https://www.nber.org/papers/w11453"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="research-link"
                >
                  <span>Read paper</span>
                  <ExternalLink size={12} />
                </a>
              </div>
            </div>

            {/* Paper B: Dhawan & Putniņš (2026) */}
            <div className="research-card">
              <div className="research-card__meta">
                <span className="research-topic">Dhawan &amp; Putniņš (2026)</span>
                <span className="research-venue">SSRN Research Series</span>
              </div>
              <h3 className="research-paper-title">
                What You Watch in Markets Matters: Attention to Information Versus Attention to Prices
              </h3>
              
              <div className="research-card__body">
                <div className="research-block">
                  <div className="research-block__label">1. What we found</div>
                  <p className="research-block__content">
                    Attention directed primarily at raw prices increases noise-trading and decision volatility, whereas attention directed at fundamental, contextual information improves analytical discipline.
                  </p>
                </div>

                <div className="research-block">
                  <div className="research-block__label">2. What we took from it</div>
                  <p className="research-block__content">
                    Beacon never treats price changes as conclusions. Price movement is only a detection candidate, which must be corroborated by volume abnormalities, historical z-scores, and benchmark divergence before demanding attention.
                  </p>
                </div>
              </div>

              <div className="research-card__footer">
                <a
                  href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4758784"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="research-link"
                >
                  <span>Read paper</span>
                  <ExternalLink size={12} />
                </a>
              </div>
            </div>

            {/* Paper C: Federal Reserve */}
            <div className="research-card">
              <div className="research-card__meta">
                <span className="research-topic">Federal Reserve</span>
                <span className="research-venue">FEDS Working Papers</span>
              </div>
              <h3 className="research-paper-title">
                Effects of Information Overload on Financial Markets: How Much Is Too Much?
              </h3>
              
              <div className="research-card__body">
                <div className="research-block">
                  <div className="research-block__label">1. What we found</div>
                  <p className="research-block__content">
                    Disclosures and high-frequency alerts beyond an optimal threshold degrade decision accuracy, creating alert fatigue and reduced responsiveness to significant market shifts.
                  </p>
                </div>

                <div className="research-block">
                  <div className="research-block__label">2. What we took from it</div>
                  <p className="research-block__content">
                    Optimize for attention quality, not quantity. Sub-threshold moves are explicitly filtered into a quiet status (score &lt; 0.20), and multiple concurrent detection signals are collapsed into single unified change episodes.
                  </p>
                </div>
              </div>

              <div className="research-card__footer">
                <a
                  href="https://www.federalreserve.gov/econres/feds/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="research-link"
                >
                  <span>Read paper</span>
                  <ExternalLink size={12} />
                </a>
              </div>
            </div>

            {/* Paper D: Hjelle et al. (2024) */}
            <div className="research-card">
              <div className="research-card__meta">
                <span className="research-topic">Visual Decision Systems</span>
                <span className="research-venue">Hjelle et al. (2024)</span>
              </div>
              <h3 className="research-paper-title">
                Attention-Aware Decision Support in High-Density Financial Environments
              </h3>
              
              <div className="research-card__body">
                <div className="research-block">
                  <div className="research-block__label">1. What we found</div>
                  <p className="research-block__content">
                    Unranked, flat tabular displays increase visual scanning time by over 40%. Decision accuracy rises when anomalies are ranked above steady-state telemetry with transparent evidence decomposition.
                  </p>
                </div>

                <div className="research-block">
                  <div className="research-block__label">2. What we took from it</div>
                  <p className="research-block__content">
                    Strict structural separation between the &quot;Since you last checked&quot; summary card, ranked attention feed, and the full registry. Every surfaced item includes decomposed evidence components.
                  </p>
                </div>
              </div>

              <div className="research-card__footer">
                <a
                  href="https://doi.org/10.1145/3613904"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="research-link"
                >
                  <span>Read paper</span>
                  <ExternalLink size={12} />
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Interactive System Architecture Explorer */}
      <ArchitectureExplorer />

      {/* 6. WHAT WE BUILT */}
      <section id="what-we-built" className="landing-built" aria-label="Architecture and engineering features">
        <div className="section-container">
          <div className="section-header text-center">
            <span className="section-eyebrow">ENGINEERING IMPLEMENTATION</span>
            <h2 className="section-headline">WHAT WE BUILT</h2>
            <p className="section-intro">
              Beacon is engineered from first principles as an attention filter, turning raw market observations into an explainable, prioritized change feed.
            </p>
          </div>

          {/* Group Filter Tabs */}
          <div className="built-tab-bar" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={activeBuiltTab === 'core'}
              className={`built-tab ${activeBuiltTab === 'core' ? 'built-tab--active' : ''}`}
              onClick={() => setActiveBuiltTab('core')}
            >
              <Cpu size={14} style={{ marginRight: '6px' }} />
              CORE ARCHITECTURE (6)
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeBuiltTab === 'further'}
              className={`built-tab ${activeBuiltTab === 'further' ? 'built-tab--active' : ''}`}
              onClick={() => setActiveBuiltTab('further')}
            >
              <GitBranch size={14} style={{ marginRight: '6px' }} />
              WHERE WE WENT FURTHER (6)
            </button>
          </div>

          {/* Core Implementation Group */}
          {activeBuiltTab === 'core' && (
            <div className="built-cards-grid">
              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <Layers size={18} />
                </div>
                <h3 className="built-card__title">Watchlists</h3>
                <p className="built-card__desc">
                  Isolated multi-watchlist management with deterministic ordering, custom naming, and idempotent symbol tracking scoped strictly per authenticated user.
                </p>
              </div>

              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <Database size={18} />
                </div>
                <h3 className="built-card__title">Market State</h3>
                <p className="built-card__desc">
                  Normalized persistence of historical EOD observations, maintaining sequential OHLCV records and honest data freshness timestamps without fabricating missing data.
                </p>
              </div>

              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <Clock size={18} />
                </div>
                <h3 className="built-card__title">Change Detection</h3>
                <p className="built-card__desc">
                  Baseline-relative delta engine evaluating changes against each user&apos;s specific last-checked point without advancing baseline state prematurely.
                </p>
              </div>

              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <TrendingUp size={18} />
                </div>
                <h3 className="built-card__title">Significance</h3>
                <p className="built-card__desc">
                  Deterministic multi-factor scoring combining magnitude, historical abnormality (z-score), volume surge, and benchmark relative return into a continuous 0.0–1.0 score.
                </p>
              </div>

              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <Filter size={18} />
                </div>
                <h3 className="built-card__title">Attention</h3>
                <p className="built-card__desc">
                  Deterministic multi-criteria ranking (overall score DESC, significance tier, signal count, symbol tie-breaker) with explicit suppression of sub-threshold noise.
                </p>
              </div>

              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <FileText size={18} />
                </div>
                <h3 className="built-card__title">Explanation</h3>
                <p className="built-card__desc">
                  Non-causal structured rationales stating observed evidence plainly without unproven causality, speculative predictions, or investment advice.
                </p>
              </div>
            </div>
          )}

          {/* Where We Went Further Group */}
          {activeBuiltTab === 'further' && (
            <div className="built-cards-grid">
              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <BookOpen size={18} />
                </div>
                <h3 className="built-card__title">News Context</h3>
                <p className="built-card__desc">
                  Bounded Marketaux news integration showing up to 3 temporally relevant contextual articles for surfaced moves without influencing quantitative scoring.
                </p>
              </div>

              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <Activity size={18} />
                </div>
                <h3 className="built-card__title">Change Timeline</h3>
                <p className="built-card__desc">
                  Episode-based audit grouping multiple concurrent detection signals per tracking interval into an inspectable chronological timeline.
                </p>
              </div>

              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <Search size={18} />
                </div>
                <h3 className="built-card__title">NSE Instrument Discovery</h3>
                <p className="built-card__desc">
                  Live search and ingestion across 1,200+ authoritative National Stock Exchange equity securities from official CM-UDiFF Bhavcopy files.
                </p>
              </div>

              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <Shield size={18} />
                </div>
                <h3 className="built-card__title">Data Quality</h3>
                <p className="built-card__desc">
                  Idempotent ingestion, source consistency guards, corrupt record rejection, and transparent handling of missing historical windows.
                </p>
              </div>

              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <Cpu size={18} />
                </div>
                <h3 className="built-card__title">Provider Abstraction</h3>
                <p className="built-card__desc">
                  Decoupled provider interfaces (<code>NSEHistoricalProvider</code>, <code>MarketauxNewsProvider</code>) isolating vendor-specific logic from derived intelligence.
                </p>
              </div>

              <div className="built-card">
                <div className="built-card__icon-wrap">
                  <Eye size={18} />
                </div>
                <h3 className="built-card__title">User State</h3>
                <p className="built-card__desc">
                  Persistent baseline tracking (<code>user_observations</code>), review audit trail (<code>change_reviews</code>), and scrypt + JWT per-user authorization scoping.
                </p>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* 7. SEE BEACON IN ACTION */}
      <section id="in-action" className="landing-action" aria-label="Working application access">
        <div className="section-container">
          <div className="section-header text-center">
            <span className="section-eyebrow">LIVE EVALUATOR ACCESS</span>
            <h2 className="section-headline">SEE BEACON IN ACTION</h2>
            <p className="section-intro">
              Experience the working attention filter running against real NSE historical market observations. Review surfaced signals, inspect multi-factor evidence cards, and test baseline advancement.
            </p>
          </div>

          <div className="action-options-grid">
            {/* Option A: Quick Evaluator Demo */}
            <div className="action-option-card action-option-card--featured">
              <div className="action-option-badge">Recommended for Evaluators</div>
              <h3 className="action-option-title">1-Click Interactive Demo</h3>
              <p className="action-option-desc">
                Pre-loaded with seeded NSE market observations, active attention items (TCS High, INFY Medium, RELIANCE Quiet), baseline delta comparisons, and Marketaux news context.
              </p>
              
              <button
                type="button"
                className="beacon-btn beacon-btn--primary action-btn"
                onClick={onDemoLogin}
                disabled={demoLoading}
              >
                <span>{demoLoading ? 'Connecting to Demo...' : 'Launch Interactive Demo'}</span>
                <ArrowRight size={15} />
              </button>

              <div className="action-option-note">
                Instant login as <code>dev@example.com</code> • Zero configuration needed
              </div>
            </div>

            {/* Option B: Clean Personal Workspace */}
            <div className="action-option-card">
              <div className="action-option-badge action-option-badge--subtle">Custom Workspace</div>
              <h3 className="action-option-title">Personal Account</h3>
              <p className="action-option-desc">
                Register a dedicated user account, curate custom watchlists from 1,200+ NSE equities, and observe changes relative to your own check-in intervals.
              </p>
              
              <button
                type="button"
                className="beacon-btn beacon-btn--secondary action-btn"
                onClick={() => onOpenAuth('login')}
              >
                <span>Create Account / Sign In</span>
                <ArrowRight size={15} />
              </button>

              <div className="action-option-note">
                Strict per-user data isolation • Scrypt password security
              </div>
            </div>
          </div>

          {/* Deterministic Walkthrough Workflow Sequence */}
          <div className="walkthrough-guide">
            <div className="walkthrough-header">
              <span className="walkthrough-title">Deterministic Evaluator Walkthrough</span>
              <span className="walkthrough-subtitle">Core Product Loop</span>
            </div>

            <div className="walkthrough-steps">
              <div className="walkthrough-step">
                <span className="walkthrough-step__num">01</span>
                <div className="walkthrough-step__content">
                  <h4>Observe Baseline</h4>
                  <p>Check active watchlist snapshot and baseline prices from previous check-in.</p>
                </div>
              </div>
              <div className="walkthrough-step">
                <span className="walkthrough-step__num">02</span>
                <div className="walkthrough-step__content">
                  <h4>Check for Changes</h4>
                  <p>Run change detection against newly available market observations without advancing state.</p>
                </div>
              </div>
              <div className="walkthrough-step">
                <span className="walkthrough-step__num">03</span>
                <div className="walkthrough-step__content">
                  <h4>Inspect Attention Feed</h4>
                  <p>Review High and Medium attention cards, multi-factor evidence, and supporting Marketaux news.</p>
                </div>
              </div>
              <div className="walkthrough-step">
                <span className="walkthrough-step__num">04</span>
                <div className="walkthrough-step__content">
                  <h4>Review &amp; Advance</h4>
                  <p>Mark items as reviewed to update your personal observation baseline for the next cycle.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 8. FINAL CTA */}
      <section className="landing-cta-banner" aria-label="Call to action">
        <div className="cta-container text-center">
          <h2 className="cta-headline">
            Don&apos;t watch everything. Know what deserves your attention.
          </h2>
          <div className="cta-action">
            <button
              type="button"
              className="beacon-btn beacon-btn--primary cta-btn"
              onClick={() => onOpenAuth('login')}
            >
              <span>Open Beacon →</span>
            </button>
          </div>
        </div>
      </section>

      {/* 9. FOOTER */}
      <footer className="landing-footer">
        <div className="footer-top">
          <div className="footer-brand">
            <div className="beacon-brand-mark" aria-hidden="true">
              <span className="beacon-brand-dot" />
            </div>
            <span className="beacon-wordmark">BEACON</span>
            <span className="footer-competition-badge">Code, by Groww 2026</span>
          </div>

          <div className="footer-links">
            <a
              href="https://github.com/bavRaghu/code-by-groww"
              target="_blank"
              rel="noopener noreferrer"
              className="footer-link"
            >
              GitHub Repository
              <ExternalLink size={11} style={{ marginLeft: '3px' }} />
            </a>
            <a
              href="https://github.com/bavRaghu/code-by-groww#architecture"
              target="_blank"
              rel="noopener noreferrer"
              className="footer-link"
            >
              Architecture Spec
              <ExternalLink size={11} style={{ marginLeft: '3px' }} />
            </a>
            <a
              href="https://github.com/bavRaghu/code-by-groww/blob/main/docs/ATTENTION_MODEL.md"
              target="_blank"
              rel="noopener noreferrer"
              className="footer-link"
            >
              Attention Model
              <ExternalLink size={11} style={{ marginLeft: '3px' }} />
            </a>
          </div>
        </div>

        <div className="footer-disclaimer">
          <p>
            <strong>Analytical Disclaimer:</strong> Beacon is an intelligent market attention filtering tool developed for Code, by Groww 2026. Beacon does not offer investment advice, buy/sell recommendations, or price direction forecasts. Market observations are processed sequentially from historical NSE Bhavcopy data archives.
          </p>
          <div className="footer-bottom-row">
            <span>Built with precision for Code, by Groww 2026</span>
            <span>National Stock Exchange CM-UDiFF &bull; Marketaux Contextual API</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

