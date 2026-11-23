"""Site and Camera ORM models."""

import uuid
from enum import Enum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from app.core.database import Base


class CameraStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="sites")  # noqa: F821
    cameras: Mapped[list["Camera"]] = relationship("Camera", back_populates="site")
    violations: Mapped[list["Violation"]] = relationship("Violation", back_populates="site")  # noqa: F821
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="site")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Site {self.name}>"


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    site_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rtsp_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=CameraStatus.INACTIVE.value
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    site: Mapped["Site"] = relationship("Site", back_populates="cameras")
    violations: Mapped[list["Violation"]] = relationship("Violation", back_populates="camera")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Camera {self.name} status={self.status}>"
