"""Tests for the pluggable vector store (SQLite embedded backend)."""

import os
import pytest
from core.vector_store import SQLiteVectorStore, get_vector_store, reset_vector_store


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure each test gets a fresh singleton."""
    reset_vector_store()
    yield
    reset_vector_store()


@pytest.fixture
def store(tmp_store):
    """Return a SQLiteVectorStore backed by tmp_path."""
    return SQLiteVectorStore(os.path.join(tmp_store, "test_vectors.db"))


def test_health_check(store):
    health = store.health_check()
    assert health["status"] == "ok"
    assert health["backend"] == "sqlite"
    assert health["total_vectors"] == 0


def test_upsert_and_count(store):
    store.upsert("molecules", "mol_1", [1.0, 0.0, 0.0], {"name": "aspirin"})
    store.upsert("molecules", "mol_2", [0.0, 1.0, 0.0], {"name": "ibuprofen"})
    assert store.count("molecules") == 2


def test_upsert_replaces(store):
    store.upsert("test", "item_1", [1.0, 0.0], {"v": 1})
    store.upsert("test", "item_1", [0.0, 1.0], {"v": 2})
    assert store.count("test") == 1
    results = store.search("test", [0.0, 1.0], limit=1)
    assert results[0]["v"] == 2


def test_search_cosine_similarity(store):
    store.upsert("coll", "a", [1.0, 0.0, 0.0], {"label": "x-axis"})
    store.upsert("coll", "b", [0.0, 1.0, 0.0], {"label": "y-axis"})
    store.upsert("coll", "c", [0.7, 0.7, 0.0], {"label": "diagonal"})

    results = store.search("coll", [1.0, 0.0, 0.0], limit=3)
    assert len(results) == 3
    # Most similar to x-axis should be "a" (score ~1.0)
    assert results[0]["id"] == "a"
    assert results[0]["score"] > 0.99
    # Diagonal should be second
    assert results[1]["id"] == "c"
    # y-axis should be last (orthogonal)
    assert results[2]["id"] == "b"
    assert results[2]["score"] < 0.01


def test_search_empty_collection(store):
    results = store.search("nonexistent", [1.0, 0.0], limit=5)
    assert results == []


def test_search_limit(store):
    for i in range(20):
        store.upsert("big", f"item_{i}", [float(i), 1.0], {"idx": i})
    results = store.search("big", [10.0, 1.0], limit=5)
    assert len(results) == 5


def test_delete_collection(store):
    store.upsert("temp", "t1", [1.0], {"x": 1})
    store.upsert("temp", "t2", [0.5], {"x": 2})
    assert store.count("temp") == 2
    store.delete_collection("temp")
    assert store.count("temp") == 0


def test_persistence(tmp_store):
    """Data survives across SQLiteVectorStore instances."""
    db_path = os.path.join(tmp_store, "persist_test.db")
    s1 = SQLiteVectorStore(db_path)
    s1.upsert("coll", "p1", [1.0, 2.0, 3.0], {"name": "test"})
    assert s1.count("coll") == 1

    s2 = SQLiteVectorStore(db_path)
    assert s2.count("coll") == 1
    results = s2.search("coll", [1.0, 2.0, 3.0], limit=1)
    assert results[0]["name"] == "test"


def test_factory_returns_sqlite_in_embedded(tmp_store, monkeypatch):
    """get_vector_store() returns SQLiteVectorStore in embedded mode."""
    from config import settings
    monkeypatch.setattr(settings, "dss_storage_backend", "embedded")
    store = get_vector_store()
    assert isinstance(store, SQLiteVectorStore)


def test_search_zero_vector(store):
    store.upsert("coll", "a", [1.0, 0.0], {"label": "a"})
    results = store.search("coll", [0.0, 0.0], limit=5)
    assert results == []


def test_metadata_preserved(store):
    meta = {"name": "test", "score": 0.95, "source": "pubmed", "pmid": "12345"}
    store.upsert("coll", "m1", [1.0, 0.0], meta)
    results = store.search("coll", [1.0, 0.0], limit=1)
    assert results[0]["name"] == "test"
    assert results[0]["source"] == "pubmed"
    assert results[0]["pmid"] == "12345"
