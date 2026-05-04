"""Context Fabric Manager (§39, §21).

3-tiered scientific project memory:
  Tier 1: Session state — hot cache in PostgreSQL (< 50 ms)
  Tier 2: Artifacts — Qdrant semantic-searchable documents (< 200 ms)
  Tier 3: Heavy archive — S3/local storage for PDBs, graph snapshots
"""

import json
import time
import hashlib
import structlog
import zlib
from typing import Dict, Any, List, Optional
from pathlib import Path

from services.context_fabric.models import ContextObject, RetrievalTrace

log = structlog.get_logger(__name__)

# Local fallback storage when PG/Qdrant/S3 are unavailable
_LOCAL_STORE: Dict[str, Dict[str, Any]] = {}  # project_id → {obj_id → ContextObject}

# Memory leak prevention: LRU cache with size limits
_MEMORY_CACHE: Dict[str, Any] = {}
_CACHE_MAX_SIZE = 1000  # Maximum number of cached objects
_CACHE_ACCESS_ORDER: List[str] = []  # Track access order for LRU eviction


class ContextFabric:
    """Manages 3-tiered caching strategy (§39, §21)."""

    def __init__(self, pg_db: Any = None, qdrant_client: Any = None, s3_client: Any = None):
        self.pg = pg_db
        self.qdrant = qdrant_client
        self.s3 = s3_client
        self._local_archive = Path("data/context_archive")
        self._local_archive.mkdir(parents=True, exist_ok=True)
        self._compression_enabled = True  # Automatic context compression
        log.info("context_fabric_initialized",
                 pg=pg_db is not None,
                 qdrant=qdrant_client is not None,
                 s3=s3_client is not None)

    async def save_context(self, obj: ContextObject) -> bool:
        """Save memory object to appropriate persistence tier (§39.2)."""
        log.info("saving_context", object_id=obj.object_id, tier=obj.tier,
                 project_id=obj.project_id)

        # Apply automatic compression for large content
        original_size = 0
        compressed_size = 0
        if self._compression_enabled and isinstance(obj.content, (dict, str)):
            content_str = json.dumps(obj.content) if isinstance(obj.content, dict) else obj.content
            original_size = len(content_str)
            if original_size > 1024:  # Compress if > 1KB
                compressed = zlib.compress(content_str.encode('utf-8'))
                compressed_size = len(compressed)
                if compressed_size < original_size * 0.8:  # Only use if >20% reduction
                    obj.content = {
                        "_compressed": True,
                        "_data": compressed.hex()
                    }
                    log.info("context_compressed", 
                            original_size=original_size,
                            compressed_size=compressed_size,
                            ratio=round(original_size / compressed_size, 2))

        # Tier 3: Heavy archive (PDB files, graph snapshots)
        if obj.tier == 3:
            if self.s3 is not None:
                s3_path = f"s3://drug-designer-archive/{obj.project_id}/{obj.object_id}"
                try:
                    await self.s3.upload(obj.content, s3_path)
                    obj.content = {"s3_path": s3_path}
                except Exception as exc:
                    log.warning("s3_upload_failed", error=str(exc))
                    # Fallback: save locally
                    self._save_local_archive(obj)
            else:
                self._save_local_archive(obj)

        # Tier 1 & 2: Store metadata in PostgreSQL
        if self.pg is not None:
            try:
                from core.db import get_async_session
                from models.db_tables import ContextObjectTable
                async with get_async_session() as session:
                    row = ContextObjectTable(
                        id=obj.object_id,
                        project_id=obj.project_id,
                        tier=obj.tier,
                        object_type=obj.object_type,
                        content=json.dumps(obj.content, default=str) if not isinstance(obj.content, str) else obj.content,
                        embedding_id=obj.embedding_id,
                    )
                    session.add(row)
                    await session.commit()
            except Exception as exc:
                log.warning("pg_save_failed", error=str(exc))
                # Fallback: save to in-memory store
                self._save_in_memory(obj)
        else:
            self._save_in_memory(obj)

        # Tier 2: Index in Qdrant for semantic search
        if obj.tier == 2 and self.qdrant is not None:
            try:
                from services.embedding_service import EmbeddingService
                svc = EmbeddingService()
                content_text = json.dumps(obj.content, default=str) if not isinstance(obj.content, str) else obj.content
                embedding = svc.embed_text([content_text[:512]])
                vec = embedding[0].tolist() if hasattr(embedding[0], 'tolist') else list(embedding[0])

                from qdrant_client.models import PointStruct
                point = PointStruct(
                    id=hashlib.md5(obj.object_id.encode()).hexdigest()[:16],
                    vector=vec,
                    payload={
                        "object_id": obj.object_id,
                        "project_id": obj.project_id,
                        "object_type": obj.object_type,
                        "tier": obj.tier,
                    },
                )
                self.qdrant.upsert(
                    collection_name="context_fabric",
                    points=[point],
                )
                obj.embedding_id = point.id
                log.info("qdrant_indexed", object_id=obj.object_id)
            except Exception as exc:
                log.warning("qdrant_index_failed", error=str(exc))

        # Update LRU cache with memory leak prevention
        self._update_cache(obj.object_id, obj)

        return True

    async def retrieve(
        self, project_id: str, query: Optional[str] = None,
        tier_filter: List[int] = [1, 2], limit: int = 20,
    ) -> Dict[str, Any]:
        """Retrieve context objects with optional semantic search (§39.3).
        
        Performance targets:
        - Tier 1 (PostgreSQL): < 50ms
        - Tier 2 (Qdrant): < 200ms
        - Tier 3 (S3/local): < 500ms
        """
        log.info("context_retrieved", project=project_id, query=query, tiers=tier_filter)

        start_ms = time.monotonic()
        objects: List[Dict[str, Any]] = []

        # Check LRU cache first for fast retrieval
        cache_hits = self._check_cache(project_id, tier_filter)
        if cache_hits:
            objects.extend(cache_hits)
            log.info("cache_hit", count=len(cache_hits))

        # Semantic search via Qdrant for Tier 2
        if query and 2 in tier_filter and self.qdrant is not None:
            try:
                from services.embedding_service import EmbeddingService
                svc = EmbeddingService()
                q_embedding = svc.embed_text([query])
                q_vec = q_embedding[0].tolist() if hasattr(q_embedding[0], 'tolist') else list(q_embedding[0])

                results = self.qdrant.search(
                    collection_name="context_fabric",
                    query_vector=q_vec,
                    query_filter={"must": [{"key": "project_id", "match": {"value": project_id}}]},
                    limit=limit,
                )
                for hit in results:
                    objects.append({
                        "object_id": hit.payload.get("object_id"),
                        "score": hit.score,
                        "tier": hit.payload.get("tier"),
                        "object_type": hit.payload.get("object_type"),
                    })
            except Exception as exc:
                log.warning("qdrant_search_failed", error=str(exc))

        # PostgreSQL lookup for Tier 1 (and fallback for Tier 2)
        if self.pg is not None and len(objects) < limit:
            try:
                from core.db import get_async_session
                from sqlalchemy import select, text
                async with get_async_session() as session:
                    rows = await session.execute(
                        text("SELECT id, tier, object_type, content FROM context_objects "
                             "WHERE project_id = :pid AND tier = ANY(:tiers) LIMIT :lim"),
                        {"pid": project_id, "tiers": tier_filter, "lim": limit},
                    )
                    for row in rows:
                        content = row[3]
                        # Decompress if needed
                        if isinstance(content, str):
                            try:
                                content_dict = json.loads(content)
                                if isinstance(content_dict, dict) and content_dict.get("_compressed"):
                                    compressed_data = bytes.fromhex(content_dict["_data"])
                                    content = zlib.decompress(compressed_data).decode('utf-8')
                            except:
                                pass
                        
                        objects.append({
                            "object_id": row[0],
                            "tier": row[1],
                            "object_type": row[2],
                            "content": content,
                        })
            except Exception as exc:
                log.debug("pg_retrieve_failed", error=str(exc))

        # Fallback: in-memory store
        if not objects:
            project_data = _LOCAL_STORE.get(project_id, {})
            for obj_id, obj_data in project_data.items():
                if obj_data.get("tier") in tier_filter:
                    objects.append(obj_data)

        elapsed_ms = int((time.monotonic() - start_ms) * 1000)

        # Calculate compression ratio
        total_original = sum(len(json.dumps(o.get("content", ""))) for o in objects)
        total_compressed = total_original  # Simplified for now
        compression_ratio = total_original / max(total_compressed, 1)

        trace = RetrievalTrace(
            query=query or "null_query",
            objects_retrieved=[o.get("object_id", "?") for o in objects],
            retrieval_time_ms=elapsed_ms,
            compression_ratio=round(compression_ratio, 2),
        )

        # Verify performance SLA
        if elapsed_ms > 200:
            log.warning("retrieval_sla_violation", 
                       elapsed_ms=elapsed_ms,
                       target_ms=200,
                       project_id=project_id)

        return {
            "query_results": objects[:limit],
            "total": len(objects),
            "latency_trace": trace.model_dump(),
        }

    def _save_in_memory(self, obj: ContextObject):
        """Fallback: save to in-memory dict."""
        if obj.project_id not in _LOCAL_STORE:
            _LOCAL_STORE[obj.project_id] = {}
        _LOCAL_STORE[obj.project_id][obj.object_id] = {
            "object_id": obj.object_id,
            "tier": obj.tier,
            "object_type": obj.object_type,
            "content": obj.content,
        }

    def _save_local_archive(self, obj: ContextObject):
        """Fallback: save tier-3 heavy objects to local filesystem."""
        path = self._local_archive / obj.project_id
        path.mkdir(parents=True, exist_ok=True)
        file_path = path / f"{obj.object_id}.json"
        content = json.dumps(obj.content, default=str) if not isinstance(obj.content, str) else obj.content
        file_path.write_text(content)
        obj.content = {"local_path": str(file_path)}

    def _update_cache(self, key: str, value: Any):
        """Update LRU cache with memory leak prevention."""
        global _MEMORY_CACHE, _CACHE_ACCESS_ORDER
        
        # Remove from current position if exists
        if key in _CACHE_ACCESS_ORDER:
            _CACHE_ACCESS_ORDER.remove(key)
        
        # Add to end (most recently used)
        _CACHE_ACCESS_ORDER.append(key)
        _MEMORY_CACHE[key] = value
        
        # Evict oldest if cache is full
        if len(_MEMORY_CACHE) > _CACHE_MAX_SIZE:
            oldest_key = _CACHE_ACCESS_ORDER.pop(0)
            del _MEMORY_CACHE[oldest_key]
            log.debug("cache_eviction", evicted_key=oldest_key)

    def _check_cache(self, project_id: str, tier_filter: List[int]) -> List[Dict[str, Any]]:
        """Check LRU cache for matching objects."""
        global _MEMORY_CACHE, _CACHE_ACCESS_ORDER
        
        results = []
        for key, obj in _MEMORY_CACHE.items():
            if isinstance(obj, ContextObject):
                if obj.project_id == project_id and obj.tier in tier_filter:
                    results.append({
                        "object_id": obj.object_id,
                        "tier": obj.tier,
                        "object_type": obj.object_type,
                        "content": obj.content,
                    })
                    # Update access order
                    if key in _CACHE_ACCESS_ORDER:
                        _CACHE_ACCESS_ORDER.remove(key)
                        _CACHE_ACCESS_ORDER.append(key)
        
        return results

    def clear_cache(self):
        """Clear memory cache to prevent leaks."""
        global _MEMORY_CACHE, _CACHE_ACCESS_ORDER
        _MEMORY_CACHE.clear()
        _CACHE_ACCESS_ORDER.clear()
        log.info("cache_cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        return {
            "cache_size": len(_MEMORY_CACHE),
            "cache_max_size": _CACHE_MAX_SIZE,
            "cache_utilization": round(len(_MEMORY_CACHE) / _CACHE_MAX_SIZE * 100, 2),
        }

    # ── K-1: L3 Dossier archival ──────────────────────────────────────────

    async def archive_dossier(self, dossier_id: str, project_id: str, content: Any) -> str:
        """K-1: Archive a finalized dossier to Tier 3 (MinIO/S3 + local fallback).

        Returns the artifact reference (s3_path or local_path).
        """
        import uuid
        object_id = f"dossier_{dossier_id}_{uuid.uuid4().hex[:8]}"
        content_json = content if isinstance(content, dict) else {"raw": str(content)}
        content_json["_dossier_id"] = dossier_id
        content_json["_archived_at"] = time.time()

        obj = ContextObject(
            object_id=object_id,
            project_id=project_id,
            object_type="dossier_archive",
            tier=3,
            content=content_json,
        )
        await self.save_context(obj)
        artifact_ref = (
            obj.content.get("s3_path")
            or obj.content.get("local_path")
            or object_id
        )
        log.info("dossier_archived_l3",
                 dossier_id=dossier_id,
                 project_id=project_id,
                 artifact_ref=artifact_ref)
        return artifact_ref

    # ── K-5: Cross-project memory linkage ────────────────────────────────

    # In-memory cross-project links (persisted to Tier 1 PG when available)
    _CROSS_PROJECT_LINKS: Dict[str, List[Dict[str, Any]]] = {}

    async def link_memory_objects(
        self,
        source_project_id: str,
        source_object_id: str,
        target_project_id: str,
        target_object_id: str,
        relation: str = "related",
    ) -> Dict[str, Any]:
        """K-5: Create a cross-project memory link (bidirectional by default)."""
        link = {
            "source_project_id": source_project_id,
            "source_object_id": source_object_id,
            "target_project_id": target_project_id,
            "target_object_id": target_object_id,
            "relation": relation,
            "created_at": time.time(),
        }
        key = f"{source_project_id}:{source_object_id}"
        if key not in ContextFabric._CROSS_PROJECT_LINKS:
            ContextFabric._CROSS_PROJECT_LINKS[key] = []
        ContextFabric._CROSS_PROJECT_LINKS[key].append(link)

        # Persist to PG if available
        if self.pg is not None:
            try:
                from core.db import get_async_session
                from sqlalchemy import text
                async with get_async_session() as session:
                    await session.execute(
                        text(
                            "INSERT INTO context_memory_links "
                            "(source_project_id, source_object_id, target_project_id, target_object_id, relation, created_at) "
                            "VALUES (:spid, :soid, :tpid, :toid, :rel, NOW()) "
                            "ON CONFLICT DO NOTHING"
                        ),
                        {
                            "spid": source_project_id,
                            "soid": source_object_id,
                            "tpid": target_project_id,
                            "toid": target_object_id,
                            "rel": relation,
                        },
                    )
                    await session.commit()
            except Exception as exc:
                log.warning("cross_project_link_pg_failed", error=str(exc))

        log.info("cross_project_link_created",
                 source=f"{source_project_id}/{source_object_id}",
                 target=f"{target_project_id}/{target_object_id}",
                 relation=relation)
        return link

    async def get_cross_project_links(
        self,
        project_id: str,
        object_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """K-5: Retrieve cross-project links for a project or specific object."""
        results: List[Dict[str, Any]] = []
        for key, links in ContextFabric._CROSS_PROJECT_LINKS.items():
            for link in links:
                if link["source_project_id"] == project_id:
                    if object_id is None or link["source_object_id"] == object_id:
                        results.append(link)
                elif link["target_project_id"] == project_id:
                    if object_id is None or link["target_object_id"] == object_id:
                        results.append(link)
        return results

