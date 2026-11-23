"""Initial schema — all core tables with indexes.

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""

from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- companies ---
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_company_id", "users", ["company_id"])

    # --- sites ---
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sites_company_id", "sites", ["company_id"])

    # --- cameras ---
    op.create_table(
        "cameras",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("rtsp_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="inactive"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cameras_site_id", "cameras", ["site_id"])

    # --- violations ---
    op.create_table(
        "violations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "camera_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("cameras.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("snapshot_url", sa.Text, nullable=True),
        sa.Column("snapshot_key", sa.Text, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Performance indexes — these make dashboard queries fast
    op.create_index("ix_violations_site_id", "violations", ["site_id"])
    op.create_index("ix_violations_camera_id", "violations", ["camera_id"])
    op.create_index("ix_violations_timestamp", "violations", ["timestamp"])
    op.create_index("ix_violations_type", "violations", ["type"])
    op.create_index("ix_violations_resolved", "violations", ["resolved"])
    # Composite index for the most common dashboard query
    op.create_index(
        "ix_violations_site_timestamp",
        "violations",
        ["site_id", "timestamp"],
    )

    # --- alerts ---
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("config_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alerts_site_id", "alerts", ["site_id"])

    # --- reports ---
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("pdf_url", sa.Text, nullable=True),
        sa.Column("period", sa.String(100), nullable=True),
    )
    op.create_index("ix_reports_site_id", "reports", ["site_id"])


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("alerts")
    op.drop_table("violations")
    op.drop_table("cameras")
    op.drop_table("sites")
    op.drop_table("users")
    op.drop_table("companies")
