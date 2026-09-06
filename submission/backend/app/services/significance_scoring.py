import logging
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models.significance_assessment import SignificanceAssessment, SignificanceLevel

logger = logging.getLogger(__name__)

# ==============================================================================
# V1 Product Heuristic Scoring Weights
# ==============================================================================
# Documented Rationale:
# - Magnitude (0.25) & Abnormality (0.25): Strongest direct evidence that the
#   observed movement itself is unusual relative to the stock's own distribution.
# - Relative Performance (0.20): Provides essential whole-market context
#   (distinguishing market-wide drift from stock-specific movement).
# - Volume (0.15): Corroborating trading activity confirming institutional or retail conviction.
# - Material Event (0.15): Company-specific filings / corporate events context.
#
# Note: These weights are explicit V1 product heuristics, not universal financial laws.
# ==============================================================================
WEIGHT_MAGNITUDE = Decimal("0.25")
WEIGHT_ABNORMALITY = Decimal("0.25")
WEIGHT_RELATIVE_PERFORMANCE = Decimal("0.20")
WEIGHT_VOLUME = Decimal("0.15")
WEIGHT_EVENT = Decimal("0.15")

WEIGHTS = {
    "magnitude": WEIGHT_MAGNITUDE,
    "abnormality": WEIGHT_ABNORMALITY,
    "relative_performance": WEIGHT_RELATIVE_PERFORMANCE,
    "volume": WEIGHT_VOLUME,
    "event": WEIGHT_EVENT,
}

# Significance level thresholds (V1 heuristics)
THRESHOLD_HIGH = Decimal("0.70")
THRESHOLD_MEDIUM = Decimal("0.40")
THRESHOLD_LOW = Decimal("0.20")


@dataclass
class SignificanceScoreResult:
    magnitude_score: Decimal | None
    abnormality_score: Decimal | None
    relative_performance_score: Decimal | None
    volume_score: Decimal | None
    event_score: Decimal | None
    overall_score: Decimal
    significance_level: SignificanceLevel
    evidence: dict[str, Any]
    explanation: str


def compute_magnitude_score(
    current_return: float | Decimal | None,
    historical_abs_returns: list[float] | None = None,
) -> tuple[Decimal | None, dict[str, Any]]:
    """
    Computes magnitude score in [0, 1] representing how large the movement is
    relative to the stock's own historical absolute returns distribution.
    Uses empirical percentile rank when >= 3 historical returns exist.
    Uses a documented linear fallback min(|r| / 0.10, 1.0) otherwise.
    """
    if current_return is None:
        return None, {"status": "unavailable"}

    r_curr = abs(float(current_return))

    if historical_abs_returns and len(historical_abs_returns) >= 3:
        # Empirical percentile rank strictly prior to current observation
        n = len(historical_abs_returns)
        strictly_less = sum(1 for h in historical_abs_returns if h < r_curr)
        equal = sum(1 for h in historical_abs_returns if h == r_curr)
        rank = (strictly_less + 0.5 * equal) / float(n)
        rank = max(0.0, min(1.0, rank))

        # Scale by absolute magnitude if return is below 1% to prevent microscopic moves
        # (<0.01) from receiving high percentile scores due to flat historical ties
        scale = min(r_curr / 0.01, 1.0)
        rank_scaled = rank * scale

        score = Decimal(str(round(rank_scaled, 4)))
        return score, {
            "method": "empirical_percentile",
            "percentile": round(rank * 100, 2),
            "sample_size": n,
            "current_abs_return": round(r_curr, 6),
        }
    else:
        # Bounded fallback: 10% move maps to 1.0
        val = min(r_curr / 0.10, 1.0)
        score = Decimal(str(round(val, 4)))
        return score, {
            "method": "direct_linear_fallback_10pct",
            "sample_size": len(historical_abs_returns) if historical_abs_returns else 0,
            "current_abs_return": round(r_curr, 6),
        }



