import { useState, useEffect, useRef } from 'react';
import mermaid from 'mermaid';
import {
  ArrowLeft,
  ExternalLink,
  FileCode2,
  Compass,
  Maximize2,
} from 'lucide-react';

const GITHUB_BASE = 'https://github.com/bavRaghu/code-by-groww';

// Initialize Mermaid once with Beacon dark aesthetic
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    darkMode: true,
    background: '#090C13',
    primaryColor: '#0E1422',
    primaryTextColor: '#F8FAFC',
    primaryBorderColor: 'rgba(245, 158, 11, 0.4)',
    lineColor: '#64748B',
    secondaryColor: '#161F33',
    tertiaryColor: '#090C13',
    fontFamily: 'Inter, system-ui, sans-serif',
    fontSize: '13px',
  },
  flowchart: {
    curve: 'basis',
    nodeSpacing: 45,
    rankSpacing: 45,
    htmlLabels: true,
  },
  securityLevel: 'loose',
});

const OVERVIEW_MERMAID = `flowchart TD
    B["BEACON"]

    FE["REACT FRONTEND<br/>Watchlists · Attention · Detail"]
    API["FASTAPI BACKEND<br/>API · Auth · Application Services"]

    INT["INTELLIGENCE<br/><br/>Detect → Assess<br/>→ Rank → Explain"]
    DATA["DATA SOURCES<br/><br/>NSE · Marketaux"]

    DB["POSTGRESQL<br/>Data + User State"]

    B --> FE
    FE -->|REST| API

    API --> INT
    API --> DATA

    INT --> DB
    DATA --> DB`;

