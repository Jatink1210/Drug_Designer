"""Database Configuration and SQLAlchemy ORM bindings."""

import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from config import settings

# Determine DB URL based on settings
if settings.postgres_url:
    _url = settings.postgres_url
    if _url.startswith("postgres://"):
        _url = _url.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    # Use SQLite fallback
    db_path = settings.sqlite_db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    # Ensure Windows paths don't break the URI scheme
    _url = f"sqlite+aiosqlite:///{db_path.replace(os.path.sep, '/')}"

engine = create_async_engine(_url, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db() -> AsyncSession: # type: ignore
    """FastAPI dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """Initialize DB tables (syncs metadata to the database)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