def compute_abnormality_score(
    z_score: float | None,
    evidence_meta: dict[str, Any] | None = None,
) -> tuple[Decimal | None, dict[str, Any]]:
    """
    Maps standardized z-score to bounded [0, 1]: min(|z| / 3.0, 1.0).
    z=0 -> 0, z=1.5 -> 0.5, |z|>=3 -> 1.0.
    Returns None if z_score is unavailable due to insufficient historical observations.
    """
    if z_score is None:
        return None, {"status": "insufficient_history_or_unavailable"}

    val = min(abs(float(z_score)) / 3.0, 1.0)
    score = Decimal(str(round(val, 4)))
    ev = {
        "z_score": round(float(z_score), 4),
        "method": "bounded_linear_z3",
    }
    if evidence_meta:
        ev.update({k: v for k, v in evidence_meta.items() if k != "z_score"})
    return score, ev


def compute_relative_performance_score(
    excess_return: float | Decimal | None,
    benchmark_symbol: str = "NIFTY 50",
) -> tuple[Decimal | None, dict[str, Any]]:
    """
    Maps excess return (stock_return - benchmark_return) to bounded [0, 1].
    Uses bounded mapping min(|excess_return| / 0.05, 1.0) (5% excess return = 1.0).
    Returns None if benchmark data is unavailable.
    """
    if excess_return is None:
        return None, {
            "status": "benchmark_data_unavailable",
            "benchmark_symbol": benchmark_symbol,
        }

    x = abs(float(excess_return))
    val = min(x / 0.05, 1.0)
    score = Decimal(str(round(val, 4)))
    return score, {
        "excess_return": round(float(excess_return), 6),
        "benchmark_symbol": benchmark_symbol,
        "method": "bounded_linear_5pct",
    }


def compute_volume_score(
    volume_ratio: float | None,
    sample_size: int = 0,
) -> tuple[Decimal | None, dict[str, Any]]:
    """
    Converts volume ratio (current_volume / historical_median) to symmetric bounded [0, 1]:
    volume_score = min(abs(log(volume_ratio)) / log(2), 1.0).
    ratio=1 -> 0, ratio=2 -> 1, ratio=0.5 -> 1.
    Returns None if volume or historical baseline is insufficient.
    """
    if volume_ratio is None or volume_ratio <= 0:
        return None, {"status": "insufficient_volume_history_or_unavailable"}

    try:
        dev = abs(math.log(float(volume_ratio))) / math.log(2.0)
        val = min(dev, 1.0)
        score = Decimal(str(round(val, 4)))
        return score, {
            "volume_ratio": round(float(volume_ratio), 4),
            "method": "symmetric_log2_cap1",
            "sample_size": sample_size,
        }
    except (ValueError, ZeroDivisionError):
        return None, {"status": "invalid_volume_ratio"}


def compute_event_score(
    events: list[dict[str, Any]] | None,
) -> tuple[Decimal, dict[str, Any]]:
    """
    Assigns event score. In V1 without a connected external provider, defaults to 0.0.
    Never fabricates events.
    """
    if not events:
        return Decimal("0.0"), {"has_events": False, "event_count": 0}

    # Verified events present
    return Decimal("1.0"), {
        "has_events": True,
        "event_count": len(events),
        "events": events,
    }


