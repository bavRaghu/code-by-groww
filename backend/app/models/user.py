from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.watchlist import Watchlist
    from app.models.user_observation import UserObservation
    from app.models.detected_change import DetectedChange


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    watchlists: Mapped[list["Watchlist"]] = relationship(
        "Watchlist",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    user_observations: Mapped[list["UserObservation"]] = relationship(
        "UserObservation",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    detected_changes: Mapped[list["DetectedChange"]] = relationship(
        "DetectedChange",
        back_populates="user",
        cascade="all, delete-orphan",
    )
