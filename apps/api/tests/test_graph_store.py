"""Tests for the pluggable graph store (NetworkX embedded backend)."""

import os
import pytest
from services.graph_store import (
    NetworkXGraphStore,
    get_graph_store,
    reset_graph_store,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_graph_store()
    yield
    reset_graph_store()


@pytest.fixture
def store(tmp_store):
    return NetworkXGraphStore(os.path.join(tmp_store, "test_kg.db"))


@pytest.mark.asyncio
async def test_create_node_and_stats(store):
    await store.create_node("Gene", "BRCA1", {"name": "BRCA1", "organism": "human"})
    s = store.stats()
    assert s["backend"] == "networkx"
    assert s["total_nodes"] == 1
    assert s["node_labels"]["Gene"] == 1


@pytest.mark.asyncio
async def test_create_edge(store):
    await store.create_node("Gene", "BRCA1", {"name": "BRCA1"})
    await store.create_node("Protein", "P38398", {"name": "BRCA1_HUMAN"})
    await store.create_edge(
        "Gene", "BRCA1", "TRANSLATES_TO", "Protein", "P38398",
        {"source": "UniProt"},
    )
    s = store.stats()
    assert s["total_nodes"] == 2
    assert s["total_edges"] == 1
    assert s["edge_types"]["TRANSLATES_TO"] == 1


@pytest.mark.asyncio
async def test_edge_creates_missing_nodes(store):
    """Creating an edge auto-creates nodes that don't exist yet."""
    await store.create_edge(
        "Drug", "aspirin", "TREATS", "Disease", "headache",
    )
    s = store.stats()
    assert s["total_nodes"] == 2
    assert s["total_edges"] == 1


@pytest.mark.asyncio
async def test_neighborhood(store):
    await store.create_node("Gene", "EGFR", {})
    await store.create_node("Protein", "P00533", {})
    await store.create_node("Disease", "NSCLC", {})
    await store.create_edge("Gene", "EGFR", "TRANSLATES_TO", "Protein", "P00533")
    await store.create_edge("Protein", "P00533", "ASSOCIATED_WITH", "Disease", "NSCLC")

    result = await store.get_neighborhood("EGFR", depth=1)
    assert len(result["nodes"]) == 2  # EGFR + P00533
    assert len(result["edges"]) == 1  # EGFR->P00533

    result_deep = await store.get_neighborhood("EGFR", depth=2)
    assert len(result_deep["nodes"]) == 3  # EGFR + P00533 + NSCLC
    assert len(result_deep["edges"]) >= 2


@pytest.mark.asyncio
async def test_neighborhood_missing_node(store):
    result = await store.get_neighborhood("nonexistent")
    assert result == {"nodes": [], "edges": []}


@pytest.mark.asyncio
async def test_shortest_path(store):
    await store.create_node("Gene", "A", {})
    await store.create_node("Gene", "B", {})
    await store.create_node("Gene", "C", {})
    await store.create_edge("Gene", "A", "INTERACTS", "Gene", "B")
    await store.create_edge("Gene", "B", "INTERACTS", "Gene", "C")

    result = await store.get_shortest_path("A", "C")
    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 2
    path_ids = [n["id"] for n in result["nodes"]]
    assert path_ids == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_shortest_path_no_route(store):
    await store.create_node("Gene", "X", {})
    await store.create_node("Gene", "Y", {})
    # No edge between X and Y
    result = await store.get_shortest_path("X", "Y")
    assert result == {"nodes": [], "edges": []}


@pytest.mark.asyncio
async def test_shortest_path_missing_node(store):
    result = await store.get_shortest_path("nonexistent_a", "nonexistent_b")
    assert result == {"nodes": [], "edges": []}


@pytest.mark.asyncio
async def test_persistence(tmp_store):
    """Data survives across NetworkXGraphStore instances."""
    db_path = os.path.join(tmp_store, "persist_test.db")
    s1 = NetworkXGraphStore(db_path)
    await s1.create_node("Drug", "aspirin", {"name": "Aspirin"})
    await s1.create_node("Disease", "headache", {"name": "Headache"})
    await s1.create_edge("Drug", "aspirin", "TREATS", "Disease", "headache")

    # New instance, same db
    s2 = NetworkXGraphStore(db_path)
    stats = s2.stats()
    assert stats["total_nodes"] == 2
    assert stats["total_edges"] == 1


@pytest.mark.asyncio
async def test_sample(store):
    for i in range(10):
        await store.create_node("Gene", f"gene_{i}", {"idx": i})
    result = store.sample(limit=5)
    assert len(result["nodes"]) == 5


@pytest.mark.asyncio
async def test_factory_returns_networkx_in_embedded(tmp_store, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "dss_storage_backend", "embedded")
    store = get_graph_store()
    assert isinstance(store, NetworkXGraphStore)


@pytest.mark.asyncio
async def test_setup_constraints_noop(store):
    """setup_constraints is a no-op for NetworkX — should not raise."""
    await store.setup_constraints()


@pytest.mark.asyncio
async def test_close_noop(store):
    """close() is a no-op for NetworkX — should not raise."""
    await store.close()


@pytest.mark.asyncio
async def test_node_upsert(store):
    """Creating the same node twice updates properties."""
    await store.create_node("Gene", "TP53", {"name": "TP53"})
    await store.create_node("Gene", "TP53", {"name": "TP53", "alias": "p53"})
    s = store.stats()
    assert s["total_nodes"] == 1
