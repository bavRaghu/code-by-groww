import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.detected_change import ChangeType, DetectedChange, ReviewStatus
from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation
from app.models.user_observation import UserObservation
from app.models.watchlist import Watchlist, WatchlistItem
from app.providers.benchmark import BenchmarkProvider, NSEBenchmarkProvider
from app.providers.events import MaterialEventProvider, NullMaterialEventProvider

# Sensible statistical minimums avoiding look-ahead bias
MIN_HISTORY_SAMPLE_SIZE = 3
MIN_VOLUME_SAMPLE_SIZE = 3
DEFAULT_WINDOW_SIZE = 30
VOLUME_ANOMALY_UPPER_THRESHOLD = 1.25
VOLUME_ANOMALY_LOWER_THRESHOLD = 0.75


@dataclass
class InstrumentChangeStatus:
    instrument_id: int
    symbol: str
    company_name: str
    baseline_observation_id: int | None
    baseline_observed_at: datetime | None
    current_observation_id: int | None
    current_observed_at: datetime | None
    status: str  # "changes_detected", "up_to_date", "no_baseline", "insufficient_data"
    diagnostics: dict[str, Any]


@dataclass
class ChangeCandidate:
    instrument_id: int
    change_type: str
    observation_start: datetime
    observation_end: datetime
    baseline_observation_id: int
    current_observation_id: int
    magnitude: Decimal | None
    evidence: dict[str, Any]


@dataclass
class WatchlistChangesResult:
    watchlist_id: int
    watchlist_name: str
    last_checked_at: datetime | None
    changes: list[DetectedChange]
    instrument_statuses: list[InstrumentChangeStatus]


