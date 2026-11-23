"""Violation ORM model — core detection record."""

import uuid
from enum import Enum

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from app.core.database import Base


class ViolationType(str, Enum):
    NO_HELMET = "no_helmet"
    NO_VEST = "no_vest"
    NO_GLOVES = "no_gloves"
    NO_BOOTS = "no_boots"
    NO_MASK = "no_mask"
    MULTIPLE = "multiple"


class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    camera_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True, index=True
    )
    site_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    snapshot_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_key: Mapped[str | None] = mapped_column(Text, nullable=True)  # R2 object key
    timestamp: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    resolved_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    camera: Mapped["Camera"] = relationship("Camera", back_populates="violations")  # noqa: F821
    site: Mapped["Site"] = relationship("Site", back_populates="violations")  # noqa: F821
    resolver: Mapped["User"] = relationship("User", foreign_keys=[resolved_by])  # noqa: F821

    def __repr__(self) -> str:
        return f"<Violation {self.type} site={self.site_id} resolved={self.resolved}>"
