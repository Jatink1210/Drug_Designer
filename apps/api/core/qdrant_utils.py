"""Qdrant utility — delegates to pluggable vector store backend.

In embedded/workbench mode uses SQLite+numpy; in full mode uses Qdrant.
Public API is preserved for backward compatibility with worker.py,
routers/embeddings.py, and scripts/embed_eval.py.
"""

import logging
from typing import Any, Dict, List

from core.vector_store import get_vector_store

log = logging.getLogger(__name__)


async def get_client():
    """Return the underlying vector store (for health checks etc.)."""
    return get_vector_store()


async def upsert_entities(
    collection_name: str,
    ids: List[str],
    vectors: List[List[float]],
    payloads: List[Dict[str, Any]],
):
    """Upsert vectors with metadata into the active vector store."""
    store = get_vector_store()
    for entity_id, vec, payload in zip(ids, vectors, payloads):
        try:
            store.upsert(collection_name, entity_id, vec, payload)
        except Exception as e:
            log.error("Vector upsert failed for %s: %s", entity_id, e)


async def similarity_search(
    collection_name: str,
    query_vector: List[float],
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Search for similar vectors in the active vector store."""
    store = get_vector_store()
    try:
        return store.search(collection_name, query_vector, limit=limit)
    except Exception as e:
        log.error("Vector search error on %s: %s", collection_name, e)
        return []
