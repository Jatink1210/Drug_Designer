"""§91 Wave 4 — Disease, Target, and Mapping tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-24

Wave 4 of the 6-Wave DB Migration Plan (§91):
Creates: disease_queries, disease_source_hits, disease_candidate_genes,
         uniprot_mappings, target_rankings

These tables have FK dependencies on Wave 1 (projects) and Wave 2 (runs),
so they must come after Wave 3 (sources/evidence).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. disease_queries
    op.create_table(
        'disease_queries',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('raw_text', sa.String(), nullable=False),
        sa.Column('normalized_name', sa.String(), nullable=True),
        sa.Column('mondo_id', sa.String(), nullable=True),
        sa.Column('omim_id', sa.String(), nullable=True),
        sa.Column('mesh_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_disease_queries_project_id', 'disease_queries', ['project_id'])
    op.create_index('ix_disease_queries_mondo_id', 'disease_queries', ['mondo_id'])

    # 2. disease_source_hits
    op.create_table(
        'disease_source_hits',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('query_id', sa.String(), nullable=False),
        sa.Column('source_name', sa.String(), nullable=False),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('hit_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['query_id'], ['disease_queries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_disease_source_hits_query_id', 'disease_source_hits', ['query_id'])

    # 3. disease_candidate_genes
    op.create_table(
        'disease_candidate_genes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('query_id', sa.String(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('entrez_id', sa.String(), nullable=True),
        sa.Column('uniprot_id', sa.String(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('sources', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('evidence_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['query_id'], ['disease_queries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_disease_candidate_genes_query_id', 'disease_candidate_genes', ['query_id'])
    op.create_index('ix_disease_candidate_genes_symbol', 'disease_candidate_genes', ['symbol'])

    # 4. uniprot_mappings
    op.create_table(
        'uniprot_mappings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('query_id', sa.String(), nullable=True),
        sa.Column('gene_symbol', sa.String(), nullable=False),
        sa.Column('uniprot_accession', sa.String(), nullable=True),
        sa.Column('protein_name', sa.String(), nullable=True),
        sa.Column('organism', sa.String(), nullable=True),
        sa.Column('sequence_length', sa.Integer(), nullable=True),
        sa.Column('go_terms', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('pathways', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('pdb_ids', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['query_id'], ['disease_queries.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_uniprot_mappings_gene_symbol', 'uniprot_mappings', ['gene_symbol'])
    op.create_index('ix_uniprot_mappings_uniprot_accession', 'uniprot_mappings', ['uniprot_accession'])

    # 5. target_rankings
    op.create_table(
        'target_rankings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=True),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('gene_symbol', sa.String(), nullable=False),
        sa.Column('uniprot_accession', sa.String(), nullable=True),
        sa.Column('composite_score', sa.Float(), nullable=False),
        sa.Column('druggability_score', sa.Float(), nullable=True),
        sa.Column('evidence_score', sa.Float(), nullable=True),
        sa.Column('pathway_score', sa.Float(), nullable=True),
        sa.Column('safety_score', sa.Float(), nullable=True),
        sa.Column('gat_embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('profile', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_target_rankings_project_id', 'target_rankings', ['project_id'])
    op.create_index('ix_target_rankings_gene_symbol', 'target_rankings', ['gene_symbol'])
    op.create_index('ix_target_rankings_composite_score', 'target_rankings', ['composite_score'])


def downgrade() -> None:
    op.drop_table('target_rankings')
    op.drop_table('uniprot_mappings')
    op.drop_table('disease_candidate_genes')
    op.drop_table('disease_source_hits')
    op.drop_table('disease_queries')
