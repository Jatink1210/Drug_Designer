"""Evidence storage service for online-first data caching with provenance."""

import sqlite3
import os
import uuid
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from config import settings

# §ALG — Evidence Ranking Weights
EVIDENCE_WEIGHT_RELEVANCE = 0.4
EVIDENCE_WEIGHT_RECENCY = 0.2
EVIDENCE_WEIGHT_SOURCE_QUALITY = 0.2
EVIDENCE_WEIGHT_EVIDENCE_STRENGTH = 0.2

# Source quality tiers (higher = more authoritative)
_SOURCE_QUALITY: Dict[str, float] = {
    "pubmed": 0.9, "europe_pmc": 0.85, "clinicaltrials": 0.8,
    "opentargets": 0.85, "uniprot": 0.9, "chembl": 0.85,
    "disgenet": 0.75, "gwas_catalog": 0.8, "rcsb": 0.9,
    "drugbank": 0.85, "reactome": 0.8, "kegg": 0.8,
    "string_db": 0.75, "intact": 0.75, "pubchem": 0.8,
}


def compute_evidence_score(
    relevance: float = 0.5,
    recency: float = 0.5,
    source_quality: float = 0.5,
    evidence_strength: float = 0.5,
) -> float:
    """Compute composite evidence score per spec formula.

    evidence_score = 0.4×relevance + 0.2×recency + 0.2×source_quality + 0.2×evidence_strength
    """
    return (
        EVIDENCE_WEIGHT_RELEVANCE * relevance
        + EVIDENCE_WEIGHT_RECENCY * recency
        + EVIDENCE_WEIGHT_SOURCE_QUALITY * source_quality
        + EVIDENCE_WEIGHT_EVIDENCE_STRENGTH * evidence_strength
    )


def get_source_quality(source_name: str) -> float:
    """Return quality tier for a given source (0-1)."""
    return _SOURCE_QUALITY.get(source_name.lower(), 0.5)

