from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession


class MaterialEventProvider(ABC):
    """Abstract boundary for retrieving external material company events."""

    @abstractmethod
    async def get_events_for_instrument(
        self,
        db: AsyncSession,
        instrument_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch real material events occurred within time window."""
        pass


class NullMaterialEventProvider(MaterialEventProvider):
    """
    Null implementation for Milestone 2.
    Does not fabricate events when no verified provider is connected.
    """

    async def get_events_for_instrument(
        self,
        db: AsyncSession,
        instrument_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        return []
