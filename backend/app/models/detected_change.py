import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.instrument import Instrument
    from app.models.market_observation import MarketObservation
    from app.models.significance_assessment import SignificanceAssessment


class ChangeType(str, enum.Enum):
    PRICE_MOVE = "PRICE_MOVE"
    ABNORMAL_RETURN = "ABNORMAL_RETURN"
    RELATIVE_PERFORMANCE = "RELATIVE_PERFORMANCE"
    VOLUME_ANOMALY = "VOLUME_ANOMALY"
    MATERIAL_EVENT = "MATERIAL_EVENT"


class ReviewStatus(str, enum.Enum):
    SURFACED = "surfaced"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


class DetectedChange(Base):
    __tablename__ = "detected_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instrument_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    observation_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    observation_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    baseline_observation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("market_observations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_observation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("market_observations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    magnitude: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
    )
    evidence: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    review_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ReviewStatus.SURFACED.value,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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

    user: Mapped["User"] = relationship("User", back_populates="detected_changes")
    instrument: Mapped["Instrument"] = relationship("Instrument", back_populates="detected_changes")
    baseline_observation: Mapped["MarketObservation"] = relationship(
        "MarketObservation",
        foreign_keys=[baseline_observation_id],
    )
    current_observation: Mapped["MarketObservation"] = relationship(
        "MarketObservation",
        foreign_keys=[current_observation_id],
    )
    assessment: Mapped["SignificanceAssessment | None"] = relationship(
        "SignificanceAssessment",
        back_populates="detected_change",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "instrument_id",
            "baseline_observation_id",
            "current_observation_id",
            "change_type",
            name="uq_detected_change_identity",
        ),
    )