def generate_explanation(
    level: SignificanceLevel,
    mag_score: Decimal | None,
    abn_score: Decimal | None,
    rel_score: Decimal | None,
    vol_score: Decimal | None,
    event_score: Decimal | None,
    evidence: dict[str, Any],
) -> str:
    """
    Generates a deterministic, non-causal explanation based strictly on stored evidence.
    Never states 'caused by'. Uses 'accompanied by', 'coincided with', 'was observed alongside'.
    """
    sentences: list[str] = []

    # 1. Primary Movement description
    pct_change = evidence.get("price", {}).get("percentage_change")
    z_score = evidence.get("abnormality", {}).get("z_score")
    vol_ratio = evidence.get("volume", {}).get("volume_ratio")
    excess_ret = evidence.get("relative_performance", {}).get("excess_return")
    benchmark_sym = evidence.get("relative_performance", {}).get("benchmark_symbol", "benchmark")

    if level == SignificanceLevel.HIGH:
        if abn_score is not None and abn_score >= Decimal("0.70"):
            sentences.append("Unusually large price movement relative to this stock's recent history")
        elif pct_change is not None:
            sentences.append(f"Substantial price movement of {abs(pct_change):.2f}%")
        else:
            sentences.append("High magnitude market movement detected")

        corroborations: list[str] = []
        if vol_ratio is not None and vol_ratio >= 1.25:
            corroborations.append(f"above-normal trading volume ({vol_ratio:.1f}× recent median)")
        elif vol_ratio is not None and vol_ratio <= 0.75:
            corroborations.append(f"unusually low volume ({vol_ratio:.1f}× recent median)")

        if rel_score is not None and rel_score >= Decimal("0.50") and excess_ret is not None:
            dir_str = "outperformed" if excess_ret > 0 else "underperformed"
            corroborations.append(f"{dir_str} {benchmark_sym} by {abs(excess_ret * 100):.2f} percentage points")

        if corroborations:
            sentences[0] += ", accompanied by " + ", and ".join(corroborations) + "."
        else:
            sentences[0] += "."

    elif level == SignificanceLevel.MEDIUM:
        if abn_score is not None and abn_score >= Decimal("0.40"):
            sentences.append("Price movement was larger than typical for this stock, with moderate supporting evidence.")
        elif pct_change is not None:
            sentences.append(f"Noteworthy price movement of {pct_change:+.2f}%, accompanied by limited secondary signals.")
        else:
            sentences.append("Moderate market change detected with partial corroborating evidence.")

    elif level == SignificanceLevel.LOW:
        sentences.append("Price changed modestly with limited evidence of unusual historical behavior.")

    else:  # NONE
        sentences.append("Movement remained within normal historical variance.")

    # 2. Add explicit note for missing data
    missing_notes: list[str] = []
    if evidence.get("relative_performance", {}).get("status") == "benchmark_data_unavailable":
        missing_notes.append("Benchmark comparison unavailable")
    if evidence.get("abnormality", {}).get("status") == "insufficient_history_or_unavailable":
        missing_notes.append("insufficient history for statistical abnormality calculation")
    if evidence.get("volume", {}).get("status") == "insufficient_volume_history_or_unavailable":
        missing_notes.append("insufficient volume history")

    if missing_notes:
        sentences.append(f"({'; '.join(missing_notes)}).")

    return " ".join(sentences)


