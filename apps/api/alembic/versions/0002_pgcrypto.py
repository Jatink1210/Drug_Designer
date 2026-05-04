"""Enable pgcrypto extension and add encrypted columns — §61.1.

Revision ID: 0002_pgcrypto
Revises: 0001_full_schema
Create Date: 2026-04-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_pgcrypto"
down_revision: Union[str, None] = "0001_full_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable pgcrypto and add encrypted columns for PII."""
    bind = op.get_bind()
    # Enable pgcrypto extension (PostgreSQL only — skip for SQLite)
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Add encrypted email column to users table
    op.add_column("users", sa.Column("email_encrypted", sa.LargeBinary(), nullable=True))

    # Add encrypted details column to audit_log
    op.add_column("audit_log", sa.Column("details_encrypted", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    """Remove encrypted columns."""
    op.drop_column("audit_log", "details_encrypted")
    op.drop_column("users", "email_encrypted")
