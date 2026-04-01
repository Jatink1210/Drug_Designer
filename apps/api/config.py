"""DrugSynth Workbench — Configuration via Pydantic Settings."""

from __future__ import annotations

import os
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict
from core.paths import get_data_dir


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Workbench mode
    dss_mode: str = "studio"  # "studio" (Docker) or "workbench" (Tauri desktop)
    dss_storage_backend: str = "full"  # "full" (Qdrant+Redis) or "embedded" (SQLite only)

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_log_level: str = "info"
    api_cors_origins: List[str] = ["http://localhost:5173"]

    # LLM
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # SQLite (Local Fallback)
    sqlite_db_path: str = os.path.join(get_data_dir(), "drugsynth.db")
    
    # Postgres (Production Auth/Routing)
    postgres_url: str = "" # e.g. "postgresql+asyncpg://user:pass@localhost/db"
    
    # Auth Security
    jwt_secret: str = "changeme-for-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # File store / S3
    local_store_path: str = get_data_dir()
    s3_bucket: str = ""
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # External APIs
    ncbi_api_key: str = ""
    opentargets_api_url: str = "https://api.platform.opentargets.org/api/v4/graphql"
    chembl_api_url: str = "https://www.ebi.ac.uk/chembl/api/data"


settings = Settings()
