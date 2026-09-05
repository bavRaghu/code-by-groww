import logging
from collections import defaultdict
from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.detected_change import ChangeType, DetectedChange
from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.significance_assessment import SignificanceAssessment, SignificanceLevel
from app.models.user_observation import UserObservation
from app.models.watchlist import Watchlist
from app.schemas.attention import ComponentScores, EvidenceCompleteness, StructuredExplanation
from app.schemas.stock_detail import (
    CurrentObservationDetail,
    EvidenceDetail,
    HistoricalSeriesPoint,
    MarketContextDetail,
    SinceLastCheckedDetail,
    StockDetailResponse,
    TimelineEpisode,
)
from app.services.significance_scoring import (
    compute_evidence_completeness,
    format_freshness_note,
    generate_structured_explanation,
)
from app.services.news import get_or_fetch_relevant_news

logger = logging.getLogger(__name__)


async def get_stock_detail(
    db: AsyncSession,
    user_id: int,
    instrument_id: int,
    watchlist_id: int | None = None,
) -> StockDetailResponse:
    """
    Assembles a comprehensive, explainable stock detail view:
    - Current/latest price, session change, and data freshness provenance.
    - 'Since you last checked' baseline comparison, net change, significance level and score.
    - Deterministic, non-causal evidence breakdown ('Why this was flagged') with missing data notes.
    - Benchmark context and relative performance comparison.
    - Chronological timeline grouping related signals from each observation window into coherent episodes.
    - Bounded historical series for lightweight chart visualization with baseline & current markers.
    """
    # 1. Fetch instrument
    inst_stmt = select(Instrument).where(Instrument.id == instrument_id)
    inst_res = await db.execute(inst_stmt)
    instrument = inst_res.scalar_one_or_none()
    if instrument is None:
        raise ValueError("Instrument not found")

    # 2. Fetch bounded historical observations (last 30 observations sorted chronologically)
    obs_stmt = (
        select(MarketObservation)
        .where(MarketObservation.instrument_id == instrument_id)
        .order_by(MarketObservation.observed_at.asc())
        .limit(30)
    )
    obs_res = await db.execute(obs_stmt)
    observations = list(obs_res.scalars().all())

    latest_obs = observations[-1] if observations else None
    prev_session_obs = observations[-2] if len(observations) >= 2 else None

    # Calculate 1-session daily movement
    session_abs = None
    session_pct = None
    if latest_obs and prev_session_obs and prev_session_obs.price > Decimal("0"):
        session_abs = latest_obs.price - prev_session_obs.price
        pct_val = float((latest_obs.price - prev_session_obs.price) / prev_session_obs.price) * 100.0
        session_pct = Decimal(str(round(pct_val, 4)))

    current_obs_detail = CurrentObservationDetail(
        price=latest_obs.price if latest_obs else None,
        observed_at=latest_obs.observed_at if latest_obs else None,
        volume=latest_obs.volume if latest_obs else None,
        source=latest_obs.source if latest_obs else "NSE",
        data_status=latest_obs.data_status if latest_obs else "final",
        session_absolute_change=session_abs,
        session_percentage_change=session_pct,
    )

    # 3. Fetch UserObservation baseline for this user and instrument
    uo_stmt = select(UserObservation).where(
        UserObservation.user_id == user_id,
        UserObservation.instrument_id == instrument_id,
    )
    uo_res = await db.execute(uo_stmt)
    user_obs = uo_res.scalar_one_or_none()
    baseline_obs_id = user_obs.last_seen_observation_id if user_obs else None

    baseline_obs: MarketObservation | None = None
    if baseline_obs_id is not None:
        baseline_obs = next((o for o in observations if o.id == baseline_obs_id), None)
        if baseline_obs is None:
            b_stmt = select(MarketObservation).where(MarketObservation.id == baseline_obs_id)
            baseline_obs = (await db.execute(b_stmt)).scalar_one_or_none()

    # 4. Fetch DetectedChange records for this user and instrument
    dc_stmt = (
        select(DetectedChange)
        .options(
            selectinload(DetectedChange.baseline_observation),
            selectinload(DetectedChange.current_observation),
        )
        .where(
            DetectedChange.user_id == user_id,
            DetectedChange.instrument_id == instrument_id,
        )
        .order_by(DetectedChange.observation_end.desc(), DetectedChange.id.desc())
    )
    dc_res = await db.execute(dc_stmt)
    all_changes = list(dc_res.scalars().all())

    # Map assessments by detected_change_id
    change_ids = [ch.id for ch in all_changes]
    assessments_by_change_id: dict[int, SignificanceAssessment] = {}
    if change_ids:
        sa_stmt = select(SignificanceAssessment).where(SignificanceAssessment.detected_change_id.in_(change_ids))
        sa_res = await db.execute(sa_stmt)
        for sa in sa_res.scalars().all():
            assessments_by_change_id[sa.detected_change_id] = sa

    # Group detected changes into episodes by (baseline_observation_id, current_observation_id)
    episodes_dict: dict[tuple[int | None, int], list[DetectedChange]] = defaultdict(list)
    for ch in all_changes:
        episodes_dict[(ch.baseline_observation_id, ch.current_observation_id)].append(ch)

    # 5. Build "Since you last checked" section and active Evidence
    since_last_checked = SinceLastCheckedDetail()
    evidence_detail: EvidenceDetail | None = None
    market_context = MarketContextDetail()

    if not observations:
        since_last_checked.tracking_note = "No market observations recorded yet for this instrument."
    elif baseline_obs is None:
        since_last_checked.has_baseline = False
        since_last_checked.current_price = latest_obs.price if latest_obs else None
        since_last_checked.current_observed_at = latest_obs.observed_at if latest_obs else None
        since_last_checked.tracking_note = "No observation baseline established yet. Click 'Mark as Checked' on your watchlist to record an initial baseline."
    else:
        # User has a baseline
        since_last_checked.has_baseline = True
        since_last_checked.baseline_observation_id = baseline_obs.id
        since_last_checked.baseline_price = baseline_obs.price
        since_last_checked.baseline_observed_at = baseline_obs.observed_at
        since_last_checked.current_observation_id = latest_obs.id if latest_obs else None
        since_last_checked.current_price = latest_obs.price if latest_obs else None
        since_last_checked.current_observed_at = latest_obs.observed_at if latest_obs else None

        p_base = baseline_obs.price
        p_curr = latest_obs.price if latest_obs else p_base
        abs_net = p_curr - p_base
        pct_net = Decimal(str(round(float(abs_net / p_base) * 100.0, 4))) if p_base > Decimal("0") else Decimal("0.0")

        since_last_checked.absolute_change = abs_net
        since_last_checked.percentage_change = pct_net

        if baseline_obs.id == (latest_obs.id if latest_obs else None):
            since_last_checked.significance_level = "NO_CHANGE"
            since_last_checked.overall_score = Decimal("0.0")
            since_last_checked.is_reviewed = True
            since_last_checked.review_status = "reviewed"
            since_last_checked.tracking_note = "You are up to date with the latest market observation. No new changes since your last check."
        else:
            # Active observation window from baseline to latest
            active_changes = episodes_dict.get((baseline_obs.id, latest_obs.id if latest_obs else -1), [])
            if active_changes:
                is_rev = all(ch.review_status == "reviewed" for ch in active_changes)
                rev_at = max((ch.reviewed_at for ch in active_changes if ch.reviewed_at), default=None)
                since_last_checked.is_reviewed = is_rev
                since_last_checked.review_status = "reviewed" if is_rev else "surfaced"
                since_last_checked.reviewed_at = rev_at

                # Pick the primary assessment
                best_sa = max(
                    (assessments_by_change_id.get(ch.id) for ch in active_changes if ch.id in assessments_by_change_id),
                    key=lambda a: a.overall_score if a else Decimal("-1"),
                    default=None,
                )

                if best_sa:
                    since_last_checked.significance_level = best_sa.significance_level
                    since_last_checked.overall_score = best_sa.overall_score
                    level_enum = SignificanceLevel(best_sa.significance_level)

                    # Build structured explanation
                    structured_exp = generate_structured_explanation(
                        symbol=instrument.nse_symbol,
                        level=level_enum,
                        mag_score=best_sa.magnitude_score,
                        abn_score=best_sa.abnormality_score,
                        rel_score=best_sa.relative_performance_score,
                        vol_score=best_sa.volume_score,
                        event_score=best_sa.event_score,
                        evidence=best_sa.evidence or {},
                    )

                    # Build completeness
                    completeness_dict = compute_evidence_completeness(
                        level=level_enum,
                        mag_score=best_sa.magnitude_score,
                        abn_score=best_sa.abnormality_score,
                        rel_score=best_sa.relative_performance_score,
                        vol_score=best_sa.volume_score,
                        event_score=best_sa.event_score,
                        evidence=best_sa.evidence or {},
                    )
                    evidence_comp = EvidenceCompleteness(**completeness_dict)

                    component_scores = ComponentScores(
                        magnitude=best_sa.magnitude_score,
                        abnormality=best_sa.abnormality_score,
                        relative_performance=best_sa.relative_performance_score,
                        volume=best_sa.volume_score,
                        event=best_sa.event_score,
                    )

                    evidence_detail = EvidenceDetail(
                        significance_level=best_sa.significance_level,
                        overall_score=best_sa.overall_score,
                        why_it_matters=structured_exp.get("why_it_stands_out", ""),
                        evidence_bullets=structured_exp.get("supporting_evidence", []),
                        missing_data_notes=structured_exp.get("missing_data_notes", []),
                        evidence_completeness=evidence_comp,
                        component_scores=component_scores,
                        structured_explanation=StructuredExplanation(**structured_exp),
                    )

                    # Extract market context
                    rel_ev = (best_sa.evidence or {}).get("relative_performance", {})
                    stock_ret = rel_ev.get("stock_return")
                    bm_ret = rel_ev.get("benchmark_return")
                    excess_ret = rel_ev.get("excess_return")
                    bm_sym = rel_ev.get("benchmark_symbol", "NIFTY 50")

                    if stock_ret is not None and bm_ret is not None and excess_ret is not None:
                        dir_word = "outperformed" if excess_ret >= 0 else "underperformed"
                        s_action = "gained" if stock_ret >= 0 else "declined"
                        b_action = "gained" if bm_ret >= 0 else "declined"
                        context_sum = (
                            f"The stock {s_action} {abs(stock_ret * 100):.2f}% while {bm_sym} {b_action} {abs(bm_ret * 100):.2f}%, "
                            f"indicating the stock {dir_word} its benchmark by {abs(excess_ret * 100):.2f} percentage points "
                            f"over the same observation window."
                        )
                        market_context = MarketContextDetail(
                            benchmark_symbol=bm_sym,
                            stock_return=stock_ret,
                            benchmark_return=bm_ret,
                            excess_return=excess_ret,
                            status="available",
                            context_summary=context_sum,
                        )
                    else:
                        market_context = MarketContextDetail(
                            benchmark_symbol=bm_sym,
                            status="unavailable",
                            context_summary="Relative performance could not be assessed because benchmark data was unavailable for this period.",
                        )
            else:
                # Baseline exists and is older than latest, but price move was quiet / no candidate changes qualified
                since_last_checked.significance_level = "NONE"
                since_last_checked.overall_score = Decimal("0.0")
                since_last_checked.is_reviewed = True
                since_last_checked.review_status = "reviewed"
                since_last_checked.tracking_note = "Price movement remained within normal historical variance (< 0.20 score). No qualifying changes detected."

    # 6. Build chronological timeline episodes
    timeline_episodes: list[TimelineEpisode] = []
    for (base_id, curr_id), changes_list in episodes_dict.items():
        first_ch = changes_list[0]
        base_o = first_ch.baseline_observation
        curr_o = first_ch.current_observation

        p_b = base_o.price if base_o else None
        p_c = curr_o.price if curr_o else None
        abs_c = (p_c - p_b) if (p_c is not None and p_b is not None) else None
        pct_c = None
        if p_b is not None and p_c is not None and p_b > Decimal("0"):
            pct_c = Decimal(str(round(float((p_c - p_b) / p_b) * 100.0, 4)))

        # Find best assessment
        ep_sa = max(
            (assessments_by_change_id.get(ch.id) for ch in changes_list if ch.id in assessments_by_change_id),
            key=lambda a: a.overall_score if a else Decimal("-1"),
            default=None,
        )

        constituent_types = sorted(list({ch.change_type for ch in changes_list}))
        is_ep_rev = all(ch.review_status == "reviewed" for ch in changes_list)
        ep_rev_at = max((ch.reviewed_at for ch in changes_list if ch.reviewed_at), default=None)

        # Bullets
        bullets: list[str] = []
        if ep_sa:
            st = generate_structured_explanation(
                symbol=instrument.nse_symbol,
                level=SignificanceLevel(ep_sa.significance_level),
                mag_score=ep_sa.magnitude_score,
                abn_score=ep_sa.abnormality_score,
                rel_score=ep_sa.relative_performance_score,
                vol_score=ep_sa.volume_score,
                event_score=ep_sa.event_score,
                evidence=ep_sa.evidence or {},
            )
            bullets = st.get("supporting_evidence", [])
        else:
            bullets = [f"{ct.replace('_', ' ').title()} candidate change recorded." for ct in constituent_types]

        timeline_episodes.append(
            TimelineEpisode(
                id=first_ch.id,
                baseline_observation_id=base_id,
                current_observation_id=curr_id,
                observation_start=first_ch.observation_start,
                observation_end=first_ch.observation_end or (curr_o.observed_at if curr_o else first_ch.detected_at),
                baseline_price=p_b,
                current_price=p_c,
                absolute_change=abs_c,
                percentage_change=pct_c,
                volume=curr_o.volume if curr_o else None,
                significance_level=ep_sa.significance_level if ep_sa else "NONE",
                overall_score=ep_sa.overall_score if ep_sa else Decimal("0.0"),
                constituent_change_types=constituent_types,
                evidence_bullets=bullets,
                review_status="reviewed" if is_ep_rev else "surfaced",
                is_reviewed=is_ep_rev,
                reviewed_at=ep_rev_at,
            )
        )

    # Sort timeline episodes in descending chronological order (most recent first)
    timeline_episodes.sort(key=lambda ep: (ep.observation_end, ep.id), reverse=True)

    # 7. Bounded historical series for the chart
    historical_series: list[HistoricalSeriesPoint] = []
    for o in observations:
        historical_series.append(
            HistoricalSeriesPoint(
                observation_id=o.id,
                observed_at=o.observed_at,
                price=o.price,
                volume=o.volume,
                is_baseline=(baseline_obs is not None and o.id == baseline_obs.id),
                is_current=(latest_obs is not None and o.id == latest_obs.id),
            )
        )

    # 8. Data freshness note
    freshness_str = format_freshness_note(
        source=latest_obs.source if latest_obs else "NSE",
        current_observed_at=latest_obs.observed_at if latest_obs else None,
    )

    # 9. Supporting news context
    news_context = None
    if latest_obs:
        try:
            news_context = await get_or_fetch_relevant_news(
                db=db,
                instrument=instrument,
                change_time=latest_obs.observed_at,
                baseline_time=since_last_checked.baseline_observed_at if since_last_checked.has_baseline else None,
            )
        except Exception as n_err:
            logger.warning("Failed to retrieve supporting news for %s: %s", instrument.nse_symbol, n_err)

    return StockDetailResponse(
        id=instrument.id,
        nse_symbol=instrument.nse_symbol,
        company_name=instrument.company_name,
        exchange=instrument.exchange,
        isin=instrument.isin,
        sector=instrument.sector,
        current_observation=current_obs_detail,
        since_last_checked=since_last_checked,
        evidence=evidence_detail,
        market_context=market_context,
        timeline=timeline_episodes,
        historical_series=historical_series,
        freshness_note=freshness_str,
        source=latest_obs.source if latest_obs else "NSE",
        data_status=latest_obs.data_status if latest_obs else "HISTORICAL",
        relevant_news=news_context,
    )
