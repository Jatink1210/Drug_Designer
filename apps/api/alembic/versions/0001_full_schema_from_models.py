"""full_schema_from_models — §91 6-Wave DB schema in a single initial migration.

Revision ID: 0001_full_schema
Revises:
Create Date: 2026-04-16 00:00:00.000000

This migration creates all 35+ tables defined in models/db_tables.py and
models/user.py. It uses Base.metadata.create_all() to ensure perfect
alignment with the SQLAlchemy model definitions.

For subsequent schema changes, use:
    alembic revision --autogenerate -m "description"
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_full_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables from the current model definitions."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from core.db import Base  # noqa: E402

    # Import every model so the metadata is populated
    from models.user import User, Project  # noqa: E402, F401
    from models.db_tables import (  # noqa: E402, F401
        Session, UserPreference, ProjectMember, ProjectNote,
        Run, Job, RunEvent,
        Source, SourceHealthRecord, EvidenceItemRecord,
        EvidenceAnnotationRecord, EvidenceBundleRecord, EvidenceBundleItem,
        DiseaseQuery, DiseaseSourceHit, DiseaseCandidateGene,
        UniProtMappingRecord, TargetRanking,
        GraphNodeRecord, GraphEdgeRecord, PathwayRecordDB, PathwayMembershipDB,
        ReportRecord, DossierRecord, MediaArtifactRecord, ExportRecord,
        MemoryObjectRecord,
        ModelRegistryRecord, ModelVersionRecord, RuntimeBackendRecord,
        LocalAgentRecord, LocalAgentEvent, RuntimeSelection, AuditLog,
    )

    bind = op.get_bind()
    Base.metadata.create_all(bind, checkfirst=True)


def downgrade() -> None:
    """Drop all tables in reverse dependency order.
    
    Safety: refuses to drop in non-development environments.
    """
    import sys, os
    env = os.getenv("DSS_ENV", "development")
    if env != "development":
        raise RuntimeError(
            f"Refusing to drop all tables in {env} environment. "
            "Set DSS_ENV=development to allow destructive downgrade."
        )

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from core.db import Base  # noqa: E402
    from models.user import User, Project  # noqa: E402, F401
    from models.db_tables import (  # noqa: E402, F401
        Session, UserPreference, ProjectMember, ProjectNote,
        Run, Job, RunEvent,
        Source, SourceHealthRecord, EvidenceItemRecord,
        EvidenceAnnotationRecord, EvidenceBundleRecord, EvidenceBundleItem,
        DiseaseQuery, DiseaseSourceHit, DiseaseCandidateGene,
        UniProtMappingRecord, TargetRanking,
        GraphNodeRecord, GraphEdgeRecord, PathwayRecordDB, PathwayMembershipDB,
        ReportRecord, DossierRecord, MediaArtifactRecord, ExportRecord,
        MemoryObjectRecord,
        ModelRegistryRecord, ModelVersionRecord, RuntimeBackendRecord,
        LocalAgentRecord, LocalAgentEvent, RuntimeSelection, AuditLog,
        ConsensusResult, ConsensusVote,
    )

    bind = op.get_bind()
    Base.metadata.drop_all(bind)