const COMPONENTS = {
  frontend: {
    id: 'frontend',
    title: 'React Frontend',
    badge: 'Presentation & Interaction Layer',
    subtitle: 'Watchlists · Attention · Detail',
    explanation:
      'React provides the user-facing layer for watchlists, attention summaries, stock detail and change review. Server communication is kept behind a small API client so UI components don\'t own backend knowledge.',
    mermaid: `flowchart TD
    FE["REACT FRONTEND"]

    FE --> APP["Application Shell"]

    APP --> WL["Watchlists"]
    APP --> ATT["Attention Feed"]
    APP --> DETAIL["Stock Detail"]
    APP --> REVIEW["Change Review"]

    APP --> API["API Client"]

    API --> REST["REST API"]

    REST --> BACKEND["FastAPI Backend"]

    WL --> STATE["Client State"]
    ATT --> STATE
    DETAIL --> STATE
    REVIEW --> STATE

    STATE --> QUERY["Server State / Query Cache"]

    CLICK_FE["main.jsx"]
    CLICK_API["api.js"]

    API -.-> CLICK_API
    APP -.-> CLICK_FE`,
    links: [
      {
        name: 'main.jsx',
        path: 'frontend/src/main.jsx',
        url: `${GITHUB_BASE}/blob/main/frontend/src/main.jsx`,
        desc: 'React 19 entry point and DOM root mount',
      },
      {
        name: 'api.js',
        path: 'frontend/src/api.js',
        url: `${GITHUB_BASE}/blob/main/frontend/src/api.js`,
        desc: 'Stateless API client with JWT token attachment and error interception',
      },
      {
        name: 'App.jsx',
        path: 'frontend/src/App.jsx',
        url: `${GITHUB_BASE}/blob/main/frontend/src/App.jsx`,
        desc: 'Root shell coordinating watchlists, attention feed, and detail navigation',
      },
    ],
    nodeLinks: {
      CLICK_FE: `${GITHUB_BASE}/blob/main/frontend/src/main.jsx`,
      CLICK_API: `${GITHUB_BASE}/blob/main/frontend/src/api.js`,
    },
  },
  backend: {
    id: 'backend',
    title: 'FastAPI Backend',
    badge: 'API & Application Services',
    subtitle: 'API · Auth · Application Services',
    explanation:
      'FastAPI is the boundary between the UI and Beacon\'s application logic. Routers handle HTTP concerns, Pydantic schemas validate data, services coordinate domain operations, and persistence stays behind the application layer.',
    mermaid: `flowchart TD
    API["FASTAPI BACKEND"]

    API --> AUTH["Authentication<br/>& Authorization"]

    API --> ROUTERS["API ROUTERS"]

    ROUTERS --> WATCH["Watchlists"]
    ROUTERS --> MARKET["Market Data"]
    ROUTERS --> CHANGE["Changes"]
    ROUTERS --> ATTENTION["Attention"]
    ROUTERS --> REVIEW["Reviews"]
    ROUTERS --> NEWS["News"]

    ROUTERS --> SCHEMAS["Pydantic Schemas"]

    WATCH --> SERVICES["APPLICATION SERVICES"]
    MARKET --> SERVICES
    CHANGE --> SERVICES
    ATTENTION --> SERVICES
    REVIEW --> SERVICES
    NEWS --> SERVICES

    SERVICES --> INTEL["DOMAIN / INTELLIGENCE"]

    SERVICES --> DB["PERSISTENCE"]

    DB --> SQLA["SQLAlchemy"]
    SQLA --> PG["PostgreSQL"]

    API -.-> MAIN["main.py"]
    ROUTERS -.-> ROUTERFILE["API router modules"]`,
    links: [
      {
        name: 'main.py',
        path: 'backend/app/main.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/main.py`,
        desc: 'Application factory, CORS middleware, and API router registration',
      },
      {
        name: 'watchlists.py',
        path: 'backend/app/api/v1/watchlists.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/api/v1/watchlists.py`,
        desc: 'Watchlist CRUD, candidate check, attention feed, and review endpoints',
      },
      {
        name: 'market.py',
        path: 'backend/app/api/v1/market.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/api/v1/market.py`,
        desc: 'Market snapshot retrieval and data freshness validation',
      },
      {
        name: 'schemas/watchlist.py',
        path: 'backend/app/schemas/watchlist.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/schemas/watchlist.py`,
        desc: 'Pydantic schemas validating client input and response contracts',
      },
    ],
    nodeLinks: {
      MAIN: `${GITHUB_BASE}/blob/main/backend/app/main.py`,
      ROUTERFILE: `${GITHUB_BASE}/blob/main/backend/app/api/v1/watchlists.py`,
    },
  },
  intelligence: {
    id: 'intelligence',
    title: 'Intelligence',
    badge: 'Derived Intelligence & Prioritization',
    subtitle: 'Detect → Assess → Rank → Explain',
    explanation:
      'Beacon separates raw market observations from derived intelligence. Candidate changes are detected first, significance is assessed using multiple signals, related changes are grouped into episodes, and the resulting evidence is ranked before reaching the user.',
    mermaid: `flowchart TD
    INT["INTELLIGENCE"]

    OBS["Market Observations"]
    EVENTS["Material Events"]
    NEWS["Relevant News"]
    USER["User Observation State"]

    OBS --> DETECT["CHANGE DETECTION"]

    EVENTS --> DETECT
    NEWS --> CONTEXT["Evidence + Context"]

    DETECT --> TYPES["Candidate Changes"]

    TYPES --> PRICE["Price Movement"]
    TYPES --> ABN["Abnormal Return"]
    TYPES --> REL["Relative Performance"]
    TYPES --> VOL["Volume Anomaly"]
    TYPES --> EVENT["Material Event"]

    PRICE --> SCORE["SIGNIFICANCE ASSESSMENT"]
    ABN --> SCORE
    REL --> SCORE
    VOL --> SCORE
    EVENT --> SCORE

    SCORE --> LEVEL["High · Medium · Low · None"]

    LEVEL --> GROUP["EPISODE GROUPING"]

    CONTEXT --> GROUP

    GROUP --> RANK["ATTENTION RANKING"]

    USER --> RANK

    RANK --> EXPLAIN["EXPLANATION"]

    EXPLAIN --> FEED["ATTENTION FEED"]
    EXPLAIN --> DETAIL["STOCK DETAIL"]

    DETECT -.-> CD["change_detection.py"]
    SCORE -.-> SS["significance_scoring.py"]
    RANK -.-> AT["attention.py"]`,
    links: [
      {
        name: 'change_detection.py',
        path: 'backend/app/services/change_detection.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/services/change_detection.py`,
        desc: 'Evaluates deltas against the user baseline without premature advancement',
      },
      {
        name: 'significance_scoring.py',
        path: 'backend/app/services/significance_scoring.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/services/significance_scoring.py`,
        desc: 'Deterministic multi-factor scoring (magnitude, z-score, volume, benchmark)',
      },
      {
        name: 'attention.py',
        path: 'backend/app/services/attention.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/services/attention.py`,
        desc: 'Episode deduplication, noise filtering, and deterministic multi-criteria ranking',
      },
      {
        name: 'watchlists.py',
        path: 'backend/app/api/v1/watchlists.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/api/v1/watchlists.py`,
        desc: 'API router mounting the attention feed and review lifecycle endpoints',
      },
    ],
    nodeLinks: {
      CD: `${GITHUB_BASE}/blob/main/backend/app/services/change_detection.py`,
      SS: `${GITHUB_BASE}/blob/main/backend/app/services/significance_scoring.py`,
      AT: `${GITHUB_BASE}/blob/main/backend/app/services/attention.py`,
    },
  },
  data: {
    id: 'data',
    title: 'Data Sources',
    badge: 'Provider Abstraction & Freshness Boundary',
    subtitle: 'NSE · Marketaux',
    explanation:
      'External data is isolated behind provider boundaries. Beacon normalizes provider-specific responses before they enter the application, allowing the intelligence layer to remain independent of a particular market-data or news provider. Data freshness and availability are treated as part of the data itself—not assumed.',
    mermaid: `flowchart TD
    DATA["DATA SOURCES"]

    NSE["NSE"]

    NSE --> PROVIDER["Market Data Provider Boundary"]

    PROVIDER --> NORMALIZE["Normalize Market Observations"]

    NORMALIZE --> VALIDATE["Validate + Check Freshness"]

    VALIDATE --> INGEST["Ingestion Service"]

    INGEST --> STORE["MarketObservation"]

    MARKET["Market Data"] --> PROVIDER

    NEWSAPI["Marketaux"]

    NEWSAPI --> NEWSPROVIDER["News Provider Boundary"]

    NEWSPROVIDER --> NEWSNORMALIZE["Normalize News"]

    NEWSNORMALIZE --> ASSOC["Associate with Instruments"]

    ASSOC --> NEWSSTORE["NewsArticle"]

    STORE --> PG["PostgreSQL"]
    NEWSSTORE --> PG

    NSE -.-> NSEFILE["nse.py"]
    PROVIDER -.-> PROVIDERFILE["providers/nse.py"]
    INGEST -.-> SERVICEFILE["ingestion/service.py"]
    NEWSAPI -.-> NEWSFILE["services/news/service.py"]`,
    links: [
      {
        name: 'ingestion/nse.py',
        path: 'backend/app/ingestion/nse.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/ingestion/nse.py`,
        desc: 'Authoritative NSE CM-UDiFF Common Bhavcopy file parser & normalizer',
      },
      {
        name: 'providers/nse.py',
        path: 'backend/app/providers/nse.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/providers/nse.py`,
        desc: 'Decoupled NSE historical market data provider abstraction',
      },
      {
        name: 'ingestion/service.py',
        path: 'backend/app/ingestion/service.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/ingestion/service.py`,
        desc: 'Idempotent ingestion coordinator with source-consistency guards',
      },
      {
        name: 'services/news/service.py',
        path: 'backend/app/services/news/service.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/services/news/service.py`,
        desc: 'Marketaux news context retrieval and temporal relevance matching',
      },
    ],
    nodeLinks: {
      NSEFILE: `${GITHUB_BASE}/blob/main/backend/app/ingestion/nse.py`,
      PROVIDERFILE: `${GITHUB_BASE}/blob/main/backend/app/providers/nse.py`,
      SERVICEFILE: `${GITHUB_BASE}/blob/main/backend/app/ingestion/service.py`,
      NEWSFILE: `${GITHUB_BASE}/blob/main/backend/app/services/news/service.py`,
    },
  },
  persistence: {
    id: 'persistence',
    title: 'PostgreSQL',
    badge: 'Normalized Persistence & User State',
    subtitle: 'Data + User State',
    explanation:
      'PostgreSQL is the durable source of truth. Beacon keeps raw observations separate from derived intelligence and user observation state, so refreshing market data does not erase what a user has already seen.',
    mermaid: `flowchart TD
    DB["POSTGRESQL"]

    RAW["RAW DATA"]

    RAW --> MO["MarketObservation"]
    RAW --> ME["MarketEvent"]
    RAW --> NA["NewsArticle"]

    DERIVED["DERIVED INTELLIGENCE"]

    DERIVED --> DC["DetectedChange"]
    DERIVED --> SA["SignificanceAssessment"]

    USER["USER STATE"]

    USER --> U["User"]
    USER --> WL["Watchlist"]
    USER --> WI["WatchlistItem"]
    USER --> UO["UserObservation"]
    USER --> CR["ChangeReview"]

    MO --> I["Instrument"]
    ME --> I
    NA --> I

    DC --> I
    SA --> DC

    WL --> WI
    WI --> I

    UO --> I
    CR --> DC

    DB --> RAW
    DB --> DERIVED
    DB --> USER`,
    links: [
      {
        name: 'market_observation.py',
        path: 'backend/app/models/market_observation.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/models/market_observation.py`,
        desc: 'Sequential OHLCV observation model with unique (instrument, observed_at)',
      },
      {
        name: 'db/session.py',
        path: 'backend/app/db/session.py',
        url: `${GITHUB_BASE}/blob/main/backend/app/db/session.py`,
        desc: 'SQLAlchemy database engine and transactional session lifecycle',
      },
      {
        name: 'alembic/env.py',
        path: 'backend/alembic/env.py',
        url: `${GITHUB_BASE}/blob/main/backend/alembic/env.py`,
        desc: 'Alembic schema migration environment and model metadata registration',
      },
      {
        name: 'docker-compose.yml',
        path: 'docker-compose.yml',
        url: `${GITHUB_BASE}/blob/main/docker-compose.yml`,
        desc: 'Production-ready PostgreSQL 16 container definition with health checks',
      },
    ],
    nodeLinks: {},
  },
};

