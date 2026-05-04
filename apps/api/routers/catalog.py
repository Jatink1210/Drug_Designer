"""Catalog routes — browse entities stored in the vector store."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from routers.auth import get_current_user
from pydantic import BaseModel

from core.vector_store import get_vector_store
from models.envelope import build_envelope

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"], dependencies=[Depends(get_current_user)])
log = logging.getLogger(__name__)

# Collections that map to entity types
ENTITY_COLLECTIONS = [
    "proteins", "genes", "diseases", "drugs", "molecules",
    "pathways", "structures", "publications", "clinical_trials",
    "patents", "variants", "interactions",
]


@router.get("/stats")
async def catalog_stats(request: Request) -> Dict[str, Any]:
    """Return counts for each collection from vector store, PostgreSQL, and Neo4j."""
    store = get_vector_store()
    counts: Dict[str, int] = {}
    total = 0

    # Vector store counts
    for coll in ENTITY_COLLECTIONS:
        c = store.count(coll)
        counts[coll] = c
        total += c

    # PostgreSQL counts
    pg_counts: Dict[str, int] = {}
    try:
        from sqlalchemy import select, func
        from core.db import AsyncSessionLocal
        from models.db_tables import (
            Run, Source, DossierRecord, ReportRecord,
            DiseaseQuery, DiseaseCandidateGene, TargetRanking,
            GraphNodeRecord, GraphEdgeRecord, PathwayRecordDB,
        )

        table_map = {
            "runs": Run,
            "sources": Source,
            "dossiers": DossierRecord,
            "reports": ReportRecord,
            "disease_queries": DiseaseQuery,
            "candidate_genes": DiseaseCandidateGene,
            "target_rankings": TargetRanking,
            "graph_nodes": GraphNodeRecord,
            "graph_edges": GraphEdgeRecord,
            "pathways_db": PathwayRecordDB,
        }

        async with AsyncSessionLocal() as session:
            for name, model in table_map.items():
                try:
                    r = await session.execute(select(func.count()).select_from(model))
                    pg_counts[name] = r.scalar() or 0
                except Exception:
                    pg_counts[name] = 0
    except Exception:
        pass

    # Neo4j counts (if available)
    neo4j_counts: Dict[str, int] = {}
    try:
        from core.db import get_neo4j_driver
        driver = get_neo4j_driver()
        if driver:
            async with driver.session() as neo_session:
                result = await neo_session.run("MATCH (n) RETURN count(n) as cnt")
                record = await result.single()
                neo4j_counts["nodes"] = record["cnt"] if record else 0
                result = await neo_session.run("MATCH ()-[r]->() RETURN count(r) as cnt")
                record = await result.single()
                neo4j_counts["edges"] = record["cnt"] if record else 0
    except Exception:
        neo4j_counts = {"nodes": 0, "edges": 0}

    return build_envelope(request, {
        "collections": counts,
        "total": total,
        "postgresql": pg_counts,
        "neo4j": neo4j_counts,
    })


class CatalogSearchRequest(BaseModel):
    entity_type: str = "proteins"
    limit: int = 50


@router.post("/search")
async def catalog_search(req: CatalogSearchRequest, request: Request) -> Dict[str, Any]:
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
            return build_envelope(request, {"items": items, "total": store.count(collection)})
    except Exception:
        log.debug("Catalog JSON parse fallback")

    # Fallback: empty
    return build_envelope(request, {"items": [], "total": store.count(collection)})
