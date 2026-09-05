import { useState } from 'react';
import { Activity, Clock } from 'lucide-react';

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

export default function StockChart({ series, baselinePrice = null, symbol = '' }) {
  const [hoverIndex, setHoverIndex] = useState(null);

  if (!series || series.length === 0) {
    return (
      <div className="stock-chart-empty">
        <Activity size={24} className="empty-icon" />
        <span>No historical observation series available for charting {symbol ? `(${symbol})` : ''}.</span>
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
  if (baselinePrice !== null && !isNaN(baselinePrice)) {
    prices.push(Number(baselinePrice));
  }
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
    <div className="stock-chart-container" aria-label={`Price and volume chart for ${symbol}`}>
      <div className="stock-chart-legend">
        <div className="legend-item">
          <span className="legend-swatch legend-swatch--line" />
          <span>NSE Price Series</span>
        </div>
        <div className="legend-item">
          <span className="legend-swatch legend-swatch--baseline" />
          <span>Baseline (Last Checked)</span>
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
        <div className="chart-hover-indicator" role="tooltip">
          <div className="hover-indicator-row">
            <span className="hover-date">
              <Clock size={11} style={{ marginRight: '4px', verticalAlign: '-1px' }} />
              {formatDateTime(activePoint.observed_at)}
            </span>
            <span className="hover-price">₹{Number(activePoint.price).toFixed(2)}</span>
            {activePoint.volume && (
              <span className="hover-vol">Vol: {Number(activePoint.volume).toLocaleString('en-IN')}</span>
            )}
            {activePoint.is_baseline && (
              <span className="hover-tag hover-tag--baseline">Baseline</span>
            )}
            {activePoint.is_current && (
              <span className="hover-tag hover-tag--current">Current</span>
            )}
          </div>
        </div>
      )}

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="stock-chart-svg"
        onMouseLeave={() => setHoverIndex(null)}
      >
        <defs>
          <linearGradient id="beaconPriceGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#F59E0B" stopOpacity="0.30" />
            <stop offset="100%" stopColor="#F59E0B" stopOpacity="0.0" />
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
                className="chart-axis-label"
              >
                ₹{pVal.toFixed(1)}
              </text>
            </g>
          );
        })}

        {/* Baseline Price Dashed Guide Line if available */}
        {baselinePrice !== null && !isNaN(baselinePrice) && (
          <g className="chart-baseline-guide">
            <line
              x1={margin.left}
              y1={getY(Number(baselinePrice))}
              x2={width - margin.right}
              y2={getY(Number(baselinePrice))}
              stroke="#F59E0B"
              strokeDasharray="4 4"
              strokeWidth="1.2"
              opacity="0.8"
            />
            <text
              x={width - margin.right}
              y={getY(Number(baselinePrice)) - 5}
              fill="#F59E0B"
              fontSize="9"
              textAnchor="end"
              fontWeight="600"
            >
              Baseline: ₹{Number(baselinePrice).toFixed(2)}
            </text>
          </g>
        )}

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
          className="chart-axis-label"
        >
          Vol 0
        </text>
        <text
          x={margin.left - 8}
          y={volumeTop + 12}
          fill="var(--color-text-muted)"
          fontSize="10"
          textAnchor="end"
          className="chart-axis-label"
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
              fill={isHov ? '#F59E0B' : 'rgba(245, 158, 11, 0.28)'}
            />
          );
        })}

        {/* Area fill under curve */}
        {series.length > 1 && (
          <polygon points={areaPoints} fill="url(#beaconPriceGradient)" />
        )}

        {/* Price curve */}
        {series.length > 1 ? (
          <polyline
            points={linePoints}
            fill="none"
            stroke="#F59E0B"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : (
          <circle
            cx={getX(0)}
            cy={getY(Number(series[0].price))}
            r="5"
            fill="#F59E0B"
          />
        )}

        {/* Highlight Circles for Baseline & Current */}
        {series.map((pt, i) => {
          const cx = getX(i);
          const cy = getY(Number(pt.price));

          if (pt.is_baseline) {
            return (
              <g key={`marker-base-${i}`}>
                <circle cx={cx} cy={cy} r="9" fill="rgba(245, 158, 11, 0.25)" />
                <circle cx={cx} cy={cy} r="5" fill="#F59E0B" stroke="#0F172A" strokeWidth="2" />
                <rect
                  x={cx - 32}
                  y={cy - 24}
                  width="64"
                  height="16"
                  rx="3"
                  fill="#1E1B18"
                  stroke="#F59E0B"
                  strokeWidth="1"
                />
                <text
                  x={cx}
                  y={cy - 12}
                  fill="#F59E0B"
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
                <circle cx={cx} cy={cy} r="9" fill="rgba(16, 185, 129, 0.25)" />
                <circle cx={cx} cy={cy} r="5" fill="#10B981" stroke="#0F172A" strokeWidth="2" />
                <rect
                  x={cx - 28}
                  y={cy - 24}
                  width="56"
                  height="16"
                  rx="3"
                  fill="#06281E"
                  stroke="#10B981"
                  strokeWidth="1"
                />
                <text
                  x={cx}
                  y={cy - 12}
                  fill="#10B981"
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
