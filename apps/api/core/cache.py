"""Two-tier cache: in-memory LRU + persistent SQLite with TTL and ETag support."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import threading
from collections import OrderedDict
from typing import Any, Optional, Tuple

import structlog

from config import settings

log = structlog.get_logger()

DEFAULT_TTL = 86400  # 24 hours
MAX_MEMORY_ITEMS = 2000


class LRUCache:
    """Thread-safe in-memory LRU cache."""

    def __init__(self, max_size: int = MAX_MEMORY_ITEMS):
        self._max = max_size
        self._store: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._store:
                return None
            val, expires = self._store[key]
            if time.time() > expires:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return val

    def put(self, key: str, value: Any, ttl: float = 300.0) -> None:
        with self._lock:
            self._store[key] = (value, time.time() + ttl)
            self._store.move_to_end(key)
            while len(self._store) > self._max:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    @property
    def _cache(self) -> OrderedDict:
        return self._store

    @property
    def _max_size(self) -> int:
        return self._max


class SQLiteCache:
    """Persistent HTTP response cache with TTL + ETag."""

    def __init__(self, db_path: Optional[str] = None):
        from core.paths import get_cache_dir
        self._db_path = db_path or os.path.join(
            get_cache_dir(), "http_cache.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS http_cache (
                cache_key TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                response_json TEXT NOT NULL,
                etag TEXT DEFAULT '',
                created_at REAL NOT NULL,
                ttl REAL NOT NULL DEFAULT 86400,
                payload_hash TEXT DEFAULT ''
            )
        """)
        self._conn.commit()

    def get(self, key: str) -> Optional[Tuple[Any, str]]:
        """Returns (data, etag) or None if expired/missing."""
        row = self._conn.execute(
            "SELECT response_json, etag, created_at, ttl FROM http_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if not row:
            return None
        data_json, etag, created_at, ttl = row
        if time.time() - created_at > ttl:
            self._conn.execute("DELETE FROM http_cache WHERE cache_key = ?", (key,))
            self._conn.commit()
            return None
        try:
            return json.loads(data_json), etag or ""
        except Exception:
            return None

    def put(
        self,
        key: str,
        source: str,
        url: str,
        data: Any,
        etag: str = "",
        ttl: float = DEFAULT_TTL,
        payload_hash: str = "",
    ) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO http_cache
               (cache_key, source, url, response_json, etag, created_at, ttl, payload_hash)
               VALUES (?,?,?,?,?,?,?,?)""",
            (key, source, url, json.dumps(data, default=str), etag, time.time(), ttl, payload_hash),
        )
        self._conn.commit()

    def stats(self) -> dict:
        row = self._conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()
        return {"total_entries": row[0] if row else 0, "db_path": self._db_path}

    def clear(self) -> None:
        self._conn.execute("DELETE FROM http_cache")
        self._conn.commit()


def cache_key(source: str, query: str, extra: str = "") -> str:
    """Deterministic cache key from source + query + extra context."""
    raw = "%s:%s:%s" % (source, query, extra)
    return hashlib.sha256(raw.lower().strip().encode()).hexdigest()


# ── Singletons ────────────────────────────────────────────
_memory_cache: Optional[LRUCache] = None
_disk_cache: Optional[SQLiteCache] = None


def get_memory_cache() -> LRUCache:
    global _memory_cache
    if _memory_cache is None:
        _memory_cache = LRUCache()
    return _memory_cache


def get_disk_cache() -> SQLiteCache:
    global _disk_cache
    if _disk_cache is None:
        _disk_cache = SQLiteCache()
    return _disk_cache


def two_tier_get(key: str) -> Optional[Any]:
    """Check memory first, then disk."""
    mem = get_memory_cache()
    result = mem.get(key)
    if result is not None:
        return result
    disk = get_disk_cache()
    disk_result = disk.get(key)
    if disk_result is not None:
        data, _ = disk_result
        mem.put(key, data, ttl=300.0)  # promote to memory
        return data
    return None


def two_tier_put(
    key: str, source: str, url: str, data: Any,
    etag: str = "", ttl: float = DEFAULT_TTL, payload_hash: str = "",
) -> None:
    """Write to both memory and disk."""
    get_memory_cache().put(key, data, ttl=min(ttl, 600.0))
    get_disk_cache().put(key, source, url, data, etag=etag, ttl=ttl, payload_hash=payload_hash)
