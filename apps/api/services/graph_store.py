"""Pluggable graph store — NetworkX+SQLite (embedded) or Neo4j (full).

Provides a factory ``get_graph_store()`` that returns the right backend
based on ``DSS_STORAGE_BACKEND`` / ``DSS_MODE``.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ── Abstract interface ───────────────────────────────────

class GraphStore(ABC):
    @abstractmethod
    async def create_node(
        self, label: str, node_id: str, properties: Dict[str, Any]
    ) -> None:
        ...

    @abstractmethod
    async def create_edge(
        self,
        src_label: str,
        src_id: str,
        rel_type: str,
        dst_label: str,
        dst_id: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        ...

    @abstractmethod
    async def get_neighborhood(
        self, node_id: str, depth: int = 1
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def get_shortest_path(
        self, src_id: str, dst_id: str
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def setup_constraints(self) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def sample(self, limit: int = 50) -> Dict[str, Any]:
        ...


# ── NetworkX + SQLite implementation (embedded mode) ────

class NetworkXGraphStore(GraphStore):
    """Embedded graph store using NetworkX for in-memory queries and
    SQLite for persistence.  Zero external dependencies beyond networkx."""

    def __init__(self, db_path: str):
        import networkx as nx

        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._graph = nx.DiGraph()
        self._setup_db()
        self._load_from_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _setup_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_nodes (
                    node_id    TEXT PRIMARY KEY,
                    label      TEXT NOT NULL,
                    properties TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_edges (
                    src_id     TEXT NOT NULL,
                    dst_id     TEXT NOT NULL,
                    rel_type   TEXT NOT NULL,
                    src_label  TEXT NOT NULL DEFAULT '',
                    dst_label  TEXT NOT NULL DEFAULT '',
                    properties TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (src_id, dst_id, rel_type)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_kg_edges_src ON kg_edges(src_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_kg_edges_dst ON kg_edges(dst_id)"
            )

    def _load_from_db(self):
        with self._conn() as conn:
            for row in conn.execute(
                "SELECT node_id, label, properties FROM kg_nodes"
            ).fetchall():
                node_id, label, props_json = row
                props = json.loads(props_json)
                self._graph.add_node(
                    node_id, label=label, **props
                )

            for row in conn.execute(
                "SELECT src_id, dst_id, rel_type, src_label, dst_label, properties FROM kg_edges"
            ).fetchall():
                src_id, dst_id, rel_type, src_label, dst_label, props_json = row
                props = json.loads(props_json)
                self._graph.add_edge(
                    src_id,
                    dst_id,
                    rel_type=rel_type,
                    src_label=src_label,
                    dst_label=dst_label,
                    **props,
                )

    async def create_node(
        self, label: str, node_id: str, properties: Dict[str, Any]
    ) -> None:
        self._graph.add_node(node_id, label=label, **properties)
        props_json = json.dumps(properties, default=str)
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO kg_nodes (node_id, label, properties)
                   VALUES (?, ?, ?)""",
                (node_id, label, props_json),
            )

    async def create_edge(
        self,
        src_label: str,
        src_id: str,
        rel_type: str,
        dst_label: str,
        dst_id: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        properties = properties or {}
        # Ensure source and target nodes exist in graph
        if not self._graph.has_node(src_id):
            self._graph.add_node(src_id, label=src_label)
        if not self._graph.has_node(dst_id):
            self._graph.add_node(dst_id, label=dst_label)

        self._graph.add_edge(
            src_id,
            dst_id,
            rel_type=rel_type,
            src_label=src_label,
            dst_label=dst_label,
            **properties,
        )
        props_json = json.dumps(properties, default=str)
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO kg_edges
                   (src_id, dst_id, rel_type, src_label, dst_label, properties)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (src_id, dst_id, rel_type, src_label, dst_label, props_json),
            )

    async def get_neighborhood(
        self, node_id: str, depth: int = 1
    ) -> Dict[str, Any]:
        import networkx as nx

        if node_id not in self._graph:
            return {"nodes": [], "edges": []}

        # BFS up to depth (treat as undirected for neighborhood)
        undirected = self._graph.to_undirected()
        visited = {node_id}
        frontier = {node_id}
        for _ in range(depth):
            next_frontier = set()
            for n in frontier:
                for neighbor in undirected.neighbors(n):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.add(neighbor)
            frontier = next_frontier

        # Build subgraph
        nodes_out = []
        for nid in visited:
            data = dict(self._graph.nodes[nid])
            label = data.pop("label", "Unknown")
            nodes_out.append({
                "id": nid,
                "labels": [label],
                "properties": data,
            })

        edges_out = []
        for u, v, data in self._graph.edges(data=True):
            if u in visited and v in visited:
                edge_data = dict(data)
                rel_type = edge_data.pop("rel_type", "REL")
                edge_data.pop("src_label", None)
                edge_data.pop("dst_label", None)
                edges_out.append({
                    "id": f"{u}-{rel_type}-{v}",
                    "source": u,
                    "target": v,
                    "type": rel_type,
                    "properties": edge_data,
                })

        return {"nodes": nodes_out, "edges": edges_out}

    async def get_shortest_path(
        self, src_id: str, dst_id: str
    ) -> Dict[str, Any]:
        import networkx as nx

        if src_id not in self._graph or dst_id not in self._graph:
            return {"nodes": [], "edges": []}

        undirected = self._graph.to_undirected()
        try:
            path = nx.shortest_path(undirected, src_id, dst_id)
        except nx.NetworkXNoPath:
            return {"nodes": [], "edges": []}

        path_set = set(path)
        nodes_out = []
        for nid in path:
            data = dict(self._graph.nodes[nid])
            label = data.pop("label", "Unknown")
            nodes_out.append({
                "id": nid,
                "labels": [label],
                "properties": data,
            })

        edges_out = []
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            # Check both directions in the directed graph
            if self._graph.has_edge(u, v):
                data = dict(self._graph.edges[u, v])
            elif self._graph.has_edge(v, u):
                data = dict(self._graph.edges[v, u])
                u, v = v, u
            else:
                continue
            rel_type = data.pop("rel_type", "REL")
            data.pop("src_label", None)
            data.pop("dst_label", None)
            edges_out.append({
                "id": f"{u}-{rel_type}-{v}",
                "source": u,
                "target": v,
                "type": rel_type,
                "properties": data,
            })

        return {"nodes": nodes_out, "edges": edges_out}

    async def setup_constraints(self) -> None:
        # No constraints needed for NetworkX — schema-free
        pass

    async def close(self) -> None:
        # No persistent connection to close
        pass

    def stats(self) -> Dict[str, Any]:
        # Count node labels
        label_counts: Dict[str, int] = {}
        for _, data in self._graph.nodes(data=True):
            label = data.get("label", "Unknown")
            label_counts[label] = label_counts.get(label, 0) + 1

        edge_type_counts: Dict[str, int] = {}
        for _, _, data in self._graph.edges(data=True):
            rel = data.get("rel_type", "REL")
            edge_type_counts[rel] = edge_type_counts.get(rel, 0) + 1

        return {
            "backend": "networkx",
            "total_nodes": self._graph.number_of_nodes(),
            "total_edges": self._graph.number_of_edges(),
            "node_labels": label_counts,
            "edge_types": edge_type_counts,
        }

    def sample(self, limit: int = 50) -> Dict[str, Any]:
        nodes_out = []
        count = 0
        for nid, data in self._graph.nodes(data=True):
            if count >= limit:
                break
            node_data = dict(data)
            label = node_data.pop("label", "Unknown")
            nodes_out.append({
                "id": nid,
                "labels": [label],
                "properties": node_data,
            })
            count += 1

        # Collect edges between sampled nodes
        sampled_ids = {n["id"] for n in nodes_out}
        edges_out = []
        for u, v, data in self._graph.edges(data=True):
            if u in sampled_ids and v in sampled_ids:
                edge_data = dict(data)
                rel_type = edge_data.pop("rel_type", "REL")
                edge_data.pop("src_label", None)
                edge_data.pop("dst_label", None)
                edges_out.append({
                    "id": f"{u}-{rel_type}-{v}",
                    "source": u,
                    "target": v,
                    "type": rel_type,
                    "properties": edge_data,
                })

        return {"nodes": nodes_out, "edges": edges_out}