class EvidenceStore:
    """Manages cached entities, evidence edges, and connector caching policies."""
    
    _db_path = os.path.join(settings.local_store_path, "evidence_cache.db")
    
    @classmethod
    def setup_db(cls):
        """Initialize the single-source-of-truth evidence database."""
        with sqlite3.connect(cls._db_path) as conn:
            # Polymorphic entity table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    type TEXT,
                    name TEXT,
                    attributes TEXT,
                    updated_at TEXT
                )
            ''')
            # Canonical evidence edge table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS evidence_edges (
                    edge_id TEXT PRIMARY KEY,
                    src_entity TEXT,
                    dst_entity TEXT,
                    relation_type TEXT,
                    method TEXT,
                    source TEXT,
                    source_locator TEXT,
                    score REAL,
                    uncertainty REAL,
                    job_id TEXT,
                    response_hash TEXT,
                    created_at TEXT,
                    FOREIGN KEY(src_entity) REFERENCES entities(entity_id),
                    FOREIGN KEY(dst_entity) REFERENCES entities(entity_id)
                )
            ''')
            conn.commit()

    @classmethod
    def clear_cache(cls) -> int:
        """Wipes the entire evidence cache."""
        cls.setup_db()
        with sqlite3.connect(cls._db_path) as conn:
            cur = conn.execute("DELETE FROM evidence_edges")
            edges_deleted = cur.rowcount
            cur = conn.execute("DELETE FROM entities")
            entities_deleted = cur.rowcount
            conn.commit()
            return edges_deleted + entities_deleted

    @classmethod
    def get_stats(cls) -> Dict[str, int]:
        """Get row counts for testing."""
        cls.setup_db()
        with sqlite3.connect(cls._db_path) as conn:
            ent = conn.execute("SELECT count(*) FROM entities").fetchone()[0]
            edg = conn.execute("SELECT count(*) FROM evidence_edges").fetchone()[0]
            return {"entities": ent, "edges": edg}

    @classmethod
    def store_entity(cls, entity_id: str, ent_type: str, name: str, attributes: Dict[str, Any]):
        """Upsert a canonical entity."""
        cls.setup_db()
        with sqlite3.connect(cls._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO entities (entity_id, type, name, attributes, updated_at) VALUES (?, ?, ?, ?, ?)",
                (entity_id, ent_type, name, json.dumps(attributes), datetime.now(timezone.utc).isoformat())
            )

    @classmethod
    async def fetch_online_async(cls, connector_cls, query: str, job_id: str, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """Online evidence caching proxy. Contacts the connector, stores discovered entities and edges."""
        cls.setup_db()
        connector = connector_cls()
        
        t0 = time.monotonic()
        try:
            results = await connector.search(query, limit=limit, **kwargs)
        except Exception as e:
            await connector.close()
            raise e
            
        await connector.close()
        duration_ms = int((time.monotonic() - t0) * 1000)
        
        # Persist the findings
        with sqlite3.connect(cls._db_path) as conn:
            for item in results:
                # 1. Deduce a primary entity ID based on the source
                source_name = getattr(connector, "name", "unknown")
                
                # Connector-specific entity extraction schema
                if source_name == "pubmed":
                    entity_id = f"PMID:{item.get('pmid')}"
                    ent_type = "Publication"
                    name = item.get("title", "Unknown Title")
                    src_locator = f"PMID:{item.get('pmid')}#snippet_offset_0" 
                elif source_name == "clinicaltrials":
                    entity_id = f"NCT:{item.get('nct_id', item.get('id', uuid.uuid4().hex[:8]))}"
                    ent_type = "ClinicalStudy"
                    name = item.get("title", "Unknown Trial")
                    src_locator = f"{entity_id}#summary"
                else:
                    entity_id = f"{source_name}:{uuid.uuid4().hex[:8]}"
                    ent_type = "Document"
                    name = item.get("title") or item.get("name") or "Unknown"
                    src_locator = f"{entity_id}#page=1"
                
                # Store Entity
                conn.execute(
                    "INSERT OR IGNORE INTO entities (entity_id, type, name, attributes, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (entity_id, ent_type, name, json.dumps(item), datetime.now(timezone.utc).isoformat())
                )
                
                # Store Edge linking the Job's Query to the Entity
                edge_id = f"edge_{uuid.uuid4().hex[:12]}"
                target_id = f"Query:{hash(query)}"
                
                # Query anchor entity for edge linking
                conn.execute(
                    "INSERT OR IGNORE INTO entities (entity_id, type, name, attributes, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (target_id, "Query", query, "{}", datetime.now(timezone.utc).isoformat())
                )
                
                conn.execute(
                    '''INSERT INTO evidence_edges 
                       (edge_id, src_entity, dst_entity, relation_type, method, source, source_locator, 
                        score, uncertainty, job_id, response_hash, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (edge_id, entity_id, target_id, "mentions", "connector_search", source_name, 
                     src_locator, 1.0, 0.0, job_id, hash(json.dumps(item)), datetime.now(timezone.utc).isoformat())
                )
            
            conn.commit()
            
        return results

    @classmethod
    def get_job_evidence(cls, job_id: str) -> Dict[str, Any]:
        """Fetch all evidence stored for a given job."""
        cls.setup_db()
        with sqlite3.connect(cls._db_path) as conn:
            conn.row_factory = sqlite3.Row
            edges = conn.execute("SELECT * FROM evidence_edges WHERE job_id = ?", (job_id,)).fetchall()
            
            # Fetch entities
            entity_ids = set()
            for e in edges:
                entity_ids.add(e["src_entity"])
                entity_ids.add(e["dst_entity"])
                
            entities = []
            if entity_ids:
                # Safe: build placeholder string from count only (no user data in SQL text)
                id_list = list(entity_ids)
                params = ",".join(["?"] * len(id_list))
                entities = conn.execute(
                    "SELECT * FROM entities WHERE entity_id IN (" + params + ")",
                    id_list,
                ).fetchall()
                
            return {
                "edges": [dict(e) for e in edges],
                "entities": [dict(ent) for ent in entities]
            }

    @classmethod
    def get_edge(cls, edge_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific edge with full provenance."""
        cls.setup_db()
        with sqlite3.connect(cls._db_path) as conn:
            conn.row_factory = sqlite3.Row
            edge = conn.execute("SELECT * FROM evidence_edges WHERE edge_id = ?", (edge_id,)).fetchone()
            return dict(edge) if edge else None
