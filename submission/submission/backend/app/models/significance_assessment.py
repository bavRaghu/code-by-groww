import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.detected_change import DetectedChange


class SignificanceLevel(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class SignificanceAssessment(Base):
    __tablename__ = "significance_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detected_change_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("detected_changes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    magnitude_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    abnormality_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    relative_performance_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    volume_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    event_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    overall_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )
    significance_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    evidence: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
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

    detected_change: Mapped["DetectedChange"] = relationship(
        "DetectedChange",
        back_populates="assessment",
    )

    __table_args__ = (
        UniqueConstraint("detected_change_id", name="uq_assessment_detected_change"),
    )
