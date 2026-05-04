"""Alembic Configuration — Database Migration Manager (Drug Designer §56.3).

§56.3: Every schema change requires a versioned migration file.
Tool: Alembic (SQLAlchemy migration framework)
Environments: dev → staging → production with separate migration tracking.
Rollback: Every migration must have a downgrade() function.

Initialize with: alembic init alembic
Then: alembic revision --autogenerate -m "description"
Then: alembic upgrade head
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

import os
import sys

# Add the API directory to path so models can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import Base

# Import ALL models so Alembic can detect them for autogeneration
from models.user import User, Project
from models.db_tables import (
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

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate
target_metadata = Base.metadata

# Get database URL from environment
def get_url():
    explicit = os.environ.get("DATABASE_URL", "")
    if explicit:
        return explicit
    # Use same logic as core/db.py — prefer app settings
    try:
        from config import settings
        from core.paths import get_data_dir
        if settings.postgres_url:
            url = settings.postgres_url
            # Convert async driver to sync for Alembic
            return url.replace("postgresql+asyncpg://", "postgresql://").replace("sqlite+aiosqlite://", "sqlite://")
        db_path = settings.sqlite_db_path
        return f"sqlite:///{db_path.replace(os.path.sep, '/')}"
    except Exception:
        pass
    # Hard fallback for CI/CD
    return "postgresql://drugdesigner:drugdesigner@localhost:5432/drugdesigner"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL script."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to database."""
    url = get_url()
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = url

    # SQLite doesn't support NullPool
    pool_class = pool.NullPool if "sqlite" not in url else pool.StaticPool

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool_class,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch="sqlite" in url,  # SQLite needs batch mode for ALTER TABLE
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
