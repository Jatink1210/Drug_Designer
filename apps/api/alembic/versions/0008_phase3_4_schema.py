"""Phase 3/4 schema additions — clinical workflows, SynthArena sessions,
lab runs, PICO extractions, contradiction analysis.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-01

Task 28: Database migrations for Phase 3/4 features.
"""

from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    """Check whether a column already exists."""
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in cols


def _table_exists(bind, table_name: str) -> bool:
    insp = sa.inspect(bind)
    return insp.has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()

    # Clinical workflow steps tracking
    if not _table_exists(bind, 'clinical_workflow_steps'):
        op.create_table(
            'clinical_workflow_steps',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('workflow_id', sa.String(36), sa.ForeignKey('runs.id'), nullable=False),
            sa.Column('step_number', sa.Integer, nullable=False),
            sa.Column('step_key', sa.String(50), nullable=False),
            sa.Column('status', sa.String(20), nullable=False, server_default='not_started'),
            sa.Column('input_data', sa.JSON, nullable=True),
            sa.Column('output_data', sa.JSON, nullable=True),
            sa.Column('evidence', sa.JSON, nullable=True),
            sa.Column('error_message', sa.Text, nullable=True),
            sa.Column('justification', sa.Text, nullable=True),
            sa.Column('started_at', sa.DateTime, nullable=True),
            sa.Column('completed_at', sa.DateTime, nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index('ix_clinical_workflow_steps_workflow_id', 'clinical_workflow_steps', ['workflow_id'])
        op.create_index('ix_clinical_workflow_steps_status', 'clinical_workflow_steps', ['status'])

    # PICO extractions table
    if not _table_exists(bind, 'pico_extractions'):
        op.create_table(
            'pico_extractions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('project_id', sa.String(36), nullable=True),
            sa.Column('query', sa.Text, nullable=True),
            sa.Column('publication_title', sa.Text, nullable=True),
            sa.Column('pmid', sa.String(20), nullable=True),
            sa.Column('population', sa.JSON, nullable=True),
            sa.Column('intervention', sa.JSON, nullable=True),
            sa.Column('comparison', sa.JSON, nullable=True),
            sa.Column('outcome', sa.JSON, nullable=True),
            sa.Column('study_design', sa.String(50), nullable=True),
            sa.Column('sample_size', sa.Integer, nullable=True),
            sa.Column('overall_confidence', sa.Float, nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index('ix_pico_extractions_query', 'pico_extractions', ['query'])
        op.create_index('ix_pico_extractions_pmid', 'pico_extractions', ['pmid'])

    # Contradiction analysis results table
    if not _table_exists(bind, 'contradiction_analyses'):
        op.create_table(
            'contradiction_analyses',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('query', sa.Text, nullable=False),
            sa.Column('contradictions_count', sa.Integer, nullable=True),
            sa.Column('similarities_count', sa.Integer, nullable=True),
            sa.Column('evidence_landscape', sa.JSON, nullable=True),
            sa.Column('results', sa.JSON, nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index('ix_contradiction_analyses_query', 'contradiction_analyses', ['query'])

    # Add workflow_type to runs for clinical workflow tracking
    if not _column_exists(bind, 'runs', 'workflow_type'):
        op.add_column(
            'runs',
            sa.Column('workflow_type', sa.String(50), nullable=True)
        )

    # SynthArena session metadata (for DB-backed sessions)
    if not _table_exists(bind, 'syntharena_sessions'):
        op.create_table(
            'syntharena_sessions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('target', sa.String(200), nullable=True),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
            sa.Column('compounds', sa.JSON, nullable=True),
            sa.Column('scores', sa.JSON, nullable=True),
            sa.Column('rankings', sa.JSON, nullable=True),
            sa.Column('debate_history', sa.JSON, nullable=True),
            sa.Column('dossier_consensus', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index('ix_syntharena_sessions_status', 'syntharena_sessions', ['status'])


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, 'syntharena_sessions'):
        op.drop_table('syntharena_sessions')
    if _table_exists(bind, 'contradiction_analyses'):
        op.drop_table('contradiction_analyses')
    if _table_exists(bind, 'pico_extractions'):
        op.drop_table('pico_extractions')
    if _table_exists(bind, 'clinical_workflow_steps'):
        op.drop_table('clinical_workflow_steps')
    if _column_exists(bind, 'runs', 'workflow_type'):
        op.drop_column('runs', 'workflow_type')