export default function ArchitectureExplorer() {
  const [selectedComponent, setSelectedComponent] = useState(null); // null = overview, or 'frontend'|'backend'|'intelligence'|'data'|'persistence'
  const [svgContent, setSvgContent] = useState('');
  const [renderError, setRenderError] = useState(null);
  const containerRef = useRef(null);

  // Render Mermaid diagram whenever selectedComponent changes
  useEffect(() => {
    let isMounted = true;

    const renderChart = async () => {
      try {
        if (isMounted) {
          setRenderError(null);
        }
        const definition = selectedComponent
          ? COMPONENTS[selectedComponent].mermaid
          : OVERVIEW_MERMAID;
        const uniqueId = `mermaid-arch-${selectedComponent || 'overview'}-${Math.random()
          .toString(36)
          .substring(2, 9)}`;

        const { svg } = await mermaid.render(uniqueId, definition);
        if (isMounted) {
          setSvgContent(svg);
        }
      } catch (err) {
        console.error('Mermaid render error:', err);
        if (isMounted) {
          setRenderError('Unable to render diagram. Please view the text representation.');
        }
      }
    };

    renderChart();
    return () => {
      isMounted = false;
    };
  }, [selectedComponent]);

  // Attach interactive click and keyboard handlers to Mermaid SVG nodes
  useEffect(() => {
    if (!containerRef.current) return;

    if (!selectedComponent) {
      // Overview mode: attach click and keyboard handlers to the 5 major components
      const nodeConfigs = [
        { key: 'FE', id: 'frontend', label: 'REACT FRONTEND' },
        { key: 'API', id: 'backend', label: 'FASTAPI BACKEND' },
        { key: 'INT', id: 'intelligence', label: 'INTELLIGENCE' },
        { key: 'DATA', id: 'data', label: 'DATA SOURCES' },
        { key: 'DB', id: 'persistence', label: 'POSTGRESQL' },
      ];

      const allNodes = containerRef.current.querySelectorAll('.node');
      nodeConfigs.forEach(({ key, id, label }) => {
        allNodes.forEach((nodeG) => {
          const idAttr = nodeG.getAttribute('id') || '';
          const dataId = nodeG.getAttribute('data-id') || '';
          const textContent = nodeG.textContent || '';

          const isMatch =
            idAttr.includes(`${key}-`) ||
            idAttr.startsWith(`flowchart-${key}-`) ||
            dataId === key ||
            textContent.toUpperCase().includes(label);

          if (isMatch) {
            nodeG.style.cursor = 'pointer';
            nodeG.setAttribute('tabindex', '0');
            nodeG.setAttribute('role', 'button');
            nodeG.setAttribute('aria-label', `Explore ${COMPONENTS[id].title} architecture`);
            nodeG.classList.add('interactive-arch-node');

            const onClick = (e) => {
              e.stopPropagation();
              setSelectedComponent(id);
            };
            const onKeyDown = (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                e.stopPropagation();
                setSelectedComponent(id);
              }
            };

            nodeG.addEventListener('click', onClick);
            nodeG.addEventListener('keydown', onKeyDown);
          }
        });
      });
    } else {
      // Detailed view: attach GitHub links to implementation nodes
      const compConfig = COMPONENTS[selectedComponent];
      if (compConfig.nodeLinks) {
        const allNodes = containerRef.current.querySelectorAll('.node');
        Object.entries(compConfig.nodeLinks).forEach(([nodeKey, url]) => {
          allNodes.forEach((nodeG) => {
            const idAttr = nodeG.getAttribute('id') || '';
            const textContent = nodeG.textContent || '';
            const isMatch =
              idAttr.includes(`${nodeKey}-`) ||
              idAttr.startsWith(`flowchart-${nodeKey}-`) ||
              (nodeKey === 'CLICK_FE' && textContent.includes('main.jsx')) ||
              (nodeKey === 'CLICK_API' && textContent.includes('api.js')) ||
              (nodeKey === 'MAIN' && textContent.includes('main.py')) ||
              (nodeKey === 'ROUTERFILE' && textContent.includes('router')) ||
              (nodeKey === 'CD' && textContent.includes('change_detection.py')) ||
              (nodeKey === 'SS' && textContent.includes('significance_scoring.py')) ||
              (nodeKey === 'AT' && textContent.includes('attention.py')) ||
              (nodeKey === 'NSEFILE' && textContent.includes('nse.py')) ||
              (nodeKey === 'PROVIDERFILE' && textContent.includes('providers/nse.py')) ||
              (nodeKey === 'SERVICEFILE' && textContent.includes('ingestion/service.py')) ||
              (nodeKey === 'NEWSFILE' && textContent.includes('services/news/service.py'));

            if (isMatch) {
              nodeG.style.cursor = 'pointer';
              nodeG.setAttribute('tabindex', '0');
              nodeG.setAttribute('role', 'link');
              nodeG.setAttribute('aria-label', `View ${textContent.trim()} on GitHub`);
              nodeG.classList.add('interactive-impl-node');

              const onClick = (e) => {
                e.stopPropagation();
                window.open(url, '_blank', 'noopener,noreferrer');
              };
              const onKeyDown = (e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  e.stopPropagation();
                  window.open(url, '_blank', 'noopener,noreferrer');
                }
              };

              nodeG.addEventListener('click', onClick);
              nodeG.addEventListener('keydown', onKeyDown);
            }
          });
        });
      }
    }
  }, [svgContent, selectedComponent]);

  const activeComp = selectedComponent ? COMPONENTS[selectedComponent] : null;

  return (
    <section id="architecture" className="landing-arch-section" aria-label="System architecture explorer">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header text-center">
          <span className="section-eyebrow">SYSTEM ARCHITECTURE</span>
          <h2 className="section-headline">Interactive Architecture Explorer</h2>
          <p className="section-intro">
            Explore Beacon at two levels: the complete end-to-end system at a glance, or drill down into any component to inspect its internal pipeline and verified implementation.
          </p>
        </div>

        {/* Application-like Architecture Window */}
        <div className="arch-window">
          {/* Window Chrome / Titlebar */}
          <div className="arch-window__titlebar">
            <div className="arch-window__controls" aria-hidden="true">
              <span className="window-dot window-dot--close" />
              <span className="window-dot window-dot--min" />
              <span className="window-dot window-dot--max" />
            </div>

            {/* Breadcrumbs Navigation */}
            <div className="arch-window__breadcrumb" aria-label="Architecture breadcrumbs">
              <span className="breadcrumb-root">HOW IT WORKS</span>
              <span className="breadcrumb-separator">/</span>
              <button
                type="button"
                className={`breadcrumb-item ${!selectedComponent ? 'breadcrumb-item--active' : ''}`}
                onClick={() => setSelectedComponent(null)}
              >
                ARCHITECTURE
              </button>
              {activeComp && (
                <>
                  <span className="breadcrumb-separator">/</span>
                  <span className="breadcrumb-item breadcrumb-item--active">
                    {activeComp.title.toUpperCase()}
                  </span>
                </>
              )}
            </div>

            {/* Back to Architecture button (when in detail view) */}
            <div className="arch-window__actions">
              {selectedComponent ? (
                <button
                  type="button"
                  className="arch-back-btn"
                  onClick={() => setSelectedComponent(null)}
                  title="Return to full system architecture"
                >
                  <ArrowLeft size={13} style={{ marginRight: '5px' }} />
                  <span>Back to architecture</span>
                </button>
              ) : (
                <span className="arch-mode-indicator">
                  <Compass size={13} style={{ marginRight: '5px', color: 'var(--beacon-gold)' }} />
                  <span>Full System View</span>
                </span>
              )}
            </div>
          </div>

          {/* Component Selection Quick-Bar */}
          <div className="arch-component-tabs" role="tablist" aria-label="Component drill-down selector">
            <button
              type="button"
              role="tab"
              aria-selected={selectedComponent === null}
              className={`arch-tab ${selectedComponent === null ? 'arch-tab--active' : ''}`}
              onClick={() => setSelectedComponent(null)}
            >
              <Maximize2 size={13} style={{ marginRight: '5px' }} />
              Full System
            </button>
            {Object.values(COMPONENTS).map((c) => (
              <button
                key={c.id}
                type="button"
                role="tab"
                aria-selected={selectedComponent === c.id}
                className={`arch-tab ${selectedComponent === c.id ? 'arch-tab--active' : ''}`}
                onClick={() => setSelectedComponent(c.id)}
              >
                {c.title}
              </button>
            ))}
          </div>

          {/* Main Canvas & Inspector Area */}
          <div
            className="arch-window__body"
            onClick={(e) => {
              // Clicking canvas background in detail mode returns to overview
              if (selectedComponent && e.target === e.currentTarget) {
                setSelectedComponent(null);
              }
            }}
          >
            {/* SVG Diagram Canvas */}
            <div className="arch-diagram-canvas">
              {renderError ? (
                <div className="arch-diagram-error">{renderError}</div>
              ) : (
                <div
                  ref={containerRef}
                  className="arch-mermaid-container"
                  dangerouslySetInnerHTML={{ __html: svgContent }}
                />
              )}

              {/* In-canvas Context Hint */}
              <div className="arch-canvas-hint">
                {!selectedComponent ? (
                  <span>Click any major component in the diagram or tabs above to inspect internal pipelines</span>
                ) : (
                  <span>Detailed Component Architecture • Click background or &quot;Back to architecture&quot; to return</span>
                )}
              </div>

              {/* Overall System Architecture Explanation (Overview State Only) */}
              {!selectedComponent && (
                <div className="arch-overview-explainer" aria-label="System architecture overview explanation">
                  <div className="arch-explainer-header">
                    <span className="arch-explainer-badge">SYSTEM ARCHITECTURE</span>
                    <h3 className="arch-explainer-heading">How Beacon is Structured</h3>
                  </div>

                  <p className="arch-explainer-lead">
                    Beacon separates the system into four concerns: the <strong className="arch-term">React frontend</strong> presents the user&apos;s watchlists, attention feed, and stock detail; the <strong className="arch-term">FastAPI backend</strong> provides the application boundary and coordinates requests; the <strong className="arch-term">intelligence layer</strong> turns raw market observations and supporting context into detected, assessed, and ranked changes; and external <strong className="arch-term">data sources</strong> provide the market and news inputs. <strong className="arch-term">PostgreSQL</strong> provides the durable source of truth for both market data and user state, allowing Beacon to distinguish what changed in the market from what the user has already seen.
                  </p>

                  <div className="arch-principles-grid">
                    <div className="arch-principle-card">
                      <div className="principle-card-head">
                        <span className="principle-layer-tag">PRESENTATION</span>
                        <h4 className="principle-name">React Frontend</h4>
                      </div>
                      <p className="principle-text">
                        The presentation layer communicates strictly through the REST API rather than directly owning market-data ingestion or provider state.
                      </p>
                    </div>

                    <div className="arch-principle-card">
                      <div className="principle-card-head">
                        <span className="principle-layer-tag">APPLICATION BOUNDARY</span>
                        <h4 className="principle-name">FastAPI Backend</h4>
                      </div>
                      <p className="principle-text">
                        Acts as the application boundary—handling HTTP routing, authentication/authorization, schema validation, and coordinating domain services.
                      </p>
                    </div>

                    <div className="arch-principle-card">
                      <div className="principle-card-head">
                        <span className="principle-layer-tag">DERIVED INTELLIGENCE</span>
                        <h4 className="principle-name">Intelligence Subsystem</h4>
                      </div>
                      <p className="principle-text">
                        Deliberately separated from data ingestion: transforms raw observations into candidate changes, assesses multi-factor significance, groups episodes, and ranks attention.
                      </p>
                    </div>

                    <div className="arch-principle-card">
                      <div className="principle-card-head">
                        <span className="principle-layer-tag">PROVIDER BOUNDARY</span>
                        <h4 className="principle-name">Data Sources &amp; Ingestion</h4>
                      </div>
                      <p className="principle-text">
                        NSE Bhavcopy and Marketaux remain isolated behind strict provider boundaries so schema formats and vendor idiosyncrasies never leak across the domain.
                      </p>
                    </div>

                    <div className="arch-principle-card arch-principle-card--span">
                      <div className="principle-card-head">
                        <span className="principle-layer-tag">DURABLE TRUTH</span>
                        <h4 className="principle-name">PostgreSQL &amp; Observation State</h4>
                      </div>
                      <p className="principle-text">
                        Stores both underlying market observations and personal check-in baselines (<code className="arch-code">user_observations</code>). This architectural separation allows Beacon to answer <em>&ldquo;What changed since I last checked?&rdquo;</em> without treating refreshed market-data snapshots as a replacement for the user&apos;s observation state.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Concise Implemented Capabilities Strip (Overview State Only) */}
              {!selectedComponent && (
                <div className="arch-capabilities-strip" aria-label="Capabilities powered by this architecture">
                  <div className="capabilities-header">
                    <span className="capabilities-label">POWERS IMPLEMENTED CAPABILITIES</span>
                  </div>
                  <div className="capabilities-pills">
                    <span className="capability-pill">Watchlists</span>
                    <span className="capability-pill">Market State</span>
                    <span className="capability-pill">Change Detection</span>
                    <span className="capability-pill">Significance</span>
                    <span className="capability-pill">Attention</span>
                    <span className="capability-pill">Explanation</span>
                    <span className="capability-pill">News Context</span>
                    <span className="capability-pill">Change Timeline</span>
                  </div>
                </div>
              )}
            </div>

            {/* Detailed Component Inspector Sidebar / Tray (when a component is drilled into) */}
            {activeComp && (
              <div className="arch-inspector-panel">
                <div className="inspector-head">
                  <div className="inspector-badge">{activeComp.badge}</div>
                  <h3 className="inspector-title">{activeComp.title}</h3>
                  <p className="inspector-subtitle">{activeComp.subtitle}</p>
                </div>

                <div className="inspector-explanation">
                  <p>{activeComp.explanation}</p>
                </div>

                {/* GitHub Implementation Links */}
                <div className="inspector-links-group">
                  <div className="links-group-title">
                    <FileCode2 size={13} style={{ color: 'var(--beacon-gold)', marginRight: '6px' }} />
                    <span>Repository Implementation</span>
                  </div>

                  <div className="impl-links-list">
                    {activeComp.links.map((link) => (
                      <a
                        key={link.path}
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="impl-link-card"
                      >
                        <div className="impl-link-info">
                          <code className="impl-link-name">{link.name}</code>
                          <span className="impl-link-desc">{link.desc}</span>
                        </div>
                        <span className="impl-link-action">
                          <span>View code</span>
                          <ExternalLink size={12} style={{ marginLeft: '4px' }} />
                        </span>
                      </a>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
