"""cockpit_runs table for run tracking

Revision ID: 0009
Revises: 0008_phase3_4_schema
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0009"
down_revision = "0008_phase3_4_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cockpit_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("result_summary", JSONB, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provenance", JSONB, nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "idx_cockpit_runs_user_created",
        "cockpit_runs",
        ["user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_cockpit_runs_user_created", table_name="cockpit_runs")
    op.drop_table("cockpit_runs")