def generate_structured_explanation(
    symbol: str,
    level: SignificanceLevel,
    mag_score: Decimal | None,
    abn_score: Decimal | None,
    rel_score: Decimal | None,
    vol_score: Decimal | None,
    event_score: Decimal | None,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """
    Generates a structured, evidence-based, non-causal explanation with:
    - what_happened: factual movement description
    - why_it_stands_out: primary context why it surfaced
    - supporting_evidence: list of corroborating evidence bullets
    - missing_data_notes: explicit disclosures of unavailable data
    Never states unsupported causality (e.g. 'caused by').
    """
    pct_change = evidence.get("price", {}).get("percentage_change")
    abs_change = evidence.get("price", {}).get("absolute_change")
    z_score = evidence.get("abnormality", {}).get("z_score")
    vol_ratio = evidence.get("volume", {}).get("volume_ratio")
    excess_ret = evidence.get("relative_performance", {}).get("excess_return")
    benchmark_sym = evidence.get("relative_performance", {}).get("benchmark_symbol", "benchmark")
    events = evidence.get("event", {}).get("events") or []

    # 1. What happened
    if pct_change is not None:
        sign = "+" if pct_change > 0 else ""
        if abs_change is not None:
            what_happened = f"{symbol} moved {sign}{pct_change:.2f}% ({sign}₹{abs_change:.2f}) since you last checked."
        else:
            what_happened = f"{symbol} moved {sign}{pct_change:.2f}% since you last checked."
    else:
        what_happened = f"Market change detected for {symbol} since you last checked."

    # 2. Why it stands out
    if level == SignificanceLevel.HIGH:
        if abn_score is not None and abn_score >= Decimal("0.70"):
            why_it_stands_out = f"The move was unusually large relative to {symbol}'s recent history."
        else:
            why_it_stands_out = "Substantial price movement detected with strong corroborating evidence."
    elif level == SignificanceLevel.MEDIUM:
        if abn_score is not None and abn_score >= Decimal("0.40"):
            why_it_stands_out = f"Price movement was larger than typical for {symbol}, with moderate corroborating signals."
        else:
            why_it_stands_out = "Noteworthy market movement with partial supporting evidence."
    elif level == SignificanceLevel.LOW:
        why_it_stands_out = "Price changed modestly, with some evidence of unusual activity."
    else:
        why_it_stands_out = "Movement remained within normal historical variance."

    # 3. Supporting evidence
    supporting_evidence: list[str] = []
    if vol_ratio is not None:
        if vol_ratio >= 1.25:
            supporting_evidence.append(f"Trading volume was approximately {vol_ratio:.1f}× its recent median.")
        elif vol_ratio <= 0.75:
            supporting_evidence.append(f"Trading volume was unusually low ({vol_ratio:.1f}× its recent median).")

    if excess_ret is not None:
        dir_str = "outperformed" if excess_ret > 0 else "underperformed"
        bm_ret = evidence.get("relative_performance", {}).get("benchmark_return")
        stock_ret = evidence.get("relative_performance", {}).get("stock_return")
        if bm_ret is not None and stock_ret is not None:
            s_action = "gained" if stock_ret >= 0 else "declined"
            b_action = "gained" if bm_ret >= 0 else "declined"
            supporting_evidence.append(
                f"{symbol} {s_action} {abs(stock_ret * 100):.1f}% while {benchmark_sym} {b_action} {abs(bm_ret * 100):.1f}%, indicating {dir_str} benchmark by {abs(excess_ret * 100):.2f} percentage points."
            )
        else:
            supporting_evidence.append(f"The stock {dir_str} {benchmark_sym} by {abs(excess_ret * 100):.2f} percentage points.")

    if z_score is not None and abs(z_score) >= 1.0:
        supporting_evidence.append(f"The move was unusually large relative to recent return distribution (z = {z_score:+.2f}).")

    if events:
        first_ev = events[0] if isinstance(events, list) and events else {}
        ev_title = first_ev.get("title") or first_ev.get("description") or "Material corporate event"
        supporting_evidence.append(f"Potentially relevant company context: {ev_title} coincided with this period.")

    # 4. Missing data notes
    missing_data_notes: list[str] = []
    if evidence.get("relative_performance", {}).get("status") == "benchmark_data_unavailable":
        missing_data_notes.append("Benchmark comparison unavailable")
    if evidence.get("abnormality", {}).get("status") == "insufficient_history_or_unavailable":
        missing_data_notes.append("Insufficient history for statistical abnormality calculation")
    if evidence.get("volume", {}).get("status") == "insufficient_volume_history_or_unavailable":
        missing_data_notes.append("Insufficient volume history")

    return {
        "what_happened": what_happened,
        "why_it_stands_out": why_it_stands_out,
        "supporting_evidence": supporting_evidence,
        "missing_data_notes": missing_data_notes,
    }


def compute_evidence_completeness(
    level: SignificanceLevel,
    mag_score: Decimal | None,
    abn_score: Decimal | None,
    rel_score: Decimal | None,
    vol_score: Decimal | None,
    event_score: Decimal | None,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluates evidence quality distinguishing:
    'Something significant happened' from 'We have enough evidence to confidently explain what happened.'
    Identifies available corroborating signals vs missing market context.
    """
    available_signals: list[str] = []
    missing_signals: list[str] = []

    # Price / Magnitude
    if mag_score is not None:
        available_signals.append("price move")

    # Abnormality
    if abn_score is not None:
        available_signals.append("historical volatility")
    elif evidence.get("abnormality", {}).get("status") == "insufficient_history_or_unavailable":
        missing_signals.append("historical volatility distribution")

    # Relative performance
    if rel_score is not None:
        available_signals.append("relative-performance")
    elif evidence.get("relative_performance", {}).get("status") == "benchmark_data_unavailable":
        missing_signals.append("benchmark comparison")

    # Volume
    if vol_score is not None:
        available_signals.append("volume")
    elif evidence.get("volume", {}).get("status") == "insufficient_volume_history_or_unavailable":
        missing_signals.append("volume history")

    # Material event
    if event_score is not None and event_score > Decimal("0.0"):
        available_signals.append("company event")

    # Corroborating signals count beyond raw price move
    corroborating_count = len([s for s in available_signals if s != "price move"])

    level_name = level.value.capitalize()
    if corroborating_count >= 2:
        completeness_level = "STRONG"
        summary_str = f"{level_name} significance — supported by {', '.join(available_signals)} signals."
    elif corroborating_count == 1:
        completeness_level = "MODERATE"
        summary_str = f"{level_name} significance — supported by {', '.join(available_signals)}."
        if missing_signals:
            summary_str += f" ({missing_signals[0]} unavailable)."
    else:
        completeness_level = "LIMITED"
        summary_str = f"{level_name} significance — large price movement detected, but supporting market context is unavailable."

    return {
        "level": completeness_level,
        "available_signals_count": len(available_signals),
        "total_signals_count": 5,
        "summary": summary_str,
        "available_signals": available_signals,
        "missing_signals": missing_signals,
    }


def format_freshness_note(source: str = "NSE", current_observed_at: Any = None) -> str:
    """
    Formats transparent data provenance and freshness note.
    Never refers to historical end-of-day data as 'live'.
    """
    if current_observed_at and hasattr(current_observed_at, "strftime"):
        date_str = current_observed_at.strftime("%b %d, %Y, %I:%M %p")
        return f"Based on {source} market data through {date_str} IST."
    return f"Based on {source} market data."



def calculate_significance(
    current_return: float | Decimal | None,
    historical_abs_returns: list[float] | None = None,
    z_score: float | None = None,
    abnormality_meta: dict[str, Any] | None = None,
    excess_return: float | Decimal | None = None,
    benchmark_symbol: str = "NIFTY 50",
    volume_ratio: float | None = None,
    volume_sample_size: int = 0,
    events: list[dict[str, Any]] | None = None,
    price_evidence: dict[str, Any] | None = None,
) -> SignificanceScoreResult:
    """
    Computes overall significance score using normalized weighted average over
    AVAILABLE components only. Excluded components do not penalize the score.
    """
    mag_score, mag_ev = compute_magnitude_score(current_return, historical_abs_returns)
    abn_score, abn_ev = compute_abnormality_score(z_score, abnormality_meta)
    rel_score, rel_ev = compute_relative_performance_score(excess_return, benchmark_symbol)
    vol_score, vol_ev = compute_volume_score(volume_ratio, volume_sample_size)
    ev_score, ev_ev = compute_event_score(events)

    components: list[tuple[str, Decimal | None, Decimal]] = [
        ("magnitude", mag_score, WEIGHT_MAGNITUDE),
        ("abnormality", abn_score, WEIGHT_ABNORMALITY),
        ("relative_performance", rel_score, WEIGHT_RELATIVE_PERFORMANCE),
        ("volume", vol_score, WEIGHT_VOLUME),
        ("event", ev_score, WEIGHT_EVENT),
    ]

    # Calculate normalized weighted average over AVAILABLE components
    weighted_sum = Decimal("0.0")
    weights_sum = Decimal("0.0")

    for name, score, weight in components:
        if score is not None:
            weighted_sum += score * weight
            weights_sum += weight

    if weights_sum > Decimal("0.0"):
        overall_score = weighted_sum / weights_sum
    else:
        overall_score = Decimal("0.0")

    overall_score = max(Decimal("0.0"), min(Decimal("1.0"), overall_score))
    overall_score = Decimal(str(round(overall_score, 4)))

    # Determine significance level
    if overall_score >= THRESHOLD_HIGH:
        level = SignificanceLevel.HIGH
    elif overall_score >= THRESHOLD_MEDIUM:
        level = SignificanceLevel.MEDIUM
    elif overall_score >= THRESHOLD_LOW:
        level = SignificanceLevel.LOW
    else:
        level = SignificanceLevel.NONE

    combined_evidence = {
        "price": price_evidence or {},
        "magnitude": mag_ev,
        "abnormality": abn_ev,
        "relative_performance": rel_ev,
        "volume": vol_ev,
        "event": ev_ev,
        "available_weights": float(weights_sum),
        "normalized_overall_score": float(overall_score),
    }

    explanation = generate_explanation(
        level=level,
        mag_score=mag_score,
        abn_score=abn_score,
        rel_score=rel_score,
        vol_score=vol_score,
        event_score=ev_score,
        evidence=combined_evidence,
    )

    return SignificanceScoreResult(
        magnitude_score=mag_score,
        abnormality_score=abn_score,
        relative_performance_score=rel_score,
        volume_score=vol_score,
        event_score=ev_score,
        overall_score=overall_score,
        significance_level=level,
        evidence=combined_evidence,
        explanation=explanation,
    )
