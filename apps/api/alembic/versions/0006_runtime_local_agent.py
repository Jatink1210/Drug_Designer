"""§91 Wave 6 — Runtime and Local Agent tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-24

Wave 6 of the 6-Wave DB Migration Plan (§91):
Creates: model_registry, model_versions, runtime_backends, local_agents,
         local_agent_events, model_install_requests, runtime_selections
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. model_registry  (spec name: "models")
    op.create_table(
        'model_registry',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('model_key', sa.String(), nullable=False),
        sa.Column('family', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('capabilities', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('hardware_requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_key', name='uq_model_registry_model_key'),
    )
    op.create_index('ix_model_registry_model_key', 'model_registry', ['model_key'])
    op.create_index('ix_model_registry_family', 'model_registry', ['family'])

    # 2. model_versions
    op.create_table(
        'model_versions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('model_id', sa.String(), nullable=False),
        sa.Column('version_tag', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='available'),
        sa.Column('download_url', sa.String(), nullable=True),
        sa.Column('sha256', sa.String(), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('quantization', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['model_id'], ['model_registry.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_model_versions_model_id', 'model_versions', ['model_id'])

    # 3. runtime_backends
    op.create_table(
        'runtime_backends',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('backend_type', sa.String(), nullable=False),
        sa.Column('endpoint_url', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='offline'),
        sa.Column('hardware_profile', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('capabilities', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('last_ping_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_runtime_backends_status', 'runtime_backends', ['status'])

    # 4. local_agents
    op.create_table(
        'local_agents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('backend_id', sa.String(), nullable=True),
        sa.Column('agent_version', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='offline'),
        sa.Column('hardware_info', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('installed_models', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['backend_id'], ['runtime_backends.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_local_agents_status', 'local_agents', ['status'])

    # 5. local_agent_events
    op.create_table(
        'local_agent_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['local_agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_local_agent_events_agent_id', 'local_agent_events', ['agent_id'])
    op.create_index('ix_local_agent_events_event_type', 'local_agent_events', ['event_type'])
    op.create_index('ix_local_agent_events_created_at', 'local_agent_events', ['created_at'])

    # 6. model_install_requests
    op.create_table(
        'model_install_requests',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('model_version_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('progress_pct', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('requested_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['local_agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_model_install_requests_agent_id', 'model_install_requests', ['agent_id'])

    # 7. runtime_selections
    op.create_table(
        'runtime_selections',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=True),
        sa.Column('model_version_id', sa.String(), nullable=True),
        sa.Column('backend_id', sa.String(), nullable=True),
        sa.Column('routing_reason', sa.String(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['backend_id'], ['runtime_backends.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_runtime_selections_run_id', 'runtime_selections', ['run_id'])


def downgrade() -> None:
    op.drop_table('runtime_selections')
    op.drop_table('model_install_requests')
    op.drop_table('local_agent_events')
    op.drop_table('local_agents')
    op.drop_table('runtime_backends')
    op.drop_table('model_versions')
    op.drop_table('model_registry')
