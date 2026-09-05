from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.instrument import Instrument
from app.models.user import User
from app.models.watchlist import Watchlist, WatchlistItem
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistDetailResponse,
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistReorderRequest,
    WatchlistSummaryResponse,
    WatchlistUpdate,
)
from app.schemas.change import (
    ChangesSummary,
    DetectedChangeItem,
    InstrumentStatusItem,
    WatchlistCheckResponse,
    WatchlistChangesResponse,
)
from app.schemas.attention import WatchlistAttentionResponse
from app.services.user_observation import mark_watchlist_checked
from app.services.change_detection import detect_changes_for_watchlist
from app.services.attention import get_watchlist_attention
from app.seed import DEV_USER_ID


router = APIRouter(prefix="/watchlists", tags=["watchlists"])


async def _get_dev_user(db: AsyncSession) -> User:
    stmt = select(User).where(User.id == DEV_USER_ID)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        user = User(id=DEV_USER_ID)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


@router.post("", response_model=WatchlistDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    payload: WatchlistCreate,
    db: AsyncSession = Depends(get_db),
) -> WatchlistDetailResponse:
    await _get_dev_user(db)
    watchlist = Watchlist(
        user_id=DEV_USER_ID,
        name=payload.name.strip(),
    )
    db.add(watchlist)
    await db.commit()
    await db.refresh(watchlist)

    return WatchlistDetailResponse(
        id=watchlist.id,
        user_id=watchlist.user_id,
        name=watchlist.name,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        items=[],
    )


@router.get("", response_model=list[WatchlistSummaryResponse])
async def list_watchlists(
    db: AsyncSession = Depends(get_db),
) -> list[WatchlistSummaryResponse]:
    await _get_dev_user(db)
    stmt = (
        select(Watchlist, func.count(WatchlistItem.id).label("item_count"))
        .outerjoin(WatchlistItem, Watchlist.id == WatchlistItem.watchlist_id)
        .where(Watchlist.user_id == DEV_USER_ID)
        .group_by(Watchlist.id)
        .order_by(Watchlist.id)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        WatchlistSummaryResponse(
            id=wl.id,
            user_id=wl.user_id,
            name=wl.name,
            created_at=wl.created_at,
            updated_at=wl.updated_at,
            item_count=count,
        )
        for wl, count in rows
    ]


@router.get("/{watchlist_id}", response_model=WatchlistDetailResponse)
async def get_watchlist(
    watchlist_id: int,
    db: AsyncSession = Depends(get_db),
) -> Watchlist:
    stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.items).selectinload(WatchlistItem.instrument))
        .where(Watchlist.id == watchlist_id)
    )
    result = await db.execute(stmt)
    watchlist = result.scalar_one_or_none()
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    if watchlist.user_id != DEV_USER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return watchlist


@router.patch("/{watchlist_id}", response_model=WatchlistDetailResponse)
async def update_watchlist(
    watchlist_id: int,
    payload: WatchlistUpdate,
    db: AsyncSession = Depends(get_db),
) -> Watchlist:
    stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.items).selectinload(WatchlistItem.instrument))
        .where(Watchlist.id == watchlist_id)
    )
    result = await db.execute(stmt)
    watchlist = result.scalar_one_or_none()
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    if watchlist.user_id != DEV_USER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    watchlist.name = payload.name.strip()
    watchlist.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(watchlist)
    return watchlist


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    watchlist_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    stmt = select(Watchlist).where(Watchlist.id == watchlist_id)
    result = await db.execute(stmt)
    watchlist = result.scalar_one_or_none()
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    if watchlist.user_id != DEV_USER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    await db.delete(watchlist)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----------------------------------------------------------------------
# Item membership & reordering
# ----------------------------------------------------------------------


@router.post("/{watchlist_id}/items", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
async def add_watchlist_item(
    watchlist_id: int,
    payload: WatchlistItemCreate,
    db: AsyncSession = Depends(get_db),
) -> WatchlistItem:
    # 1. Verify watchlist exists
    wl_stmt = select(Watchlist).where(Watchlist.id == watchlist_id)
    wl_result = await db.execute(wl_stmt)
    watchlist = wl_result.scalar_one_or_none()
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    if watchlist.user_id != DEV_USER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # 2. Verify instrument exists
    inst_stmt = select(Instrument).where(Instrument.id == payload.instrument_id)
    inst_result = await db.execute(inst_stmt)
    instrument = inst_result.scalar_one_or_none()
    if instrument is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found")

    # 3. Check duplicate
    dup_stmt = select(WatchlistItem).where(
        WatchlistItem.watchlist_id == watchlist_id,
        WatchlistItem.instrument_id == payload.instrument_id,
    )
    dup_result = await db.execute(dup_stmt)
    if dup_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Instrument already in watchlist")

    # 4. Determine next position
    pos_stmt = select(func.coalesce(func.max(WatchlistItem.position), -1)).where(
        WatchlistItem.watchlist_id == watchlist_id
    )
    pos_result = await db.execute(pos_stmt)
    max_pos = pos_result.scalar_one()
    next_pos = max_pos + 1

    item = WatchlistItem(
        watchlist_id=watchlist_id,
        instrument_id=payload.instrument_id,
        position=next_pos,
    )
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Instrument already in watchlist",
        )

    # Reload with relationship
    stmt = (
        select(WatchlistItem)
        .options(selectinload(WatchlistItem.instrument))
        .where(WatchlistItem.id == item.id)
    )
    item_result = await db.execute(stmt)
    return item_result.scalar_one()