# ── Neo4j implementation (full/cloud mode) ──────────────

class Neo4jGraphStore(GraphStore):
    """Thin async wrapper around neo4j-driver for full deployment."""

    def __init__(self, uri: str, user: str, password: str):
        self._uri = uri
        self._user = user
        self._password = password
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            try:
                from neo4j import AsyncGraphDatabase
                self._driver = AsyncGraphDatabase.driver(
                    self._uri, auth=(self._user, self._password)
                )
            except ImportError:
                raise RuntimeError("neo4j driver not installed")
        return self._driver

    async def create_node(
        self, label: str, node_id: str, properties: Dict[str, Any]
    ) -> None:
        driver = self._get_driver()
        query = f"MERGE (n:{label} {{id: $id}}) SET n += $props"
        async with driver.session() as session:
            await session.run(query, id=node_id, props=properties)

    async def create_edge(
        self,
        src_label: str,
        src_id: str,
        rel_type: str,
        dst_label: str,
        dst_id: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        properties = properties or {}
        driver = self._get_driver()
        query = f"""
        MATCH (a:{src_label} {{id: $src_id}})
        MATCH (b:{dst_label} {{id: $dst_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $props
        """
        async with driver.session() as session:
            await session.run(
                query, src_id=src_id, dst_id=dst_id, props=properties
            )

    async def get_neighborhood(
        self, node_id: str, depth: int = 1
    ) -> Dict[str, Any]:
        driver = self._get_driver()
        query = """
        MATCH path = (n {id: $id})-[*1..%d]-(m)
        UNWIND nodes(path) AS node
        UNWIND relationships(path) AS rel
        RETURN collect(DISTINCT {id: node.id, labels: labels(node), props: properties(node)}) AS nodes,
               collect(DISTINCT {id: elementId(rel), src: startNode(rel).id, dst: endNode(rel).id, type: type(rel), props: properties(rel)}) AS rels
        """ % depth
        async with driver.session() as session:
            result = await session.run(query, id=node_id)
            records = await result.data()
            return self._format_graph_output(records)

    async def get_shortest_path(
        self, src_id: str, dst_id: str
    ) -> Dict[str, Any]:
        driver = self._get_driver()
        query = """
        MATCH path = shortestPath((a {id: $src_id})-[*..6]-(b {id: $dst_id}))
        UNWIND nodes(path) AS node
        UNWIND relationships(path) AS rel
        RETURN collect(DISTINCT {id: node.id, labels: labels(node), props: properties(node)}) AS nodes,
               collect(DISTINCT {id: elementId(rel), src: startNode(rel).id, dst: endNode(rel).id, type: type(rel), props: properties(rel)}) AS rels
        """
        async with driver.session() as session:
            result = await session.run(
                query, src_id=src_id, dst_id=dst_id
            )
            records = await result.data()
            return self._format_graph_output(records)

    async def setup_constraints(self) -> None:
        driver = self._get_driver()
        queries = [
            "CREATE CONSTRAINT gene_id IF NOT EXISTS FOR (n:Gene) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT protein_id IF NOT EXISTS FOR (n:Protein) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT disease_id IF NOT EXISTS FOR (n:Disease) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT drug_id IF NOT EXISTS FOR (n:Drug) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT variant_id IF NOT EXISTS FOR (n:Variant) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT trial_id IF NOT EXISTS FOR (n:Trial) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT publication_id IF NOT EXISTS FOR (n:Publication) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT pathway_id IF NOT EXISTS FOR (n:Pathway) REQUIRE n.id IS UNIQUE",
        ]
        async with driver.session() as session:
            for q in queries:
                try:
                    await session.run(q)
                except Exception as e:
                    log.warning("Constraint setup issue: %s", e)

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    def stats(self) -> Dict[str, Any]:
        """Return connection status. Detailed counts require a live Neo4j session via async API."""
        connected = self._driver is not None
        return {
            "backend": "neo4j",
            "status": "connected" if connected else "disconnected",
            "total_nodes": None,
            "total_edges": None,
            "note": (
                "Neo4j connected. Query /api/graph for live node/edge counts."
                if connected else
                "Neo4j is not connected. Check neo4j_uri in settings or use embedded (NetworkX) mode."
            ),
        }

    def sample(self, limit: int = 50) -> Dict[str, Any]:
        """Returns empty sample when not connected (Neo4j requires async session)."""
        connected = self._driver is not None
        return {
            "nodes": [],
            "edges": [],
            "backend": "neo4j",
            "status": "connected" if connected else "disconnected",
            "note": (
                "Use /api/graph/sample endpoint for live results."
                if connected else
                "Neo4j is not connected. Sampling unavailable."
            ),
        }

    @staticmethod
    def _format_graph_output(records: List[Dict]) -> Dict[str, Any]:
        nodes_dict: Dict[str, Any] = {}
        edges_list: List[Dict[str, Any]] = []
        for r in records:
            for n in r.get("nodes", []):
                nid = str(n.get("id"))
                if nid not in nodes_dict:
                    nodes_dict[nid] = {
                        "id": nid,
                        "labels": n.get("labels", []),
                        "properties": n.get("props", {}),
                    }
            for e in r.get("rels", []):
                try:
                    edges_list.append({
                        "id": str(e.get("id")),
                        "source": str(e.get("src")),
                        "target": str(e.get("dst")),
                        "type": e.get("type", "REL"),
                        "properties": e.get("props", {}),
                    })
                except Exception:
                    continue
        return {"nodes": list(nodes_dict.values()), "edges": edges_list}


# ── Factory ──────────────────────────────────────────────

_instance: Optional[GraphStore] = None


def get_graph_store() -> GraphStore:
    """Return the singleton graph store instance."""
    global _instance
    if _instance is not None:
        return _instance

    from config import settings

    use_embedded = (
        settings.dss_storage_backend == "embedded"
        or settings.dss_mode == "workbench"
    )

    if use_embedded:
        db_path = os.path.join(settings.local_store_path, "knowledge_graph.db")
        _instance = NetworkXGraphStore(db_path)
        log.info("Graph store: NetworkX (embedded) at %s", db_path)
    else:
        _instance = Neo4jGraphStore(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        log.info("Graph store: Neo4j at %s", settings.neo4j_uri)

    return _instance


def reset_graph_store():
    """Reset singleton (for testing)."""
    global _instance
    _instance = None
