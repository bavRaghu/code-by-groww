import logging
from collections import defaultdict
from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detected_change import ChangeType, DetectedChange
from app.models.market_observation import MarketObservation
from app.models.significance_assessment import SignificanceAssessment, SignificanceLevel
from app.providers.benchmark import BenchmarkProvider, NSEBenchmarkProvider
from app.providers.events import MaterialEventProvider, NullMaterialEventProvider
from app.schemas.attention import (
    AttentionItem,
    AttentionSummary,
    ChangeFeedItem,
    ComponentScores,
    EvidenceCompleteness,
    InsufficientDataItem,
    InstrumentReference,
    QuietInstrumentItem,
    StructuredExplanation,
    UnderlyingChangeSummary,
    WatchlistAttentionResponse,
)
from app.services.change_detection import detect_changes_for_watchlist
from app.services.significance_scoring import (
    calculate_significance,
    compute_evidence_completeness,
    format_freshness_note,
    generate_structured_explanation,
)

logger = logging.getLogger(__name__)

LEVEL_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}


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
    groups changes by instrument episode, isolates per-instrument scoring failures,
    and returns a ranked attention feed with clear structured explanations.
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
    quiet_instruments: list[QuietInstrumentItem] = []
    insufficient_data_instruments: list[InsufficientDataItem] = []

    # Identify instruments that could not be fully assessed due to lack of baseline or market data
    for s in changes_result.instrument_statuses:
        if s.status in ("no_baseline", "insufficient_data"):
            reason = s.diagnostics.get("message", "Insufficient baseline or market observation data.")
            insufficient_data_instruments.append(
                InsufficientDataItem(
                    instrument_id=s.instrument_id,
                    symbol=s.symbol,
                    company_name=s.company_name,
                    reason=reason,
                )
            )

    # Process each instrument episode with candidate changes
    for instrument_id, changes_list in changes_by_instrument.items():
        first_ch = changes_list[0]
        inst = first_ch.instrument
        base_obs = first_ch.baseline_observation
        curr_obs = first_ch.current_observation

        status_info = status_by_instrument.get(instrument_id)
        diagnostics: dict[str, Any] = status_info.diagnostics if status_info else {}

        constituent_change_types = sorted(list({ch.change_type for ch in changes_list}))

        try:
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

            # Persist SignificanceAssessment for each DetectedChange idempotently
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

            # Structured explanation
            symbol_str = inst.nse_symbol if inst else f"ID #{instrument_id}"
            structured_exp = generate_structured_explanation(
                symbol=symbol_str,
                level=score_result.significance_level,
                mag_score=score_result.magnitude_score,
                abn_score=score_result.abnormality_score,
                rel_score=score_result.relative_performance_score,
                vol_score=score_result.volume_score,
                event_score=score_result.event_score,
                evidence=score_result.evidence,
            )

            # Compute evidence completeness
            completeness_data = compute_evidence_completeness(
                level=score_result.significance_level,
                mag_score=score_result.magnitude_score,
                abn_score=score_result.abnormality_score,
                rel_score=score_result.relative_performance_score,
                vol_score=score_result.volume_score,
                event_score=score_result.event_score,
                evidence=score_result.evidence,
            )
            evidence_completeness = EvidenceCompleteness(**completeness_data)

            # Freshness note
            freshness_str = format_freshness_note(
                source=curr_obs.source if curr_obs else "NSE",
                current_observed_at=curr_obs.observed_at if curr_obs else None,
            )

            # Underlying changes summary & episode review status
            is_reviewed = len(changes_list) > 0 and all(ch.review_status == "reviewed" for ch in changes_list)
            episode_review_status = "reviewed" if is_reviewed else "surfaced"
            latest_reviewed_at = max((ch.reviewed_at for ch in changes_list if ch.reviewed_at is not None), default=None)

            underlying_changes = [
                UnderlyingChangeSummary(
                    id=ch.id,
                    change_type=ch.change_type,
                    magnitude=ch.magnitude,
                    evidence=ch.evidence,
                    detected_at=ch.detected_at,
                    review_status=ch.review_status or "surfaced",
                    reviewed_at=ch.reviewed_at,
                )
                for ch in changes_list
            ]

            p_base_dec = base_obs.price if base_obs else None
            p_curr_dec = curr_obs.price if curr_obs else None
            abs_change_dec = (p_curr_dec - p_base_dec) if (p_base_dec is not None and p_curr_dec is not None) else None
            pct_change_dec = Decimal(str(round(pct_change, 4))) if pct_change is not None else None

            item = AttentionItem(
                instrument=InstrumentReference(
                    id=inst.id if inst else instrument_id,
                    symbol=inst.nse_symbol if inst else "",
                    company_name=inst.company_name if inst else "",
                ),
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
                current_price=p_curr_dec,
                absolute_change=abs_change_dec,
                percentage_change=pct_change_dec,
                baseline_observation_id=base_obs.id if base_obs else first_ch.baseline_observation_id,
                baseline_price=p_base_dec,
                baseline_timestamp=base_obs.observed_at if base_obs else None,
                baseline_observed_at=base_obs.observed_at if base_obs else None,
                current_observation_id=curr_obs.id if curr_obs else first_ch.current_observation_id,
                current_timestamp=curr_obs.observed_at if curr_obs else None,
                current_observed_at=curr_obs.observed_at if curr_obs else None,

                changes=underlying_changes,
                constituent_change_types=constituent_change_types,
                evidence=score_result.evidence,
                explanation=score_result.explanation,
                structured_explanation=StructuredExplanation(**structured_exp),
                evidence_completeness=evidence_completeness,
                freshness_note=freshness_str,
                source=curr_obs.source if curr_obs else "NSE",
                data_status=curr_obs.data_status if curr_obs else "final",
                review_status=episode_review_status,
                is_reviewed=is_reviewed,
                reviewed_at=latest_reviewed_at,
            )
            all_items.append(item)

        except Exception as ex:
            logger.exception("Failed to score instrument %s in attention feed: %s", instrument_id, ex)
            # Isolate failure: do not crash whole watchlist
            insufficient_data_instruments.append(
                InsufficientDataItem(
                    instrument_id=inst.id if inst else instrument_id,
                    symbol=inst.nse_symbol if inst else "",
                    company_name=inst.company_name if inst else "",
                    reason=f"Scoring error: {str(ex)}",
                )
            )

    await db.commit()

    # Build chronological feed items from all DetectedChange records in the watchlist
    def _format_metrics_summary(ch: DetectedChange) -> str:
        ct = ch.change_type
        ev = ch.evidence or {}
        if ct == ChangeType.PRICE_MOVE.value:
            pct = ev.get("percentage_change")
            p_base = ev.get("baseline_price")
            p_curr = ev.get("current_price")
            if pct is not None and p_base is not None and p_curr is not None:
                sign = "+" if pct > 0 else ""
                return f"{sign}{pct:.2f}% (₹{p_base:.2f} → ₹{p_curr:.2f})"
            elif pct is not None:
                sign = "+" if pct > 0 else ""
                return f"{sign}{pct:.2f}% price movement"
        elif ct == ChangeType.ABNORMAL_RETURN.value:
            z = ev.get("z_score")
            if z is not None:
                sign = "+" if z > 0 else ""
                return f"Statistical anomaly (z-score: {sign}{z:.2f})"
        elif ct == ChangeType.VOLUME_ANOMALY.value:
            ratio = ev.get("volume_ratio")
            if ratio is not None:
                return f"Trading volume {ratio:.1f}× recent median"
        elif ct == ChangeType.RELATIVE_PERFORMANCE.value:
            diff = ev.get("excess_return")
            bm = ev.get("benchmark_symbol", "NIFTY 50")
            if diff is not None:
                sign = "+" if diff > 0 else ""
                dir_word = "outperformed" if diff > 0 else "underperformed"
                return f"{sign}{diff*100:.2f}% vs {bm} ({dir_word})"
        elif ct == ChangeType.MATERIAL_EVENT.value:
            title = ev.get("title") or ev.get("headline") or "Material corporate event"
            return title
        return ch.change_type.replace("_", " ").title()

    item_by_inst_id = {item.instrument_id: item for item in all_items}
    feed_items: list[ChangeFeedItem] = []
    for ch in changes_result.changes:
        inst = ch.instrument
        parent_item = item_by_inst_id.get(ch.instrument_id)
        base_obs = ch.baseline_observation
        curr_obs = ch.current_observation
        p_base_dec = base_obs.price if base_obs else None
        p_curr_dec = curr_obs.price if curr_obs else None
        abs_change_dec = (p_curr_dec - p_base_dec) if (p_base_dec is not None and p_curr_dec is not None) else None
        pct_val = ch.evidence.get("percentage_change") if ch.evidence else None
        if pct_val is None and p_base_dec and p_curr_dec and p_base_dec > Decimal("0"):
            pct_val = float((p_curr_dec - p_base_dec) / p_base_dec) * 100.0
        pct_change_dec = Decimal(str(round(pct_val, 4))) if pct_val is not None else None

        feed_items.append(
            ChangeFeedItem(
                id=ch.id,
                instrument_id=ch.instrument_id,
                symbol=inst.nse_symbol if inst else "",
                company_name=inst.company_name if inst else "",
                change_type=ch.change_type,
                significance_level=parent_item.significance_level if parent_item else "NONE",
                overall_score=parent_item.overall_score if parent_item else Decimal("0.0"),
                timestamp=ch.detected_at,
                baseline_observed_at=base_obs.observed_at if base_obs else None,
                current_observed_at=curr_obs.observed_at if curr_obs else None,
                baseline_price=p_base_dec,
                current_price=p_curr_dec,
                percentage_change=pct_change_dec,
                absolute_change=abs_change_dec,
                metrics_summary=_format_metrics_summary(ch),
                explanation=parent_item.explanation if parent_item else "",
                evidence_bullets=parent_item.structured_explanation.supporting_evidence if parent_item else [],
                source=curr_obs.source if curr_obs else "NSE",
                data_status=curr_obs.data_status if curr_obs else "HISTORICAL",
                review_status=ch.review_status or "surfaced",
                is_reviewed=(ch.review_status == "reviewed"),
                reviewed_at=ch.reviewed_at,
            )
        )

    feed_items.sort(key=lambda it: (it.timestamp, it.id), reverse=True)

    # Filter: primary feed surfaces HIGH, MEDIUM, LOW
    # Items with NONE level are excluded from primary feed
    meaningful_items: list[AttentionItem] = []
    for item in all_items:
        if item.significance_level in ("HIGH", "MEDIUM", "LOW"):
            meaningful_items.append(item)
        else:
            quiet_instruments.append(
                QuietInstrumentItem(
                    instrument_id=item.instrument_id,
                    symbol=item.symbol,
                    company_name=item.company_name,
                    reason=f"Price movement remained within normal historical variance (Score: {item.overall_score} < 0.20).",
                )
            )

    # Add evaluated instruments that had no qualifying changes to quiet_instruments
    for s in changes_result.instrument_statuses:
        if s.status in ("up_to_date", "no_qualifying_changes"):
            quiet_instruments.append(
                QuietInstrumentItem(
                    instrument_id=s.instrument_id,
                    symbol=s.symbol,
                    company_name=s.company_name,
                    reason=s.diagnostics.get("message", "No meaningful changes detected since last check."),
                )
            )

    # Deterministic multi-criteria ranking:
    # 1. overall_score DESCENDING
    # 2. significance level strength: HIGH (3) > MEDIUM (2) > LOW (1)
    # 3. evidence completeness: STRONG (3) > MODERATE (2) > LIMITED (1)
    # 4. symbol ASCENDING
    def ranking_key(it: AttentionItem):
        level_weight = LEVEL_ORDER.get(it.significance_level, 0)
        comp_level = it.evidence_completeness.level if it.evidence_completeness else "LIMITED"
        completeness_weight = 3 if comp_level == "STRONG" else (2 if comp_level == "MODERATE" else 1)
        return (-it.overall_score, -level_weight, -completeness_weight, it.symbol)

    ranked_attention_items = sorted(meaningful_items, key=ranking_key)

    total_inst = len(changes_result.instrument_statuses)
    insufficient_count = len(insufficient_data_instruments)
    evaluated_count = max(0, total_inst - insufficient_count)
    attn_count = len(ranked_attention_items)
    no_meaningful_count = max(0, evaluated_count - attn_count)

    high_count = sum(1 for it in ranked_attention_items if it.significance_level == "HIGH")
    medium_count = sum(1 for it in ranked_attention_items if it.significance_level == "MEDIUM")
    low_count = sum(1 for it in ranked_attention_items if it.significance_level == "LOW")

    unreviewed_count = sum(1 for it in ranked_attention_items if not it.is_reviewed)
    reviewed_count = sum(1 for it in ranked_attention_items if it.is_reviewed)

    summary = AttentionSummary(
        total_instruments=total_inst,
        instruments_evaluated=evaluated_count,
        attention_count=attn_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        no_meaningful_change_count=no_meaningful_count,
        insufficient_data_count=insufficient_count,
        unreviewed_count=unreviewed_count,
        reviewed_count=reviewed_count,
        # Backward compatibility
        instruments_with_changes=len(changes_by_instrument),
        instruments_with_meaningful_changes=attn_count,
        instruments_without_meaningful_changes=no_meaningful_count,
    )

    return WatchlistAttentionResponse(
        watchlist_id=changes_result.watchlist_id,
        watchlist_name=changes_result.watchlist_name,
        last_checked_at=changes_result.last_checked_at,
        items=ranked_attention_items,
        attention_items=ranked_attention_items,
        feed_items=feed_items,
        summary=summary,
        quiet_instruments=quiet_instruments,
        insufficient_data_instruments=insufficient_data_instruments,
    )


