"""Drug Designer Platform — Configuration via Pydantic Settings."""

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
    llm_runtime_mode: str = "hosted"  # hosted | local | auto
    llm_remote_base_url: str = "https://api.openai.com/v1"
    llm_enable_ollama: bool = False
    airllm_enabled: bool = False
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma4:26b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    spacy_model_name: str = "en_core_sci_sm"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # SQLite (Local Fallback)
    sqlite_db_path: str = os.path.join(get_data_dir(), "drugsynth.db")
    
    # Postgres (Production Auth/Routing)
    postgres_url: str = "" # e.g. "postgresql+asyncpg://user:pass@localhost/db"
    
    # Auth Security (§55.1)
    jwt_secret: str = ""  # REQUIRED — set via JWT_SECRET env var
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15  # §55.1: Access Token 15 min TTL
    refresh_token_expire_days: int = 7  # §55.1: Refresh Token 7 day TTL

    # File store / S3
    local_store_path: str = get_data_dir()
    s3_bucket: str = ""
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""  # Set via NEO4J_PASSWORD env var

    # Model weights cache
    model_cache_dir: str = ""  # Override via MODEL_CACHE_DIR env var; defaults to data/models/

    # Indian population genomics boost (§83.5)
    india_population_weight: float = 0.15  # Multiplier on variant signal when Indian-population-relevant

    # Encryption (§61.1)
    encryption_key: str = ""  # 32-byte Fernet key, set via ENCRYPTION_KEY env var

    # External APIs
    ncbi_api_key: str = ""
    disgenet_api_key: str = ""  # Set via DISGENET_API_KEY env var
    opentargets_api_url: str = "https://api.platform.opentargets.org/api/v4/graphql"
    chembl_api_url: str = "https://www.ebi.ac.uk/chembl/api/data"

    # EvolutionaryScale ESM Forge API (ESM-3 Large — De Novo Protein Design §24.2)
    esm_forge_api_key: str = ""  # Set via ESM_FORGE_API_KEY env var
    # Model name: esm3-large-2024-08
    # Endpoint: https://forge.evolutionaryscale.ai

    # Observability (§60.4, §96)
    sentry_dsn: str = ""  # Set via SENTRY_DSN env var
    prometheus_enabled: bool = True


settings = Settings()
