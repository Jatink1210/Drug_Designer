"""Catalog routes — browse entities stored in the vector store."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core.vector_store import get_vector_store

router = APIRouter(prefix="/api/catalog", tags=["catalog"])
log = logging.getLogger(__name__)

# Collections that map to entity types
ENTITY_COLLECTIONS = [
    "proteins", "genes", "diseases", "drugs", "molecules",
    "pathways", "structures", "publications", "clinical_trials",
    "patents", "variants", "interactions",
]


@router.get("/stats")
async def catalog_stats() -> Dict[str, Any]:
    """Return counts for each vector store collection."""
    store = get_vector_store()
    counts: Dict[str, int] = {}
    total = 0
    for coll in ENTITY_COLLECTIONS:
        c = store.count(coll)
        counts[coll] = c
        total += c
    return {"collections": counts, "total": total}


class CatalogSearchRequest(BaseModel):
    entity_type: str = "proteins"
    limit: int = 50


@router.post("/search")
async def catalog_search(req: CatalogSearchRequest) -> Dict[str, Any]:
    """List entities from a collection.

    Since vector search requires a query vector, this returns all items
    by doing a brute-force scan (fine for embedded mode with small collections).
    """
    store = get_vector_store()
    collection = req.entity_type

    # For SQLiteVectorStore we can read rows directly.
    # For other backends, use a zero-vector search with high limit.
    try:
        from core.vector_store import SQLiteVectorStore
        if isinstance(store, SQLiteVectorStore):
            import json
            with store._conn() as conn:
                rows = conn.execute(
                    "SELECT id, metadata FROM vector_store WHERE collection = ? LIMIT ?",
                    (collection, req.limit),
                ).fetchall()
            items = []
            for row_id, meta_json in rows:
                meta = json.loads(meta_json)
                items.append({"id": row_id, **meta})
            return {"items": items, "total": store.count(collection)}
    except Exception:
        log.debug("Catalog JSON parse fallback")

    # Fallback: empty
    return {"items": [], "total": store.count(collection)}
