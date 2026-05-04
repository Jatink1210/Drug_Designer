"""Clinical workflow tables for 10-stage pipeline

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-21

This migration adds 9 tables for the clinical workflow pipeline:
1. clinical_records - EHR data storage with PHI redaction
2. phenotype_clusters - HDBSCAN clustering results
3. tissue_analyses - Histopathology image analysis
4. biomarker_profiles - Flow cytometry quantification
5. genomic_variants - VCF parsing results
6. pathogenicity_predictions - DL model predictions
7. disruption_models - Mutation effect simulations
8. therapy_stratifications - Patient compatibility scores
9. consensus_results - MAV consensus voting results

Requirements: FR-DB-002, FR-API-002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002_pgcrypto'
branch_labels = None
depends_on = None


def upgrade():
    # 1. clinical_records table
    op.create_table(
        'clinical_records',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('patient_id', sa.String(), nullable=False),  # Hashed/anonymized
        sa.Column('record_type', sa.String(50), nullable=False),  # ehr | family_history | clinical_note
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('structured_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('phi_redacted', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_clinical_records_project', 'clinical_records', ['project_id'])
    op.create_index('ix_clinical_records_patient', 'clinical_records', ['patient_id'])

    # 2. phenotype_clusters table
    op.create_table(
        'phenotype_clusters',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('cluster_id', sa.Integer(), nullable=False),
        sa.Column('phenotypes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),  # Array of {term, hpo_id, severity}
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('rarity_score', sa.Float(), nullable=False),
        sa.Column('representative_terms', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_phenotype_clusters_run', 'phenotype_clusters', ['run_id'])

    # 3. tissue_analyses table
    op.create_table(
        'tissue_analyses',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('image_ref', sa.String(500), nullable=False),  # S3 key for WSI
        sa.Column('anomalies_detected', postgresql.JSONB(astext_type=sa.Text()), nullable=False),  # Array of {type, location, confidence}
        sa.Column('heatmap_ref', sa.String(500), nullable=True),  # S3 key for heatmap
        sa.Column('model_version', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tissue_analyses_run', 'tissue_analyses', ['run_id'])

    # 4. biomarker_profiles table
    op.create_table(
        'biomarker_profiles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('sample_id', sa.String(255), nullable=False),
        sa.Column('cell_populations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),  # Array of {population, count, percentage}
        sa.Column('abnormal_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('reference_comparison', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_biomarker_profiles_run', 'biomarker_profiles', ['run_id'])

    # 5. genomic_variants table
    op.create_table(
        'genomic_variants',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('chromosome', sa.String(10), nullable=False),
        sa.Column('position', sa.BigInteger(), nullable=False),
        sa.Column('ref_allele', sa.String(1000), nullable=False),
        sa.Column('alt_allele', sa.String(1000), nullable=False),
        sa.Column('variant_type', sa.String(50), nullable=False),  # snv | indel | cnv
        sa.Column('gene_symbol', sa.String(100), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('population_frequency', sa.Float(), nullable=True),
        sa.Column('annotations', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_genomic_variants_run', 'genomic_variants', ['run_id'])
    op.create_index('ix_genomic_variants_gene', 'genomic_variants', ['gene_symbol'])

    # 6. pathogenicity_predictions table
    op.create_table(
        'pathogenicity_predictions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('variant_id', sa.String(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),  # 0-1
        sa.Column('classification', sa.String(50), nullable=False),  # pathogenic | likely_pathogenic | uncertain | likely_benign | benign
        sa.Column('confidence_interval', postgresql.JSONB(astext_type=sa.Text()), nullable=False),  # {lower, upper}
        sa.Column('features_used', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('model_version', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['variant_id'], ['genomic_variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_pathogenicity_predictions_variant', 'pathogenicity_predictions', ['variant_id'])

    # 7. disruption_models table
    op.create_table(
        'disruption_models',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('variant_id', sa.String(), nullable=True),
        sa.Column('affected_pathways', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('transcriptional_impacts', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('immune_dysregulation', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('disruption_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['genomic_variants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_disruption_models_run', 'disruption_models', ['run_id'])

    # 8. therapy_stratifications table
    op.create_table(
        'therapy_stratifications',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('therapy_type', sa.String(100), nullable=False),  # stem_cell | bone_marrow | gene_therapy
        sa.Column('compatibility_score', sa.Float(), nullable=False),
        sa.Column('risk_benefit_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('eligibility_criteria', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('timeline_estimate', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_therapy_stratifications_run', 'therapy_stratifications', ['run_id'])

    # 9. consensus_results table (for MAV consensus protocol)
    op.create_table(
        'consensus_results',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('claim', sa.Text(), nullable=False),
        sa.Column('evidence_bundle_id', sa.String(), nullable=True),
        sa.Column('jury_size', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),  # verified | contradicted | conflict
        sa.Column('votes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),  # Array of {agent_id, verdict, confidence, reasoning}
        sa.Column('consensus_trace', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['evidence_bundle_id'], ['evidence_bundles.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_consensus_results_status', 'consensus_results', ['status'])


def downgrade():
    # Drop tables in reverse order (respecting foreign key dependencies)
    op.drop_index('ix_consensus_results_status', table_name='consensus_results')
    op.drop_table('consensus_results')
    
    op.drop_index('ix_therapy_stratifications_run', table_name='therapy_stratifications')
    op.drop_table('therapy_stratifications')
    
    op.drop_index('ix_disruption_models_run', table_name='disruption_models')
    op.drop_table('disruption_models')
    
    op.drop_index('ix_pathogenicity_predictions_variant', table_name='pathogenicity_predictions')
    op.drop_table('pathogenicity_predictions')
    
    op.drop_index('ix_genomic_variants_gene', table_name='genomic_variants')
    op.drop_index('ix_genomic_variants_run', table_name='genomic_variants')
    op.drop_table('genomic_variants')
    
    op.drop_index('ix_biomarker_profiles_run', table_name='biomarker_profiles')
    op.drop_table('biomarker_profiles')
    
    op.drop_index('ix_tissue_analyses_run', table_name='tissue_analyses')
    op.drop_table('tissue_analyses')
    
    op.drop_index('ix_phenotype_clusters_run', table_name='phenotype_clusters')
    op.drop_table('phenotype_clusters')
    
    op.drop_index('ix_clinical_records_patient', table_name='clinical_records')
    op.drop_index('ix_clinical_records_project', table_name='clinical_records')
    op.drop_table('clinical_records')
