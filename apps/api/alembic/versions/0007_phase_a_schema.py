"""Phase A schema additions — contradiction_type, degraded_sources_json,
per_source_evidence_json, parent_version_id, consensus_votes table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-28

Phase A of the gap-analysis task list:
  A-2  evidence_items.contradiction_type (VARCHAR 50)
  A-3  runs.degraded_sources_json (JSON)
  A-5  target_rankings.per_source_evidence_json (JSON)
  A-6  model_registry.parent_version_id (FK self-ref)
  A-7  consensus_votes table (run_id FK, entity_id, specialist_role, vote JSON)
"""

from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    """Check whether a column already exists (portable helper)."""
    import sqlalchemy as _sa
    insp = _sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in cols


def _table_exists(bind, table_name: str) -> bool:
    import sqlalchemy as _sa
    insp = _sa.inspect(bind)
    return insp.has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()

    # A-2: contradiction_type to evidence_items
    if not _column_exists(bind, 'evidence_items', 'contradiction_type'):
        op.add_column(
            'evidence_items',
            sa.Column('contradiction_type', sa.String(50), nullable=True)
        )

    # A-3: degraded_sources_json to runs
    if not _column_exists(bind, 'runs', 'degraded_sources_json'):
        op.add_column(
            'runs',
            sa.Column('degraded_sources_json', sa.JSON(), nullable=True,
                      server_default='[]')
        )

    # A-5: per_source_evidence_json to target_rankings
    if not _column_exists(bind, 'target_rankings', 'per_source_evidence_json'):
        op.add_column(
            'target_rankings',
            sa.Column('per_source_evidence_json', sa.JSON(), nullable=True,
                      server_default='{}')
        )

    # A-6: parent_version_id FK (self-referential) to model_registry
    if not _column_exists(bind, 'model_registry', 'parent_version_id'):
        op.add_column(
            'model_registry',
            sa.Column('parent_version_id', sa.String(), nullable=True)
        )
    # SQLite does not support ADD CONSTRAINT via ALTER TABLE, so only add FK
    # on PostgreSQL.  The ORM relationship is still defined in db_tables.py
    # and enforced at application level for SQLite (workbench mode).
    if bind.dialect.name == 'postgresql':
        op.create_foreign_key(
            'fk_model_registry_parent_version_id',
            'model_registry', 'model_registry',
            ['parent_version_id'], ['id'],
            ondelete='SET NULL'
        )

    # A-7: consensus_votes table
    if not _table_exists(bind, 'consensus_votes'):
        op.create_table(
            'consensus_votes',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('run_id', sa.String(), nullable=False),
            sa.Column('entity_id', sa.String(), nullable=False),
            sa.Column('specialist_role', sa.String(100), nullable=False),
            sa.Column('vote', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True),
                      server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_consensus_votes_run_entity',
                        'consensus_votes', ['run_id', 'entity_id'])
        op.create_index('ix_consensus_votes_run_id',
                        'consensus_votes', ['run_id'])


def downgrade() -> None:
    op.drop_index('ix_consensus_votes_run_id', table_name='consensus_votes')
    op.drop_index('ix_consensus_votes_run_entity', table_name='consensus_votes')
    op.drop_table('consensus_votes')

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.drop_constraint('fk_model_registry_parent_version_id',
                           'model_registry', type_='foreignkey')
    op.drop_column('model_registry', 'parent_version_id')
    op.drop_column('target_rankings', 'per_source_evidence_json')
    op.drop_column('runs', 'degraded_sources_json')
    op.drop_column('evidence_items', 'contradiction_type')
