from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.instrument import InstrumentResponse


class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Watchlist name cannot be empty or whitespace only")
        return stripped


class WatchlistUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Watchlist name cannot be empty or whitespace only")
        return stripped


class WatchlistItemCreate(BaseModel):
    instrument_id: int


class WatchlistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    watchlist_id: int
    instrument_id: int
    position: int
    added_at: datetime
    instrument: InstrumentResponse | None = None


class WatchlistSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    last_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    item_count: int = 0


class WatchlistDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    last_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[WatchlistItemResponse]


class WatchlistReorderRequest(BaseModel):
    instrument_ids: list[int] = Field(..., min_length=1)