async def detect_changes_for_watchlist(
    db: AsyncSession,
    user_id: int,
    watchlist_id: int,
    benchmark_provider: BenchmarkProvider | None = None,
    event_provider: MaterialEventProvider | None = None,
    min_history_sample_size: int = MIN_HISTORY_SAMPLE_SIZE,
    min_volume_sample_size: int = MIN_VOLUME_SAMPLE_SIZE,
) -> WatchlistChangesResult:
    if benchmark_provider is None:
        benchmark_provider = NSEBenchmarkProvider()
    if event_provider is None:
        event_provider = NullMaterialEventProvider()

    # 1. Fetch watchlist with items and instruments
    wl_stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.items).selectinload(WatchlistItem.instrument))
        .where(Watchlist.id == watchlist_id)
    )
    wl_res = await db.execute(wl_stmt)
    watchlist = wl_res.scalar_one_or_none()
    if watchlist is None:
        raise ValueError("Watchlist not found")
    if watchlist.user_id != user_id:
        raise PermissionError("Access denied")

    sorted_items = sorted(watchlist.items, key=lambda x: x.position)

    instrument_statuses: list[InstrumentChangeStatus] = []
    candidates_to_persist: list[ChangeCandidate] = []
    valid_baseline_obs_ids: dict[int, int] = {}  # instrument_id -> baseline_observation_id

    now = datetime.now(timezone.utc)

    inst_ids = [item.instrument_id for item in sorted_items if item.instrument is not None]
    uobs_map: dict[int, UserObservation] = {}
    if inst_ids:
        uobs_stmt = select(UserObservation).where(
            UserObservation.user_id == user_id,
            UserObservation.instrument_id.in_(inst_ids),
        )
        uobs_res = await db.execute(uobs_stmt)
        uobs_map = {uo.instrument_id: uo for uo in uobs_res.scalars().all()}

    for item in sorted_items:
        inst = item.instrument
        if inst is None:
            continue

        # Fetch user's observation baseline for this instrument from pre-fetched map
        user_obs = uobs_map.get(inst.id)

        if user_obs is None or user_obs.last_seen_observation_id is None:
            instrument_statuses.append(
                InstrumentChangeStatus(
                    instrument_id=inst.id,
                    symbol=inst.nse_symbol,
                    company_name=inst.company_name,
                    baseline_observation_id=None,
                    baseline_observed_at=None,
                    current_observation_id=None,
                    current_observed_at=None,
                    status="no_baseline",
                    diagnostics={"message": "No observation baseline established. Check watchlist to start tracking."},
                )
            )
            continue

        # Fetch baseline observation
        base_stmt = select(MarketObservation).where(MarketObservation.id == user_obs.last_seen_observation_id)
        base_res = await db.execute(base_stmt)
        baseline_obs = base_res.scalar_one_or_none()

        # Fetch latest observation
        curr_stmt = (
            select(MarketObservation)
            .where(MarketObservation.instrument_id == inst.id)
            .order_by(MarketObservation.observed_at.desc(), MarketObservation.id.desc())
            .limit(1)
        )
        curr_res = await db.execute(curr_stmt)
        current_obs = curr_res.scalar_one_or_none()

        if baseline_obs is None or current_obs is None:
            instrument_statuses.append(
                InstrumentChangeStatus(
                    instrument_id=inst.id,
                    symbol=inst.nse_symbol,
                    company_name=inst.company_name,
                    baseline_observation_id=user_obs.last_seen_observation_id,
                    baseline_observed_at=None,
                    current_observation_id=current_obs.id if current_obs else None,
                    current_observed_at=current_obs.observed_at if current_obs else None,
                    status="insufficient_data",
                    diagnostics={"message": "Market observation data missing for comparison."},
                )
            )
            continue

        valid_baseline_obs_ids[inst.id] = baseline_obs.id

        # If baseline is the same or current is not newer than baseline, it's up to date
        if current_obs.id == baseline_obs.id or current_obs.observed_at <= baseline_obs.observed_at:
            instrument_statuses.append(
                InstrumentChangeStatus(
                    instrument_id=inst.id,
                    symbol=inst.nse_symbol,
                    company_name=inst.company_name,
                    baseline_observation_id=baseline_obs.id,
                    baseline_observed_at=baseline_obs.observed_at,
                    current_observation_id=current_obs.id,
                    current_observed_at=current_obs.observed_at,
                    status="up_to_date",
                    diagnostics={"message": "No new market observations since last check."},
                )
            )
            continue

        # Newer observation exists! Run candidate change detections
        diagnostics: dict[str, Any] = {}
        instrument_candidates: list[ChangeCandidate] = []

        # -------------------------------------------------------------
        # 1. PRICE_MOVE detection
        # -------------------------------------------------------------
        p_base = baseline_obs.price
        p_curr = current_obs.price
        abs_change = p_curr - p_base
        pct_change: Decimal | None = None

        if p_base > Decimal("0"):
            pct_change = ((p_curr - p_base) / p_base) * Decimal("100")

        if abs_change != Decimal("0"):
            magnitude_val = round(pct_change, 4) if pct_change is not None else round(abs_change, 4)
            instrument_candidates.append(
                ChangeCandidate(
                    instrument_id=inst.id,
                    change_type=ChangeType.PRICE_MOVE.value,
                    observation_start=baseline_obs.observed_at,
                    observation_end=current_obs.observed_at,
                    baseline_observation_id=baseline_obs.id,
                    current_observation_id=current_obs.id,
                    magnitude=magnitude_val,
                    evidence={
                        "baseline_price": float(p_base),
                        "current_price": float(p_curr),
                        "absolute_change": float(round(abs_change, 4)),
                        "percentage_change": float(round(pct_change, 4)) if pct_change is not None else None,
                        "source": current_obs.source,
                        "data_status": current_obs.data_status,
                    },
                )
            )
        else:
            diagnostics["price_move"] = "no_price_change"

        # -------------------------------------------------------------
        # 2. ABNORMAL_RETURN detection (Strictly prior observations)
        # -------------------------------------------------------------
        hist_stmt = (
            select(MarketObservation)
            .where(
                MarketObservation.instrument_id == inst.id,
                MarketObservation.source == current_obs.source,
                MarketObservation.observed_at < current_obs.observed_at,
            )
            .order_by(MarketObservation.observed_at.asc())
            .limit(DEFAULT_WINDOW_SIZE)
        )
        hist_res = await db.execute(hist_stmt)
        hist_obs_list = hist_res.scalars().all()

        # Calculate returns from consecutive historical observations
        hist_returns: list[float] = []
        for i in range(1, len(hist_obs_list)):
            prev_p = hist_obs_list[i - 1].price
            curr_p = hist_obs_list[i].price
            if prev_p > Decimal("0"):
                hist_returns.append(float((curr_p - prev_p) / prev_p))

        if len(hist_returns) < min_history_sample_size:
            diagnostics["abnormal_return"] = {
                "status": "insufficient_history",
                "sample_size": len(hist_returns),
                "min_required": min_history_sample_size,
            }
        else:
            mean_ret = statistics.mean(hist_returns)
            std_ret = statistics.stdev(hist_returns) if len(hist_returns) > 1 else 0.0

            if p_base > Decimal("0") and std_ret > 0.0:
                observed_ret = float((p_curr - p_base) / p_base)
                z_score = (observed_ret - mean_ret) / std_ret

                instrument_candidates.append(
                    ChangeCandidate(
                        instrument_id=inst.id,
                        change_type=ChangeType.ABNORMAL_RETURN.value,
                        observation_start=baseline_obs.observed_at,
                        observation_end=current_obs.observed_at,
                        baseline_observation_id=baseline_obs.id,
                        current_observation_id=current_obs.id,
                        magnitude=Decimal(str(round(z_score, 4))),
                        evidence={
                            "observed_return": round(observed_ret, 6),
                            "historical_mean": round(mean_ret, 6),
                            "historical_stddev": round(std_ret, 6),
                            "z_score": round(z_score, 4),
                            "sample_size": len(hist_returns),
                            "window_size": len(hist_obs_list),
                        },
                    )
                )
            else:
                diagnostics["abnormal_return"] = {
                    "status": "zero_variance_or_invalid_price",
                    "historical_stddev": std_ret,
                }

        # -------------------------------------------------------------
        # 3. RELATIVE_PERFORMANCE detection
        # -------------------------------------------------------------
        bench_ret = await benchmark_provider.get_benchmark_return(
            db=db,
            start_time=baseline_obs.observed_at,
            end_time=current_obs.observed_at,
            benchmark_symbol="NIFTY 50",
        )

        if bench_ret is None:
            diagnostics["relative_performance"] = {
                "status": "benchmark_data_unavailable",
                "benchmark_symbol": "NIFTY 50",
            }
        elif p_base > Decimal("0"):
            stock_ret = (p_curr - p_base) / p_base
            excess_ret = stock_ret - bench_ret
            excess_pct = excess_ret * Decimal("100")

            instrument_candidates.append(
                ChangeCandidate(
                    instrument_id=inst.id,
                    change_type=ChangeType.RELATIVE_PERFORMANCE.value,
                    observation_start=baseline_obs.observed_at,
                    observation_end=current_obs.observed_at,
                    baseline_observation_id=baseline_obs.id,
                    current_observation_id=current_obs.id,
                    magnitude=round(excess_pct, 4),
                    evidence={
                        "stock_return": float(round(stock_ret, 6)),
                        "benchmark_return": float(round(bench_ret, 6)),
                        "excess_return": float(round(excess_ret, 6)),
                        "benchmark_symbol": "NIFTY 50",
                    },
                )
            )

        # -------------------------------------------------------------
        # 4. VOLUME_ANOMALY detection
        # -------------------------------------------------------------
        hist_volumes = [
            obs.volume for obs in hist_obs_list
            if obs.volume is not None and obs.volume > 0
        ]

        if len(hist_volumes) < min_volume_sample_size:
            diagnostics["volume_anomaly"] = {
                "status": "insufficient_volume_history",
                "sample_size": len(hist_volumes),
                "min_required": min_volume_sample_size,
            }
        elif current_obs.volume is not None:
            median_vol = statistics.median(hist_volumes)
            if median_vol > 0:
                vol_ratio = float(current_obs.volume) / float(median_vol)
                if vol_ratio >= VOLUME_ANOMALY_UPPER_THRESHOLD or vol_ratio <= VOLUME_ANOMALY_LOWER_THRESHOLD:
                    instrument_candidates.append(
                        ChangeCandidate(
                            instrument_id=inst.id,
                            change_type=ChangeType.VOLUME_ANOMALY.value,
                            observation_start=baseline_obs.observed_at,
                            observation_end=current_obs.observed_at,
                            baseline_observation_id=baseline_obs.id,
                            current_observation_id=current_obs.id,
                            magnitude=Decimal(str(round(vol_ratio, 4))),
                            evidence={
                                "current_volume": current_obs.volume,
                                "historical_median_volume": float(median_vol),
                                "volume_ratio": round(vol_ratio, 4),
                                "sample_size": len(hist_volumes),
                            },
                        )
                    )
                else:
                    diagnostics["volume_anomaly"] = {
                        "status": "normal_volume",
                        "volume_ratio": round(vol_ratio, 4),
                    }

        # -------------------------------------------------------------
        # 5. MATERIAL_EVENT boundary
        # -------------------------------------------------------------
        events = await event_provider.get_events_for_instrument(
            db=db,
            instrument_id=inst.id,
            start_time=baseline_obs.observed_at,
            end_time=current_obs.observed_at,
        )
        for ev in events:
            instrument_candidates.append(
                ChangeCandidate(
                    instrument_id=inst.id,
                    change_type=ChangeType.MATERIAL_EVENT.value,
                    observation_start=baseline_obs.observed_at,
                    observation_end=current_obs.observed_at,
                    baseline_observation_id=baseline_obs.id,
                    current_observation_id=current_obs.id,
                    magnitude=None,
                    evidence=ev,
                )
            )

        candidates_to_persist.extend(instrument_candidates)

        instrument_statuses.append(
            InstrumentChangeStatus(
                instrument_id=inst.id,
                symbol=inst.nse_symbol,
                company_name=inst.company_name,
                baseline_observation_id=baseline_obs.id,
                baseline_observed_at=baseline_obs.observed_at,
                current_observation_id=current_obs.id,
                current_observed_at=current_obs.observed_at,
                status="changes_detected" if instrument_candidates else "no_qualifying_changes",
                diagnostics=diagnostics,
            )
        )

    # Persist detected change candidates idempotently
    for cand in candidates_to_persist:
        exist_stmt = select(DetectedChange).where(
            DetectedChange.user_id == user_id,
            DetectedChange.instrument_id == cand.instrument_id,
            DetectedChange.baseline_observation_id == cand.baseline_observation_id,
            DetectedChange.current_observation_id == cand.current_observation_id,
            DetectedChange.change_type == cand.change_type,
        )
        exist_res = await db.execute(exist_stmt)
        existing_change = exist_res.scalar_one_or_none()

        if existing_change is None:
            new_change = DetectedChange(
                user_id=user_id,
                instrument_id=cand.instrument_id,
                change_type=cand.change_type,
                detected_at=now,
                observation_start=cand.observation_start,
                observation_end=cand.observation_end,
                baseline_observation_id=cand.baseline_observation_id,
                current_observation_id=cand.current_observation_id,
                magnitude=cand.magnitude,
                evidence=cand.evidence,
                review_status=ReviewStatus.SURFACED.value,
            )
            db.add(new_change)
        else:
            existing_change.detected_at = now
            existing_change.magnitude = cand.magnitude
            existing_change.evidence = cand.evidence
            existing_change.observation_start = cand.observation_start
            existing_change.observation_end = cand.observation_end

    await db.commit()

    # Retrieve all detected changes strictly matching current user baseline for watchlist instruments
    active_changes: list[DetectedChange] = []
    if valid_baseline_obs_ids:
        from sqlalchemy import or_
        conditions = [
            (DetectedChange.instrument_id == inst_id) & (DetectedChange.baseline_observation_id == base_id)
            for inst_id, base_id in valid_baseline_obs_ids.items()
        ]
        ch_stmt = (
            select(DetectedChange)
            .options(
                selectinload(DetectedChange.instrument),
                selectinload(DetectedChange.baseline_observation),
                selectinload(DetectedChange.current_observation),
            )
            .where(
                DetectedChange.user_id == user_id,
                or_(*conditions),
            )
            .order_by(DetectedChange.id.asc())
        )
        ch_res = await db.execute(ch_stmt)
        active_changes = list(ch_res.scalars().all())

    return WatchlistChangesResult(
        watchlist_id=watchlist.id,
        watchlist_name=watchlist.name,
        last_checked_at=watchlist.last_checked_at,
        changes=active_changes,
        instrument_statuses=instrument_statuses,
    )
