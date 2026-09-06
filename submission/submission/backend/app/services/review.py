import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.change_review import ChangeReview
from app.models.detected_change import DetectedChange, ReviewStatus
from app.models.watchlist import Watchlist, WatchlistItem

logger = logging.getLogger(__name__)


async def review_detected_change(
    db: AsyncSession,
    user_id: int,
    watchlist_id: int,
    change_id: int,
) -> tuple[DetectedChange, ChangeReview]:
    """
    Marks a single DetectedChange as reviewed for the specified user and watchlist.
    Validates ownership and persists both DetectedChange.review_status and a ChangeReview audit record.
    """
    # 1. Validate watchlist ownership
    wl_stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.items))
        .where(Watchlist.id == watchlist_id)
    )
    wl_res = await db.execute(wl_stmt)
    watchlist = wl_res.scalar_one_or_none()
    if watchlist is None:
        raise ValueError("Watchlist not found")
    if watchlist.user_id != user_id:
        raise PermissionError("Access denied")

    watchlist_inst_ids = {item.instrument_id for item in watchlist.items}

    # 2. Fetch DetectedChange
    ch_stmt = (
        select(DetectedChange)
        .options(
            selectinload(DetectedChange.instrument),
            selectinload(DetectedChange.baseline_observation),
            selectinload(DetectedChange.current_observation),
        )
        .where(
            DetectedChange.id == change_id,
            DetectedChange.user_id == user_id,
        )
    )
    ch_res = await db.execute(ch_stmt)
    change = ch_res.scalar_one_or_none()
    if change is None:
        raise ValueError("Detected change not found")

    if change.instrument_id not in watchlist_inst_ids:
        raise ValueError("Change does not belong to an instrument in this watchlist")

    now = datetime.now(timezone.utc)
    change.review_status = ReviewStatus.REVIEWED.value
    change.reviewed_at = now

    review_record = ChangeReview(
        user_id=user_id,
        detected_change_id=change.id,
        action="reviewed",
        reviewed_at=now,
    )
    db.add(review_record)
    await db.commit()
    await db.refresh(change)
    await db.refresh(review_record)

    logger.info("User %d marked change %d as reviewed", user_id, change_id)
    return change, review_record


async def review_instrument_changes(
    db: AsyncSession,
    user_id: int,
    watchlist_id: int,
    instrument_id: int,
) -> int:
    """
    Marks all active DetectedChange records for an instrument in the watchlist as reviewed.
    Returns the count of reviewed changes.
    """
    # 1. Validate watchlist ownership
    wl_stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.items))
        .where(Watchlist.id == watchlist_id)
    )
    wl_res = await db.execute(wl_stmt)
    watchlist = wl_res.scalar_one_or_none()
    if watchlist is None:
        raise ValueError("Watchlist not found")
    if watchlist.user_id != user_id:
        raise PermissionError("Access denied")

    watchlist_inst_ids = {item.instrument_id for item in watchlist.items}
    if instrument_id not in watchlist_inst_ids:
        raise ValueError("Instrument not in this watchlist")

    # 2. Fetch active changes for this instrument
    ch_stmt = select(DetectedChange).where(
        DetectedChange.user_id == user_id,
        DetectedChange.instrument_id == instrument_id,
    )
    ch_res = await db.execute(ch_stmt)
    changes = list(ch_res.scalars().all())

    now = datetime.now(timezone.utc)
    reviewed_count = 0
    for ch in changes:
        ch.review_status = ReviewStatus.REVIEWED.value
        ch.reviewed_at = now
        db.add(
            ChangeReview(
                user_id=user_id,
                detected_change_id=ch.id,
                action="reviewed",
                reviewed_at=now,
            )
        )
        reviewed_count += 1

    await db.commit()
    logger.info("User %d marked %d changes for instrument %d as reviewed", user_id, reviewed_count, instrument_id)
    return reviewed_count


async def review_all_watchlist_changes(
    db: AsyncSession,
    user_id: int,
    watchlist_id: int,
) -> int:
    """
    Marks all active DetectedChange records across all instruments in the watchlist as reviewed.
    Returns the count of reviewed changes.
    """
    wl_stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.items))
        .where(Watchlist.id == watchlist_id)
    )
    wl_res = await db.execute(wl_stmt)
    watchlist = wl_res.scalar_one_or_none()
    if watchlist is None:
        raise ValueError("Watchlist not found")
    if watchlist.user_id != user_id:
        raise PermissionError("Access denied")

    inst_ids = [item.instrument_id for item in watchlist.items]
    if not inst_ids:
        return 0

    ch_stmt = select(DetectedChange).where(
        DetectedChange.user_id == user_id,
        DetectedChange.instrument_id.in_(inst_ids),
    )
    ch_res = await db.execute(ch_stmt)
    changes = list(ch_res.scalars().all())

    now = datetime.now(timezone.utc)
    reviewed_count = 0
    for ch in changes:
        ch.review_status = ReviewStatus.REVIEWED.value
        ch.reviewed_at = now
        db.add(
            ChangeReview(
                user_id=user_id,
                detected_change_id=ch.id,
                action="reviewed",
                reviewed_at=now,
            )
        )
        reviewed_count += 1

    await db.commit()
    logger.info("User %d marked %d changes across watchlist %d as reviewed", user_id, reviewed_count, watchlist_id)
    return reviewed_count
