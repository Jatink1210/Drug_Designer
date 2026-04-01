"""Tests for the EvidenceStore SQLite-backed evidence cache."""

import sqlite3
import json
from datetime import datetime, timezone

from services.evidence_store import EvidenceStore


def test_setup_creates_tables(evidence_store):
    with sqlite3.connect(evidence_store._db_path) as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "entities" in tables
    assert "evidence_edges" in tables


def test_get_stats_empty(evidence_store):
    stats = evidence_store.get_stats()
    assert stats == {"entities": 0, "edges": 0}


def test_store_entity_and_stats(evidence_store):
    evidence_store.store_entity("ENT001", "Drug", "Aspirin", {"mw": 180.16})
    stats = evidence_store.get_stats()
    assert stats["entities"] == 1


def test_store_entity_upsert(evidence_store):
    evidence_store.store_entity("ENT001", "Drug", "Aspirin", {"mw": 180.16})
    evidence_store.store_entity("ENT001", "Drug", "Aspirin (updated)", {"mw": 180.16})
    stats = evidence_store.get_stats()
    assert stats["entities"] == 1


def test_store_multiple_entities(evidence_store):
    evidence_store.store_entity("E1", "Drug", "A", {})
    evidence_store.store_entity("E2", "Target", "B", {})
    evidence_store.store_entity("E3", "Disease", "C", {})
    stats = evidence_store.get_stats()
    assert stats["entities"] == 3


def test_clear_cache_empties(evidence_store):
    evidence_store.store_entity("E1", "Drug", "A", {})
    evidence_store.store_entity("E2", "Target", "B", {})
    deleted = evidence_store.clear_cache()
    assert deleted >= 2
    stats = evidence_store.get_stats()
    assert stats["entities"] == 0
    assert stats["edges"] == 0


def test_get_job_evidence_empty(evidence_store):
    result = evidence_store.get_job_evidence("nonexistent_job")
    assert result["edges"] == []
    assert result["entities"] == []


def test_get_edge_not_found(evidence_store):
    assert evidence_store.get_edge("fake_edge_id") is None


def test_get_edge_found(evidence_store):
    """Manually insert an edge and verify get_edge retrieves it."""
    with sqlite3.connect(evidence_store._db_path) as conn:
        conn.execute(
            "INSERT INTO entities (entity_id, type, name, attributes, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("src1", "Drug", "DrugA", "{}", datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            "INSERT INTO entities (entity_id, type, name, attributes, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("dst1", "Target", "TargetA", "{}", datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            """INSERT INTO evidence_edges
               (edge_id, src_entity, dst_entity, relation_type, method, source,
                source_locator, score, uncertainty, job_id, response_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("edge_001", "src1", "dst1", "binds", "assay", "chembl",
             "ChEMBL:12345", 0.9, 0.05, "job_test", "abc123", datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()

    edge = evidence_store.get_edge("edge_001")
    assert edge is not None
    assert edge["src_entity"] == "src1"
    assert edge["relation_type"] == "binds"


def test_get_job_evidence_with_data(evidence_store):
    """Insert entities and an edge, then verify get_job_evidence returns them."""
    with sqlite3.connect(evidence_store._db_path) as conn:
        conn.execute(
            "INSERT INTO entities (entity_id, type, name, attributes, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("src2", "Drug", "DrugB", "{}", datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            "INSERT INTO entities (entity_id, type, name, attributes, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("dst2", "Target", "TargetB", "{}", datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            """INSERT INTO evidence_edges
               (edge_id, src_entity, dst_entity, relation_type, method, source,
                source_locator, score, uncertainty, job_id, response_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("edge_002", "src2", "dst2", "inhibits", "docking", "pubmed",
             "PMID:999", 0.8, 0.1, "job_xyz", "def456", datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()

    result = evidence_store.get_job_evidence("job_xyz")
    assert len(result["edges"]) == 1
    assert result["edges"][0]["edge_id"] == "edge_002"
    assert len(result["entities"]) == 2
