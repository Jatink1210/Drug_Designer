"""§91 Wave 5 — Graph, Pathways, and Artifacts tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-24

Wave 5 of the 6-Wave DB Migration Plan (§91):
Creates: graph_nodes, graph_edges, pathway_records, pathway_memberships,
         reports, dossiers, media_artifacts, exports, memory_objects
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. graph_nodes
    op.create_table(
        'graph_nodes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=True),
        sa.Column('properties', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('source_system', sa.String(), nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_graph_nodes_project_id', 'graph_nodes', ['project_id'])
    op.create_index('ix_graph_nodes_entity_id', 'graph_nodes', ['entity_id'])
    op.create_index('ix_graph_nodes_entity_type', 'graph_nodes', ['entity_type'])

    # 2. graph_edges
    op.create_table(
        'graph_edges',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('source_id', sa.String(), nullable=False),
        sa.Column('target_id', sa.String(), nullable=False),
        sa.Column('edge_type', sa.String(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('properties', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('source_system', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_graph_edges_project_id', 'graph_edges', ['project_id'])
    op.create_index('ix_graph_edges_source_id', 'graph_edges', ['source_id'])
    op.create_index('ix_graph_edges_target_id', 'graph_edges', ['target_id'])
    op.create_index('ix_graph_edges_edge_type', 'graph_edges', ['edge_type'])

    # 3. pathway_records
    op.create_table(
        'pathway_records',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('pathway_id', sa.String(), nullable=False),
        sa.Column('source_system', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('species', sa.String(), nullable=True),
        sa.Column('gene_count', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pathway_records_pathway_id', 'pathway_records', ['pathway_id'])
    op.create_index('ix_pathway_records_source_system', 'pathway_records', ['source_system'])

    # 4. pathway_memberships
    op.create_table(
        'pathway_memberships',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('pathway_record_id', sa.String(), nullable=False),
        sa.Column('gene_symbol', sa.String(), nullable=False),
        sa.Column('uniprot_accession', sa.String(), nullable=True),
        sa.Column('role', sa.String(), nullable=True),
        sa.Column('evidence_code', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['pathway_record_id'], ['pathway_records.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pathway_memberships_pathway_record_id', 'pathway_memberships', ['pathway_record_id'])
    op.create_index('ix_pathway_memberships_gene_symbol', 'pathway_memberships', ['gene_symbol'])

    # 5. reports
    op.create_table(
        'reports',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('run_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('report_type', sa.String(), nullable=False, server_default='analysis'),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('file_ref', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reports_project_id', 'reports', ['project_id'])

    # 6. dossiers
    op.create_table(
        'dossiers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('target_symbol', sa.String(), nullable=True),
        sa.Column('disease_name', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('sections', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('evidence_ids', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('file_ref', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_dossiers_project_id', 'dossiers', ['project_id'])

    # 7. media_artifacts
    op.create_table(
        'media_artifacts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('run_id', sa.String(), nullable=True),
        sa.Column('artifact_type', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('file_ref', sa.String(), nullable=False),
        sa.Column('mime_type', sa.String(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_media_artifacts_project_id', 'media_artifacts', ['project_id'])

    # 8. exports
    op.create_table(
        'exports',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('object_type', sa.String(), nullable=False),
        sa.Column('object_id', sa.String(), nullable=False),
        sa.Column('export_format', sa.String(), nullable=False, server_default='json'),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('file_ref', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_exports_project_id', 'exports', ['project_id'])

    # 9. memory_objects
    op.create_table(
        'memory_objects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('object_type', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('ttl_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_memory_objects_project_id', 'memory_objects', ['project_id'])
    op.create_index('ix_memory_objects_key', 'memory_objects', ['key'])


def downgrade() -> None:
    op.drop_table('memory_objects')
    op.drop_table('exports')
    op.drop_table('media_artifacts')
    op.drop_table('dossiers')
    op.drop_table('reports')
    op.drop_table('pathway_memberships')
    op.drop_table('pathway_records')
    op.drop_table('graph_edges')
    op.drop_table('graph_nodes')
