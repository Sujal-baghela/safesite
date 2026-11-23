"""Company ORM model."""

import uuid
from enum import Enum

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from app.core.database import Base


class PlanTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default=PlanTier.FREE.value)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="company")  # noqa: F821
    sites: Mapped[list["Site"]] = relationship("Site", back_populates="company")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Company {self.name} plan={self.plan}>"
