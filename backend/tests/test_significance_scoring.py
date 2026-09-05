import math
from decimal import Decimal
import pytest

from app.models.significance_assessment import SignificanceLevel
from app.services.significance_scoring import (
    compute_magnitude_score,
    compute_abnormality_score,
    compute_relative_performance_score,
    compute_volume_score,
    compute_event_score,
    calculate_significance,
    generate_explanation,
    WEIGHT_MAGNITUDE,
    WEIGHT_ABNORMALITY,
    WEIGHT_RELATIVE_PERFORMANCE,
    WEIGHT_VOLUME,
    WEIGHT_EVENT,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
    THRESHOLD_LOW,
)


def test_compute_magnitude_score_percentile():
    # >= 3 historical returns: uses empirical percentile rank
    hist = [0.01, 0.02, 0.03, 0.04, 0.05]
    score, ev = compute_magnitude_score(current_return=0.035, historical_abs_returns=hist)
    assert score is not None
    assert Decimal("0.0") <= score <= Decimal("1.0")
    assert ev["method"] == "empirical_percentile"
    assert ev["sample_size"] == 5
    # 0.035 is greater than 3 out of 5 -> rank = 3 / 5 = 0.6
    assert score == Decimal("0.6000")


def test_compute_magnitude_score_fallback():
    # < 3 historical returns: uses direct linear fallback min(|r| / 0.10, 1.0)
    score_small, ev_small = compute_magnitude_score(current_return=0.03, historical_abs_returns=[0.01])
    assert score_small == Decimal("0.3000")
    assert ev_small["method"] == "direct_linear_fallback_10pct"

    # 15% move caps at 1.0
    score_large, _ = compute_magnitude_score(current_return=0.15, historical_abs_returns=[])
    assert score_large == Decimal("1.0000")

    # None return returns None
    score_none, ev_none = compute_magnitude_score(current_return=None)
    assert score_none is None
    assert ev_none["status"] == "unavailable"


def test_compute_abnormality_score():
    # Standardized z-score mapped to min(|z| / 3.0, 1.0)
    # z = 0 -> 0.0
    score_zero, _ = compute_abnormality_score(z_score=0.0)
    assert score_zero == Decimal("0.0000")

    # z = 1.5 -> 0.5
    score_mid, _ = compute_abnormality_score(z_score=1.5)
    assert score_mid == Decimal("0.5000")

    # z = -3.0 -> 1.0 (symmetric)
    score_neg, _ = compute_abnormality_score(z_score=-3.0)
    assert score_neg == Decimal("1.0000")

    # z = 4.5 -> capped at 1.0
    score_cap, _ = compute_abnormality_score(z_score=4.5)
    assert score_cap == Decimal("1.0000")

    # Unavailable (insufficient history)
    score_none, ev_none = compute_abnormality_score(z_score=None)
    assert score_none is None
    assert ev_none["status"] == "insufficient_history_or_unavailable"


def test_compute_relative_performance_score():
    # Excess return mapped to min(|excess| / 0.05, 1.0)
    # 0 excess -> 0.0
    score_zero, _ = compute_relative_performance_score(excess_return=0.0)
    assert score_zero == Decimal("0.0000")

    # 2.5% excess -> 0.50
    score_mid, _ = compute_relative_performance_score(excess_return=0.025)
    assert score_mid == Decimal("0.5000")

    # -5% excess -> 1.00 (symmetric)
    score_five, _ = compute_relative_performance_score(excess_return=-0.05)
    assert score_five == Decimal("1.0000")

    # Benchmark unavailable
    score_none, ev_none = compute_relative_performance_score(excess_return=None)
    assert score_none is None
    assert ev_none["status"] == "benchmark_data_unavailable"


def test_compute_volume_score():
    # volume_score = min(abs(log(volume_ratio)) / log(2), 1.0)
    # ratio = 1.0 (identical to median) -> 0.0
    score_norm, _ = compute_volume_score(volume_ratio=1.0)
    assert score_norm == Decimal("0.0000")

    # ratio = 2.0 (double median) -> 1.0
    score_double, _ = compute_volume_score(volume_ratio=2.0)
    assert score_double == Decimal("1.0000")

    # ratio = 0.5 (half median) -> 1.0
    score_half, _ = compute_volume_score(volume_ratio=0.5)
    assert score_half == Decimal("1.0000")

    # ratio = 1.414 (~sqrt(2)) -> ~0.50
    score_sqrt, _ = compute_volume_score(volume_ratio=math.sqrt(2))
    assert score_sqrt == Decimal("0.5000")

    # ratio None or <= 0
    score_none, ev_none = compute_volume_score(volume_ratio=None)
    assert score_none is None
    assert ev_none["status"] == "insufficient_volume_history_or_unavailable"

    score_neg, ev_neg = compute_volume_score(volume_ratio=-1.0)
    assert score_neg is None
    assert ev_neg["status"] == "insufficient_volume_history_or_unavailable"


