from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
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
    await db.commit()

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
