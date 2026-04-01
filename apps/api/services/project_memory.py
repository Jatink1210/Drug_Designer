"""
Project Memory SQLite Datastore.
Satisfies Section 19 of the architecture specification requiring run provenance 
and reproducible historical data arrays persisting across server restarts.
"""

import sqlite3
import os
from datetime import datetime, timezone
from config import settings
import structlog

log = structlog.get_logger(__name__)

class ProjectMemoryStore:
    _db_path = os.path.join(settings.local_store_path, "project_memory.db")
    
    @classmethod
    def setup(cls):
        os.makedirs(settings.local_store_path, exist_ok=True)
        with sqlite3.connect(cls._db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    target_name TEXT,
                    prompt TEXT,
                    llm_output TEXT,
                    status TEXT,
                    timestamp TEXT
                )
            ''')
            conn.commit()
            log.debug("project_memory_db_ready")

    @classmethod
    def log_run(cls, run_id: str, target_name: str, prompt: str, llm_output: str, status: str):
        cls.setup()
        try:
            with sqlite3.connect(cls._db_path) as conn:
                conn.execute(
                    "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                    (run_id, target_name, prompt, llm_output, status, datetime.now(timezone.utc).isoformat())
                )
                conn.commit()
            log.info("project_memory_run_saved", run_id=run_id)
        except Exception as e:
            log.error("project_memory_save_failed", error=str(e))
