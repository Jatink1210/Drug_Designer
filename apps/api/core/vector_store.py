"""Pluggable vector store — SQLite+numpy (embedded) or Qdrant (full).

Provides a factory ``get_vector_store()`` that returns the right backend
based on ``DSS_STORAGE_BACKEND`` / ``DSS_MODE``.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import struct
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np

log = logging.getLogger(__name__)


# ── Abstract interface ───────────────────────────────────

class VectorStore(ABC):
    @abstractmethod
    def upsert(self, collection: str, id: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        ...

    @abstractmethod
    def search(self, collection: str, vector: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def delete_collection(self, collection: str) -> None:
        ...

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def count(self, collection: str) -> int:
        ...


# ── SQLite + numpy implementation (embedded mode) ────────

def _pack_vector(vec: List[float]) -> bytes:
    """Pack float list into compact binary (little-endian float32)."""
    return struct.pack(f"<{len(vec)}f", *vec)


def _unpack_vector(data: bytes) -> np.ndarray:
    """Unpack binary back to numpy array."""
    n = len(data) // 4
    return np.array(struct.unpack(f"<{n}f", data), dtype=np.float32)


class SQLiteVectorStore(VectorStore):
    """Embedded vector store using SQLite for persistence and numpy for
    cosine similarity search.  Zero external dependencies beyond numpy."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._setup()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _setup(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vector_store (
                    collection TEXT NOT NULL,
                    id         TEXT NOT NULL,
                    vector     BLOB NOT NULL,
                    metadata   TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (collection, id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vs_collection
                ON vector_store(collection)
            """)

    def upsert(self, collection: str, id: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        blob = _pack_vector(vector)
        meta_json = json.dumps(metadata, default=str)
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO vector_store (collection, id, vector, metadata)
                   VALUES (?, ?, ?, ?)""",
                (collection, id, blob, meta_json),
            )

    def search(self, collection: str, vector: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        query_vec = np.array(vector, dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm == 0:
            return []

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, vector, metadata FROM vector_store WHERE collection = ?",
                (collection,),
            ).fetchall()

        if not rows:
            return []

        results = []
        for row_id, blob, meta_json in rows:
            stored_vec = _unpack_vector(blob)
            s_norm = np.linalg.norm(stored_vec)
            if s_norm == 0:
                continue
            score = float(np.dot(query_vec, stored_vec) / (q_norm * s_norm))
            meta = json.loads(meta_json)
            results.append({"id": row_id, "score": score, **meta})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def delete_collection(self, collection: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM vector_store WHERE collection = ?", (collection,)
            )

    def health_check(self) -> Dict[str, Any]:
        try:
            with self._conn() as conn:
                count = conn.execute("SELECT count(*) FROM vector_store").fetchone()[0]
            return {"status": "ok", "backend": "sqlite", "total_vectors": count}
        except Exception as e:
            return {"status": "error", "backend": "sqlite", "error": str(e)}

    def count(self, collection: str) -> int:
        with self._conn() as conn:
            return conn.execute(
                "SELECT count(*) FROM vector_store WHERE collection = ?",
                (collection,),
            ).fetchone()[0]


# ── Qdrant implementation (full/cloud mode) ──────────────

class QdrantVectorStore(VectorStore):
    """Thin sync wrapper around qdrant-client for full deployment."""

    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
                self._client = QdrantClient(host=self._host, port=self._port)
            except ImportError:
                raise RuntimeError("qdrant-client not installed")
        return self._client

    def upsert(self, collection: str, id: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        from qdrant_client.http import models
        client = self._get_client()
        if not client.collection_exists(collection):
            client.create_collection(
                collection_name=collection,
                vectors_config=models.VectorParams(
                    size=len(vector), distance=models.Distance.COSINE
                ),
            )
        q_id = abs(hash(id)) % (2**63 - 1)
        client.upsert(
            collection_name=collection,
            points=[models.PointStruct(id=q_id, vector=vector, payload=metadata)],
        )

    def search(self, collection: str, vector: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        client = self._get_client()
        try:
            results = client.search(
                collection_name=collection,
                query_vector=vector,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            return [{"score": r.score, **r.payload} for r in results]
        except Exception as e:
            log.error("Qdrant search error: %s", e)
            return []

    def delete_collection(self, collection: str) -> None:
        client = self._get_client()
        try:
            client.delete_collection(collection)
        except Exception as exc:
            # Suppress "collection not found" equivalents; log everything else.
            msg = str(exc).lower()
            if "not found" in msg or "doesn't exist" in msg or "status_code=404" in msg:
                log.debug("delete_collection(%s): already absent (%s)", collection, exc)
            else:
                log.warning("delete_collection(%s) failed: %s", collection, exc)
                raise

    def health_check(self) -> Dict[str, Any]:
        try:
            client = self._get_client()
            info = client.get_collections()
            return {
                "status": "ok",
                "backend": "qdrant",
                "collections": len(info.collections),
            }
        except Exception as e:
            return {"status": "error", "backend": "qdrant", "error": str(e)}

    def count(self, collection: str) -> int:
        try:
            client = self._get_client()
            info = client.get_collection(collection)
            return info.points_count or 0
        except Exception:
            return 0


# ── Factory ──────────────────────────────────────────────

_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Return the singleton vector store instance."""
    global _instance
    if _instance is not None:
        return _instance

    from config import settings

    use_embedded = (
        settings.dss_storage_backend == "embedded"
        or settings.dss_mode == "workbench"
    )

    if use_embedded:
        db_path = os.path.join(settings.local_store_path, "vector_store.db")
        _instance = SQLiteVectorStore(db_path)
        log.info("Vector store: SQLite (embedded) at %s", db_path)
    else:
        _instance = QdrantVectorStore(
            host=settings.qdrant_host, port=settings.qdrant_port
        )
        log.info("Vector store: Qdrant at %s:%s", settings.qdrant_host, settings.qdrant_port)

    return _instance


def reset_vector_store():
    """Reset singleton (for testing)."""
    global _instance
    _instance = None
