from collections import defaultdict
from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detected_change import ChangeType, DetectedChange
from app.models.market_observation import MarketObservation
from app.models.significance_assessment import SignificanceAssessment
from app.providers.benchmark import BenchmarkProvider, NSEBenchmarkProvider
from app.providers.events import MaterialEventProvider, NullMaterialEventProvider
from app.schemas.attention import (
    AttentionItem,
    AttentionSummary,
    ComponentScores,
    WatchlistAttentionResponse,
)
from app.services.change_detection import detect_changes_for_watchlist
from app.services.significance_scoring import calculate_significance


async def get_watchlist_attention(
    db: AsyncSession,
    user_id: int,
    watchlist_id: int,
    benchmark_provider: BenchmarkProvider | None = None,
    event_provider: MaterialEventProvider | None = None,
) -> WatchlistAttentionResponse:
    """
    Evaluates candidate changes for a watchlist against the user's observation baseline,
    computes deterministic significance assessments, persists assessments idempotently,
    groups changes by instrument episode, and returns a ranked attention feed.
    """
    if benchmark_provider is None:
        benchmark_provider = NSEBenchmarkProvider()
    if event_provider is None:
        event_provider = NullMaterialEventProvider()

    # 1. Run change detection for the watchlist (persists/updates DetectedChange records)
    changes_result = await detect_changes_for_watchlist(
        db=db,
        user_id=user_id,
        watchlist_id=watchlist_id,
        benchmark_provider=benchmark_provider,
        event_provider=event_provider,
    )

    # Map instrument statuses by instrument_id
    status_by_instrument = {s.instrument_id: s for s in changes_result.instrument_statuses}

    # Group candidate changes by instrument_id (the unit of an episode)
    changes_by_instrument: dict[int, list[DetectedChange]] = defaultdict(list)
    for ch in changes_result.changes:
        changes_by_instrument[ch.instrument_id].append(ch)

    all_items: list[AttentionItem] = []

    for instrument_id, changes_list in changes_by_instrument.items():
        first_ch = changes_list[0]
        inst = first_ch.instrument
        base_obs = first_ch.baseline_observation
        curr_obs = first_ch.current_observation

        status_info = status_by_instrument.get(instrument_id)
        diagnostics: dict[str, Any] = status_info.diagnostics if status_info else {}

        constituent_change_types = sorted(list({ch.change_type for ch in changes_list}))

        # -------------------------------------------------------------
        # Gather Component 1: Price / Magnitude
        # -------------------------------------------------------------
        price_move_ch = next((ch for ch in changes_list if ch.change_type == ChangeType.PRICE_MOVE.value), None)
        if price_move_ch and price_move_ch.evidence:
            pct_change = price_move_ch.evidence.get("percentage_change")
            current_return = (pct_change / 100.0) if pct_change is not None else None
            price_evidence = price_move_ch.evidence
        elif base_obs and curr_obs and base_obs.price > Decimal("0"):
            p_base = float(base_obs.price)
            p_curr = float(curr_obs.price)
            ret = (p_curr - p_base) / p_base
            pct_change = ret * 100.0
            current_return = ret
            price_evidence = {
                "baseline_price": p_base,
                "current_price": p_curr,
                "absolute_change": round(p_curr - p_base, 4),
                "percentage_change": round(pct_change, 4),
            }
        else:
            current_return = None
            price_evidence = {}

        # Fetch strictly prior observations for empirical percentile rank
        hist_abs_returns: list[float] = []
        if curr_obs and inst:
            hist_stmt = (
                select(MarketObservation.price)
                .where(
                    MarketObservation.instrument_id == inst.id,
                    MarketObservation.source == curr_obs.source,
                    MarketObservation.observed_at < curr_obs.observed_at,
                )
                .order_by(MarketObservation.observed_at.asc())
                .limit(30)
            )
            hist_prices = (await db.execute(hist_stmt)).scalars().all()
            for i in range(1, len(hist_prices)):
                p0 = hist_prices[i - 1]
                p1 = hist_prices[i]
                if p0 > Decimal("0"):
                    hist_abs_returns.append(abs(float((p1 - p0) / p0)))

        # -------------------------------------------------------------
        # Gather Component 2: Abnormality (Z-score)
        # -------------------------------------------------------------
        abn_ch = next((ch for ch in changes_list if ch.change_type == ChangeType.ABNORMAL_RETURN.value), None)
        if abn_ch and abn_ch.evidence and "z_score" in abn_ch.evidence:
            z_score = float(abn_ch.evidence["z_score"])
            abnormality_meta = abn_ch.evidence
        else:
            z_score = None
            abnormality_meta = diagnostics.get("abnormal_return", {"status": "insufficient_history_or_unavailable"})

        # -------------------------------------------------------------
        # Gather Component 3: Relative Performance
        # -------------------------------------------------------------
        rel_ch = next((ch for ch in changes_list if ch.change_type == ChangeType.RELATIVE_PERFORMANCE.value), None)
        if rel_ch and rel_ch.evidence and "excess_return" in rel_ch.evidence:
            excess_return = float(rel_ch.evidence["excess_return"])
            benchmark_symbol = rel_ch.evidence.get("benchmark_symbol", "NIFTY 50")
        else:
            excess_return = None
            benchmark_symbol = "NIFTY 50"

        # -------------------------------------------------------------
        # Gather Component 4: Volume
        # -------------------------------------------------------------
        vol_ch = next((ch for ch in changes_list if ch.change_type == ChangeType.VOLUME_ANOMALY.value), None)
        if vol_ch and vol_ch.evidence and "volume_ratio" in vol_ch.evidence:
            volume_ratio = float(vol_ch.evidence["volume_ratio"])
            volume_sample_size = int(vol_ch.evidence.get("sample_size", 0))
        elif "volume_anomaly" in diagnostics and diagnostics["volume_anomaly"].get("status") == "normal_volume":
            volume_ratio = float(diagnostics["volume_anomaly"].get("volume_ratio", 1.0))
            volume_sample_size = int(diagnostics["volume_anomaly"].get("sample_size", 0))
        else:
            volume_ratio = None
            volume_sample_size = 0

        # -------------------------------------------------------------
        # Gather Component 5: Material Events
        # -------------------------------------------------------------
        event_changes = [ch for ch in changes_list if ch.change_type == ChangeType.MATERIAL_EVENT.value]
        events = [ch.evidence for ch in event_changes if ch.evidence] if event_changes else None

        # -------------------------------------------------------------
        # Compute Significance
        # -------------------------------------------------------------
        score_result = calculate_significance(
            current_return=current_return,
            historical_abs_returns=hist_abs_returns,
            z_score=z_score,
            abnormality_meta=abnormality_meta,
            excess_return=excess_return,
            benchmark_symbol=benchmark_symbol,
            volume_ratio=volume_ratio,
            volume_sample_size=volume_sample_size,
            events=events,
            price_evidence=price_evidence,
        )

        # -------------------------------------------------------------
        # Persist SignificanceAssessment for each DetectedChange idempotently
        # -------------------------------------------------------------
        for ch in changes_list:
            ass_stmt = select(SignificanceAssessment).where(
                SignificanceAssessment.detected_change_id == ch.id
            )
            ass_res = await db.execute(ass_stmt)
            ass = ass_res.scalar_one_or_none()

            if ass is None:
                ass = SignificanceAssessment(
                    detected_change_id=ch.id,
                    magnitude_score=score_result.magnitude_score,
                    abnormality_score=score_result.abnormality_score,
                    relative_performance_score=score_result.relative_performance_score,
                    volume_score=score_result.volume_score,
                    event_score=score_result.event_score,
                    overall_score=score_result.overall_score,
                    significance_level=score_result.significance_level.value,
                    evidence=score_result.evidence,
                    explanation=score_result.explanation,
                )
                db.add(ass)
            else:
                ass.magnitude_score = score_result.magnitude_score
                ass.abnormality_score = score_result.abnormality_score
                ass.relative_performance_score = score_result.relative_performance_score
                ass.volume_score = score_result.volume_score
                ass.event_score = score_result.event_score
                ass.overall_score = score_result.overall_score
                ass.significance_level = score_result.significance_level.value
                ass.evidence = score_result.evidence
                ass.explanation = score_result.explanation

        # -------------------------------------------------------------
        # Construct AttentionItem for the Episode
        # -------------------------------------------------------------
        item = AttentionItem(
            instrument_id=inst.id if inst else instrument_id,
            symbol=inst.nse_symbol if inst else "",
            company_name=inst.company_name if inst else "",
            significance_level=score_result.significance_level.value,
            overall_score=score_result.overall_score,
            component_scores=ComponentScores(
                magnitude=score_result.magnitude_score,
                abnormality=score_result.abnormality_score,
                relative_performance=score_result.relative_performance_score,
                volume=score_result.volume_score,
                event=score_result.event_score,
            ),
            explanation=score_result.explanation,
            evidence=score_result.evidence,
            constituent_change_types=constituent_change_types,
            baseline_observation_id=base_obs.id if base_obs else first_ch.baseline_observation_id,
            baseline_price=base_obs.price if base_obs else None,
            baseline_observed_at=base_obs.observed_at if base_obs else None,
            current_observation_id=curr_obs.id if curr_obs else first_ch.current_observation_id,
            current_price=curr_obs.price if curr_obs else None,
            current_observed_at=curr_obs.observed_at if curr_obs else None,
            source=curr_obs.source if curr_obs else "NSE",
            data_status=curr_obs.data_status if curr_obs else "final",
        )
        all_items.append(item)

    await db.commit()

    # Filter: items deserving attention have significance >= LOW (HIGH, MEDIUM, LOW)
    # Items with NONE level are omitted from active attention cards
    meaningful_items = [
        item for item in all_items if item.significance_level in ("HIGH", "MEDIUM", "LOW")
    ]

    # Deterministic ranking:
    # 1. overall_score DESCENDING
    # 2. available evidence count DESCENDING
    # 3. symbol ASCENDING
    def ranking_key(it: AttentionItem):
        available_count = sum(
            1 for s in [
                it.component_scores.magnitude,
                it.component_scores.abnormality,
                it.component_scores.relative_performance,
                it.component_scores.volume,
                it.component_scores.event,
            ] if s is not None
        )
        return (-it.overall_score, -available_count, it.symbol)

    ranked_attention_items = sorted(meaningful_items, key=ranking_key)

    total_inst = len(changes_result.instrument_statuses)
    inst_with_changes = len(changes_by_instrument)
    inst_with_meaningful = len(ranked_attention_items)
    inst_without_meaningful = max(0, total_inst - inst_with_meaningful)

    high_count = sum(1 for it in ranked_attention_items if it.significance_level == "HIGH")
    medium_count = sum(1 for it in ranked_attention_items if it.significance_level == "MEDIUM")
    low_count = sum(1 for it in ranked_attention_items if it.significance_level == "LOW")

    summary = AttentionSummary(
        total_instruments=total_inst,
        instruments_with_changes=inst_with_changes,
        instruments_with_meaningful_changes=inst_with_meaningful,
        instruments_without_meaningful_changes=inst_without_meaningful,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
    )

    return WatchlistAttentionResponse(
        watchlist_id=changes_result.watchlist_id,
        watchlist_name=changes_result.watchlist_name,
        last_checked_at=changes_result.last_checked_at,
        attention_items=ranked_attention_items,
        summary=summary,
    )