@router.delete("/{watchlist_id}/items/{instrument_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_watchlist_item(
    watchlist_id: int,
    instrument_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    wl_stmt = select(Watchlist).where(Watchlist.id == watchlist_id)
    wl_result = await db.execute(wl_stmt)
    watchlist = wl_result.scalar_one_or_none()
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    if watchlist.user_id != DEV_USER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    item_stmt = select(WatchlistItem).where(
        WatchlistItem.watchlist_id == watchlist_id,
        WatchlistItem.instrument_id == instrument_id,
    )
    item_result = await db.execute(item_stmt)
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not in watchlist")

    await db.delete(item)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{watchlist_id}/items/reorder", response_model=WatchlistDetailResponse)
async def reorder_watchlist_items(
    watchlist_id: int,
    payload: WatchlistReorderRequest,
    db: AsyncSession = Depends(get_db),
) -> Watchlist:
    stmt = (
        select(Watchlist)
        .options(selectinload(Watchlist.items).selectinload(WatchlistItem.instrument))
        .where(Watchlist.id == watchlist_id)
    )
    result = await db.execute(stmt)
    watchlist = result.scalar_one_or_none()
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    if watchlist.user_id != DEV_USER_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    item_map = {item.instrument_id: item for item in watchlist.items}

    # Validate that payload has all and only existing instruments without duplicates
    if set(payload.instrument_ids) != set(item_map.keys()) or len(payload.instrument_ids) != len(item_map):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reorder instrument IDs must match the current watchlist items exactly without duplicates",
        )

    for new_pos, inst_id in enumerate(payload.instrument_ids):
        item_map[inst_id].position = new_pos

    watchlist.updated_at = datetime.now(timezone.utc)
    await db.commit()

    watchlist.items.sort(key=lambda x: x.position)
    return watchlist


# ----------------------------------------------------------------------
# User Check & Change Detection
# ----------------------------------------------------------------------


@router.post("/{watchlist_id}/check", response_model=WatchlistCheckResponse)
async def check_watchlist_endpoint(
    watchlist_id: int,
    db: AsyncSession = Depends(get_db),
) -> WatchlistCheckResponse:
    try:
        res = await mark_watchlist_checked(db, DEV_USER_ID, watchlist_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    return WatchlistCheckResponse(
        watchlist_id=res.watchlist_id,
        checked_at=res.checked_at,
        number_of_instruments=res.number_of_instruments,
        number_with_market_data=res.number_with_market_data,
        number_without_market_data=res.number_without_market_data,
        last_checked_at=res.last_checked_at,
    )


@router.get("/{watchlist_id}/changes", response_model=WatchlistChangesResponse)
async def get_watchlist_changes(
    watchlist_id: int,
    db: AsyncSession = Depends(get_db),
) -> WatchlistChangesResponse:
    try:
        result = await detect_changes_for_watchlist(db, DEV_USER_ID, watchlist_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    change_items: list[DetectedChangeItem] = []
    instruments_with_changes_set = set()

    for ch in result.changes:
        inst = ch.instrument
        base_obs = ch.baseline_observation
        curr_obs = ch.current_observation

        evidence = ch.evidence or {}
        abs_change = evidence.get("absolute_change")
        pct_change = evidence.get("percentage_change")

        change_items.append(
            DetectedChangeItem(
                id=ch.id,
                instrument_id=ch.instrument_id,
                symbol=inst.nse_symbol if inst else "",
                company_name=inst.company_name if inst else "",
                change_type=ch.change_type,
                magnitude=ch.magnitude,
                detected_at=ch.detected_at,
                observation_start=ch.observation_start,
                observation_end=ch.observation_end,
                baseline_observation_id=ch.baseline_observation_id,
                baseline_price=base_obs.price if base_obs else None,
                current_observation_id=ch.current_observation_id,
                current_price=curr_obs.price if curr_obs else None,
                absolute_change=abs_change,
                percentage_change=pct_change,
                evidence=evidence,
                source=curr_obs.source if curr_obs else "NSE",
                data_status=curr_obs.data_status if curr_obs else "final",
                review_status=ch.review_status,
                reviewed_at=ch.reviewed_at,
            )
        )
        instruments_with_changes_set.add(ch.instrument_id)

    status_items = [
        InstrumentStatusItem(
            instrument_id=s.instrument_id,
            symbol=s.symbol,
            company_name=s.company_name,
            baseline_observation_id=s.baseline_observation_id,
            baseline_observed_at=s.baseline_observed_at,
            current_observation_id=s.current_observation_id,
            current_observed_at=s.current_observed_at,
            status=s.status,
            diagnostics=s.diagnostics,
        )
        for s in result.instrument_statuses
    ]

    summary = ChangesSummary(
        total_instruments=len(result.instrument_statuses),
        instruments_with_changes=len(instruments_with_changes_set),
        total_candidate_changes=len(change_items),
        has_unseen_changes=len(change_items) > 0,
    )

    return WatchlistChangesResponse(
        watchlist_id=result.watchlist_id,
        watchlist_name=result.watchlist_name,
        last_checked_at=result.last_checked_at,
        changes=change_items,
        instrument_statuses=status_items,
        summary=summary,
    )


@router.get("/{watchlist_id}/attention", response_model=WatchlistAttentionResponse)
async def get_watchlist_attention_endpoint(
    watchlist_id: int,
    db: AsyncSession = Depends(get_db),
) -> WatchlistAttentionResponse:
    try:
        return await get_watchlist_attention(db, DEV_USER_ID, watchlist_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

