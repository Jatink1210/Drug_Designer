"""Service for tracking minute-by-minute execution logs and provenance."""

import sqlite3
import time
import json
import logging
import os
import re
import uuid
import hashlib
import platform
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from config import settings

log = logging.getLogger(__name__)

# Keys that must never appear in logs
_SECRET_KEYS = re.compile(
    r"(api_key|secret|token|password|credential|authorization)", re.IGNORECASE
)


def _redact(obj: Any, depth: int = 0) -> Any:
    """Recursively redact secret fields from a dict/list before logging."""
    if depth > 10:
        return obj
    if isinstance(obj, dict):
        return {
            k: "***REDACTED***" if _SECRET_KEYS.search(k) else _redact(v, depth + 1)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(v, depth + 1) for v in obj]
    if isinstance(obj, str) and _SECRET_KEYS.search(obj):
        return "***REDACTED***"
    return obj


class JobLogger:
    """Context manager for structured job logging and provenance tracking."""

    _db_path = os.path.join(settings.local_store_path, "job_logs.db")

    @classmethod
    def _jobs_dir(cls, job_id: str) -> str:
        """Return the per-job directory for JSONL logs, creating it if needed."""
        d = os.path.join(settings.local_store_path, "jobs", job_id)
        os.makedirs(d, exist_ok=True)
        return d

    @classmethod
    def setup_db(cls):
        """Initialize the SQLite database schema."""
        with sqlite3.connect(cls._db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    name TEXT,
                    status TEXT,
                    started_at TEXT,
                    duration_ms INTEGER
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS job_steps (
                    step_id TEXT PRIMARY KEY,
                    job_id TEXT,
                    name TEXT,
                    timestamp TEXT,
                    duration_ms INTEGER,
                    status TEXT,
                    details TEXT,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    job_id TEXT,
                    type TEXT,
                    title TEXT,
                    description TEXT,
                    created_at TEXT,
                    svg_path TEXT,
                    png_path TEXT,
                    json_path TEXT,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
            ''')
            conn.commit()

    def __init__(self, job_name: str, job_id: Optional[str] = None):
        if not job_id:
            job_id = f"job_{uuid.uuid4().hex[:7]}"
        self.job_id = job_id
        self.job_name = job_name
        self.started_at = datetime.now(timezone.utc).isoformat() + "Z"
        self.t0 = time.monotonic()
        self._step_counter = 0
        self._connector_calls: List[Dict[str, Any]] = []

        # Ensure DB is ready
        self.setup_db()

        # Register job
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO jobs (job_id, name, status, started_at, duration_ms) VALUES (?, ?, 'active', ?, 0)",
                (self.job_id, self.job_name, self.started_at),
            )

        # Write the first JSONL entry (job start)
        self._append_jsonl({
            "level": "info",
            "event": "job_started",
            "job_id": self.job_id,
            "name": self.job_name,
            "ts": self.started_at,
        })

    # ── JSONL file helpers ─────────────────────────────────────
    def _jsonl_path(self) -> str:
        return os.path.join(self._jobs_dir(self.job_id), "logs.jsonl")

    def _append_jsonl(self, entry: Dict[str, Any]) -> None:
        """Append a single redacted JSON line to the per-job JSONL file."""
        safe = _redact(entry)
        with open(self._jsonl_path(), "a") as f:
            f.write(json.dumps(safe, default=str) + "\n")

    # ── Step logging ───────────────────────────────────────────
    def log_step(self, step_name: str, status: str, details: Dict[str, Any], duration_ms: int = 0):
        """Append a step to the execution trace (SQLite + JSONL)."""
        self._step_counter += 1
        step_id = f"step_{uuid.uuid4().hex[:8]}"
        ts_full = datetime.now(timezone.utc).isoformat() + "Z"
        ts_short = datetime.now(timezone.utc).strftime("%H:%M:%S")

        # Provenance hash
        details_str = json.dumps(details, sort_keys=True)
        prov_hash = hashlib.sha256(details_str.encode()).hexdigest()[:11]
        details["prov_hash"] = prov_hash

        # Track connector calls for the recipe
        tool = details.get("tool_name", "")
        if tool and details.get("action_type") == "tool_call":
            self._connector_calls.append({
                "step": self._step_counter,
                "tool": tool,
                "duration_ms": duration_ms,
                "ts": ts_full,
            })

        # SQLite insert
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO job_steps (step_id, job_id, name, timestamp, duration_ms, status, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (step_id, self.job_id, step_name, ts_short, duration_ms, status, json.dumps(details)),
            )

        # JSONL append (redacted)
        self._append_jsonl({
            "level": "warning" if status == "warning" else ("error" if status == "failed" else "info"),
            "event": "step",
            "step_id": step_id,
            "step_num": self._step_counter,
            "job_id": self.job_id,
            "name": step_name,
            "status": status,
            "duration_ms": duration_ms,
            "ts": ts_full,
            "details": details,
        })

    def complete(self, status: str = "completed"):
        """Mark the job as finalized."""
        duration = int((time.monotonic() - self.t0) * 1000)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, duration_ms = ? WHERE job_id = ?",
                (status, duration, self.job_id),
            )

        # Final JSONL entry
        self._append_jsonl({
            "level": "info",
            "event": "job_finished",
            "job_id": self.job_id,
            "status": status,
            "duration_ms": duration,
            "ts": datetime.now(timezone.utc).isoformat() + "Z",
        })

        # Write run recipe alongside logs.jsonl
        self._write_recipe(status, duration)

    # ── Run recipe ──────────────────────────────────────────────
    def _write_recipe(self, status: str, duration_ms: int) -> None:
        """Write a JSON run recipe capturing everything needed to reproduce."""
        from core.paths import get_data_dir, get_data_mode

        # Load current user settings (runtime, model, compute mode)
        settings_path = os.path.join(
            os.environ.get("DSS_APP_DIR", ""),
            "user_settings.json",
        )
        user_settings: Dict[str, Any] = {}
        try:
            from core.paths import get_app_dir
            settings_path = os.path.join(get_app_dir(), "user_settings.json")
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    user_settings = json.load(f)
        except Exception:
            log.debug("Could not read user settings for recipe")

        recipe: Dict[str, Any] = {
            "schema_version": "1.0",
            "job_id": self.job_id,
            "name": self.job_name,
            "status": status,
            "started_at": self.started_at,
            "duration_ms": duration_ms,
            "steps_total": self._step_counter,
            "environment": {
                "platform": platform.system(),
                "platform_version": platform.version(),
                "python": platform.python_version(),
                "hostname": platform.node(),
            },
            "settings": _redact({
                "compute_mode": user_settings.get("compute_mode", "cpu"),
                "runtime": user_settings.get("runtime", "llama.cpp"),
                "model_id": user_settings.get("model_id", "unknown"),
                "data_mode": get_data_mode(),
                "privacy_mode": user_settings.get("privacy_mode", True),
            }),
            "connector_calls": self._connector_calls,
            "data_dir": get_data_dir(),
        }

        recipe_path = os.path.join(self._jobs_dir(self.job_id), "recipe.json")
        with open(recipe_path, "w") as f:
            json.dump(recipe, f, indent=2, default=str)

    # ── Class methods: read logs & recipe ──────────────────────
    @classmethod
    def get_job_logs(cls, job_id: str, offset: int = 0, limit: int = 200, search: str = "", tool_filter: str = "") -> Dict[str, Any]:
        """Read JSONL logs for a job with optional pagination / search / filter."""
        jsonl_path = os.path.join(cls._jobs_dir(job_id), "logs.jsonl")
        if not os.path.exists(jsonl_path):
            return {"job_id": job_id, "total": 0, "offset": offset, "limit": limit, "entries": []}

        entries: List[Dict[str, Any]] = []
        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Apply search filter (case-insensitive substring across serialized entry)
                if search and search.lower() not in json.dumps(entry).lower():
                    continue

                # Apply tool filter
                if tool_filter:
                    details = entry.get("details", {})
                    if isinstance(details, dict) and details.get("tool_name", "") != tool_filter:
                        continue

                entries.append(entry)

        total = len(entries)
        page = entries[offset : offset + limit]
        return {"job_id": job_id, "total": total, "offset": offset, "limit": limit, "entries": page}

    @classmethod
    def get_job_recipe(cls, job_id: str) -> Optional[Dict[str, Any]]:
        """Read the run recipe JSON for a job."""
        recipe_path = os.path.join(cls._jobs_dir(job_id), "recipe.json")
        if not os.path.exists(recipe_path):
            return None
        with open(recipe_path, "r") as f:
            return json.load(f)

    @classmethod
    def log_artifact(cls, artifact_id: str, job_id: str, type: str, title: str, description: str, svg_path: str, png_path: str, json_path: str):
        """Register a generated artifact."""
        created_at = datetime.now(timezone.utc).isoformat() + "Z"
        with sqlite3.connect(cls._db_path) as conn:
            conn.execute(
                "INSERT INTO artifacts (artifact_id, job_id, type, title, description, created_at, svg_path, png_path, json_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (artifact_id, job_id, type, title, description, created_at, svg_path, png_path, json_path)
            )

    # Context manager protocol
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.complete("failed")
        else:
            self.complete("completed")
            
    @classmethod
    def get_all_jobs(cls) -> List[Dict[str, Any]]:
        """Fetch all historical jobs."""
        try:
            with sqlite3.connect(cls._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute("SELECT * FROM jobs ORDER BY started_at DESC LIMIT 50")
                return [dict(row) for row in cur.fetchall()]
        except sqlite3.OperationalError:
            return []

    @classmethod
    def get_job_trace(cls, job_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full trace for a job."""
        try:
            with sqlite3.connect(cls._db_path) as conn:
                conn.row_factory = sqlite3.Row
                job_row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
                if not job_row:
                    return None
                    
                steps = conn.execute("SELECT * FROM job_steps WHERE job_id = ? ORDER BY timestamp ASC", (job_id,)).fetchall()
                
                job_data = dict(job_row)
                job_data["steps"] = [
                    {
                        "id": idx + 1,
                        "name": step["name"],
                        "timestamp": step["timestamp"],
                        "duration_ms": step["duration_ms"],
                        "status": step["status"],
                        "details": json.loads(step["details"]) if step["details"] else {}
                    }
                    for idx, step in enumerate(steps)
                ]
                return job_data
        except sqlite3.OperationalError:
            return None

    @classmethod
    def get_job_artifacts(cls, job_id: str) -> List[Dict[str, Any]]:
        """Fetch all artifacts for a job."""
        try:
            with sqlite3.connect(cls._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute("SELECT * FROM artifacts WHERE job_id = ? ORDER BY created_at ASC", (job_id,))
                return [dict(row) for row in cur.fetchall()]
        except sqlite3.OperationalError:
            return []

    @classmethod
    def get_artifact(cls, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific artifact."""
        try:
            with sqlite3.connect(cls._db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
                return dict(row) if row else None
        except sqlite3.OperationalError:
            return None
