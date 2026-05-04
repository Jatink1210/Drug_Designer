"""Two-tier cache: in-memory LRU + persistent SQLite with TTL and ETag support."""

from __future__ import annotations

import asyncio
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
    """Deterministic cache key: cache:{source}:{sha256(params)} per §69."""
    raw = "%s:%s:%s" % (source, query, extra)
    digest = hashlib.sha256(raw.lower().strip().encode()).hexdigest()
    return f"cache:{source}:{digest}"

# §69 TTL tiers
CACHE_TTL_HTTP = 300        # 5 minutes
CACHE_TTL_CONNECTOR = 1800  # 30 minutes
CACHE_TTL_EMBEDDING = 86400 # 24 hours
CACHE_TTL_GRAPH = 900       # 15 minutes


class RedisCache:
    """Redis-backed application cache tier (§69).

    Sits between L1 (in-memory LRU) and L2 (SQLite disk).
    Falls back gracefully if Redis is unavailable.
    """

    def __init__(self, redis_url: str = None):
        self._redis_url = redis_url
        self._client = None
        self._available = False
        self._init_attempted = False

    def _get_client(self):
        if self._init_attempted:
            return self._client
        self._init_attempted = True
        try:
            import redis
            url = self._redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/1")
            self._client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
            self._client.ping()
            self._available = True
            log.info("redis_cache_connected", url=url)
        except Exception as e:
            log.info("redis_cache_unavailable", error=str(e))
            self._client = None
            self._available = False
        return self._client

    def get(self, key: str) -> Optional[Any]:
        client = self._get_client()
        if not client:
            return None
        try:
            raw = client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def put(self, key: str, data: Any, ttl: float = CACHE_TTL_CONNECTOR) -> None:
        client = self._get_client()
        if not client:
            return
        try:
            client.setex(key, int(ttl), json.dumps(data, default=str))
        except Exception:
            pass

    def clear(self) -> None:
        client = self._get_client()
        if client:
            try:
                client.flushdb()
            except Exception:
                pass

    @property
    def available(self) -> bool:
        self._get_client()
        return self._available


# ── Singletons ────────────────────────────────────────────
_memory_cache: Optional[LRUCache] = None
_disk_cache: Optional[SQLiteCache] = None
_redis_cache: Optional[RedisCache] = None


def get_memory_cache() -> LRUCache:
    global _memory_cache
    if _memory_cache is None:
        _memory_cache = LRUCache()
    return _memory_cache


def get_redis_cache() -> RedisCache:
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
    return _redis_cache


def get_disk_cache() -> SQLiteCache:
    global _disk_cache
    if _disk_cache is None:
        _disk_cache = SQLiteCache()
    return _disk_cache


def two_tier_get(key: str) -> Optional[Any]:
    """Check memory → Redis → disk (§69 three-tier cache)."""
    mem = get_memory_cache()
    result = mem.get(key)
    if result is not None:
        return result
    # L2: Redis
    redis_c = get_redis_cache()
    result = redis_c.get(key)
    if result is not None:
        mem.put(key, result, ttl=300.0)
        return result
    # L3: Disk
    disk = get_disk_cache()
    disk_result = disk.get(key)
    if disk_result is not None:
        data, _ = disk_result
        mem.put(key, data, ttl=300.0)
        redis_c.put(key, data, ttl=CACHE_TTL_CONNECTOR)
        return data
    return None


def two_tier_put(
    key: str, source: str, url: str, data: Any,
    etag: str = "", ttl: float = DEFAULT_TTL, payload_hash: str = "",
) -> None:
    """Write to all three tiers: memory + Redis + disk."""
    get_memory_cache().put(key, data, ttl=min(ttl, 600.0))
    get_redis_cache().put(key, data, ttl=ttl)
    get_disk_cache().put(key, source, url, data, etag=etag, ttl=ttl, payload_hash=payload_hash)


# ── Async wrappers (safe for event loop) ────────────────
async def async_two_tier_get(key: str) -> Optional[Any]:
    """Non-blocking three-tier get: memory → Redis → SQLite."""
    mem = get_memory_cache()
    result = mem.get(key)
    if result is not None:
        return result
    # Redis (sync but fast)
    redis_c = get_redis_cache()
    result = redis_c.get(key)
    if result is not None:
        mem.put(key, result, ttl=300.0)
        return result
    # Disk
    disk_result = await asyncio.to_thread(get_disk_cache().get, key)
    if disk_result is not None:
        data, _ = disk_result
        mem.put(key, data, ttl=300.0)
        redis_c.put(key, data, ttl=CACHE_TTL_CONNECTOR)
        return data
    return None


async def async_two_tier_put(
    key: str, source: str, url: str, data: Any,
    etag: str = "", ttl: float = DEFAULT_TTL, payload_hash: str = "",
) -> None:
    """Non-blocking three-tier put."""
    get_memory_cache().put(key, data, ttl=min(ttl, 600.0))
    get_redis_cache().put(key, data, ttl=ttl)
    await asyncio.to_thread(
        get_disk_cache().put, key, source, url, data,
        etag, ttl, payload_hash,
    )
