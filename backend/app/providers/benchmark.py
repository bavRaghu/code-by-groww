from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.market_observation import MarketObservation


class BenchmarkProvider(ABC):
    """Abstract boundary for retrieving benchmark index returns."""

    @abstractmethod
    async def get_benchmark_return(
        self,
        db: AsyncSession,
        start_time: datetime,
        end_time: datetime,
        benchmark_symbol: str = "NIFTY 50",
    ) -> Decimal | None:
        """
        Calculates simple benchmark return between start_time and end_time.
        Returns None if benchmark instrument or observations are unavailable.
        """
        pass


class NSEBenchmarkProvider(BenchmarkProvider):
    """Default benchmark provider checking persisted index observations."""

    async def get_benchmark_return(
        self,
        db: AsyncSession,
        start_time: datetime,
        end_time: datetime,
        benchmark_symbol: str = "NIFTY 50",
    ) -> Decimal | None:
        # 1. Look up benchmark instrument
        inst_stmt = select(Instrument).where(Instrument.nse_symbol == benchmark_symbol)
        inst_res = await db.execute(inst_stmt)
        benchmark_inst = inst_res.scalar_one_or_none()
        if benchmark_inst is None:
            return None

        # 2. Find observation at or prior to start_time
        start_obs_stmt = (
            select(MarketObservation)
            .where(
                MarketObservation.instrument_id == benchmark_inst.id,
                MarketObservation.observed_at <= start_time,
            )
            .order_by(MarketObservation.observed_at.desc())
            .limit(1)
        )
        start_obs_res = await db.execute(start_obs_stmt)
        start_obs = start_obs_res.scalar_one_or_none()
        if start_obs is None or start_obs.price <= 0:
            return None

        # 3. Find observation at or prior to end_time
        end_obs_stmt = (
            select(MarketObservation)
            .where(
                MarketObservation.instrument_id == benchmark_inst.id,
                MarketObservation.observed_at <= end_time,
            )
            .order_by(MarketObservation.observed_at.desc())
            .limit(1)
        )
        end_obs_res = await db.execute(end_obs_stmt)
        end_obs = end_obs_res.scalar_one_or_none()
        if end_obs is None or end_obs.id == start_obs.id:
            return None

        # Simple return: (end_price - start_price) / start_price
        ret = (end_obs.price - start_obs.price) / start_obs.price
        return ret
