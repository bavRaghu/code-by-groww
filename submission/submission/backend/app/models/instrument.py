from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.watchlist import WatchlistItem
    from app.models.market_observation import MarketObservation
    from app.models.user_observation import UserObservation
    from app.models.detected_change import DetectedChange
    from app.models.news_article import NewsArticle


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    nse_symbol: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    bse_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False, default="NSE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        "WatchlistItem",
        back_populates="instrument",
        cascade="all, delete-orphan",
    )
    market_observations: Mapped[list["MarketObservation"]] = relationship(
        "MarketObservation",
        back_populates="instrument",
        cascade="all, delete-orphan",
    )
    user_observations: Mapped[list["UserObservation"]] = relationship(
        "UserObservation",
        back_populates="instrument",
        cascade="all, delete-orphan",
    )
    detected_changes: Mapped[list["DetectedChange"]] = relationship(
        "DetectedChange",
        back_populates="instrument",
        cascade="all, delete-orphan",
    )
    news_articles: Mapped[list["NewsArticle"]] = relationship(
        "NewsArticle",
        back_populates="instrument",
        cascade="all, delete-orphan",
    )