def test_compute_event_score():
    # No events -> 0.0
    score_empty, ev_empty = compute_event_score(events=[])
    assert score_empty == Decimal("0.0")
    assert ev_empty["has_events"] is False

    score_none, _ = compute_event_score(events=None)
    assert score_none == Decimal("0.0")

    # Verified events present -> 1.0
    score_present, ev_present = compute_event_score(events=[{"title": "Q2 Earnings", "impact": "high"}])
    assert score_present == Decimal("1.0")
    assert ev_present["has_events"] is True
    assert ev_present["event_count"] == 1


def test_calculate_significance_all_components_present():
    # When all 5 components are present, weights sum to 1.0
    res = calculate_significance(
        current_return=0.10,          # mag = 1.0 (weight 0.25)
        historical_abs_returns=[],    # fallback 10%
        z_score=3.0,                  # abn = 1.0 (weight 0.25)
        excess_return=0.05,           # rel = 1.0 (weight 0.20)
        volume_ratio=2.0,             # vol = 1.0 (weight 0.15)
        events=[{"type": "earnings"}], # ev = 1.0 (weight 0.15)
    )
    assert res.overall_score == Decimal("1.0000")
    assert res.significance_level == SignificanceLevel.HIGH
    assert res.evidence["available_weights"] == 1.0


def test_calculate_significance_missing_components_reweighted():
    # Missing relative performance and volume (no benchmark, insufficient volume history)
    # Magnitude: 0.05 -> fallback min(0.05/0.10, 1.0) = 0.50 (weight 0.25)
    # Abnormality: z = 1.5 -> 0.50 (weight 0.25)
    # Relative performance: None (weight 0.20 excluded)
    # Volume: None (weight 0.15 excluded)
    # Event: None -> 0.0 (weight 0.15 included)
    # Total available weight = 0.25 + 0.25 + 0.15 = 0.65
    # Weighted sum = 0.50*0.25 + 0.50*0.25 + 0.0*0.15 = 0.125 + 0.125 = 0.25
    # Overall score = 0.25 / 0.65 = 0.3846 -> MEDIUM threshold is >= 0.40, LOW is >= 0.20 -> LOW
    res = calculate_significance(
        current_return=0.05,
        z_score=1.5,
        excess_return=None,
        volume_ratio=None,
        events=None,
    )
    expected_score = Decimal(str(round(0.25 / 0.65, 4)))
    assert res.overall_score == expected_score
    assert res.significance_level == SignificanceLevel.LOW
    assert res.relative_performance_score is None
    assert res.volume_score is None
    assert res.evidence["available_weights"] == 0.65


def test_threshold_classification():
    # Check that thresholds match the specification:
    # HIGH >= 0.70, MEDIUM >= 0.40, LOW >= 0.20, NONE < 0.20
    assert THRESHOLD_HIGH == Decimal("0.70")
    assert THRESHOLD_MEDIUM == Decimal("0.40")
    assert THRESHOLD_LOW == Decimal("0.20")

    # High
    high_res = calculate_significance(current_return=0.10, z_score=3.0, excess_return=0.05)
    assert high_res.overall_score >= THRESHOLD_HIGH
    assert high_res.significance_level == SignificanceLevel.HIGH

    # None (negligible movement, e.g. 0.05% price change, z=0.1, no events)
    none_res = calculate_significance(
        current_return=0.0005,
        z_score=0.1,
        excess_return=0.0005,
        volume_ratio=1.0,
        events=None,
    )
    assert none_res.overall_score < THRESHOLD_LOW
    assert none_res.significance_level == SignificanceLevel.NONE


def test_explanation_non_causal_and_transparent():
    # Explanation must never contain causal language ("caused by")
    # Must use non-causal language ("accompanied by", "coincided with")
    # and explicitly note missing benchmark/history
    res = calculate_significance(
        current_return=0.08,
        z_score=2.8,
        excess_return=None,
        volume_ratio=1.8,
        events=None,
        price_evidence={"percentage_change": 8.0},
    )
    exp = res.explanation.lower()
    assert "caused by" not in exp
    assert "because of" not in exp
    # Mentions accompanied or unusual
    assert "accompanied by" in exp or "unusually" in exp or "noteworthy" in exp
    # Discloses missing benchmark
    assert "benchmark comparison unavailable" in exp
