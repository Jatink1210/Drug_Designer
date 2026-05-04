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

    async def embed_subgraph(
        self, node_ids: List[str], depth: int = 2
    ) -> Dict[str, Any]:
        """Return R-GCN 512-d embeddings keyed by node_id.

        Retrieves the depth-hop neighbourhood of all *node_ids*, converts it
        to a COO edge_index tensor, runs it through the singleton RGCNModel,
        and returns a dict ``{node_id: embedding_list}`` where each embedding
        is a Python list of 512 floats.

        If torch/transformers are unavailable the method falls back to
        returning random unit-vectors so callers always receive a response.
        """
        # Collect neighbourhood across all seed nodes
        all_nodes: Dict[str, Any] = {}
        all_edges: List[Dict[str, Any]] = []
        for nid in node_ids:
            result = await self.get_neighborhood(nid, depth=depth)
            for n in result.get("nodes", []):
                all_nodes[n["id"]] = n
            all_edges.extend(result.get("edges", []))

        if not all_nodes:
            return {}

        # Build integer index
        node_list = list(all_nodes.keys())
        node_idx = {n: i for i, n in enumerate(node_list)}
        n_nodes = len(node_list)

        try:
            import torch
            from services.ml.rgcn_model import RGCNModel

            # Build relationship-type index
            rel_types: Dict[str, int] = {}
            src_list, dst_list, etype_list = [], [], []
            for edge in all_edges:
                s = edge.get("source", "")
                t = edge.get("target", "")
                r = edge.get("type", "REL")
                if s in node_idx and t in node_idx:
                    if r not in rel_types:
                        rel_types[r] = len(rel_types)
                    src_list.append(node_idx[s])
                    dst_list.append(node_idx[t])
                    etype_list.append(rel_types[r])

            n_rels = max(len(rel_types), 1)
            if src_list:
                edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)
                edge_type = torch.tensor(etype_list, dtype=torch.long)
            else:
                edge_index = torch.zeros((2, 0), dtype=torch.long)
                edge_type = torch.zeros(0, dtype=torch.long)

            model = RGCNModel(num_nodes=n_nodes, num_relations=n_rels)
            embeddings_tensor = model.embed_nodes(edge_index, edge_type, n_nodes)
            result_dict: Dict[str, Any] = {}
            for i, nid in enumerate(node_list):
                result_dict[nid] = embeddings_tensor[i].tolist()
            return result_dict

        except Exception:
            import random, math
            out: Dict[str, Any] = {}
            for nid in node_list:
                vec = [random.gauss(0, 1) for _ in range(512)]
                norm = math.sqrt(sum(x * x for x in vec)) or 1.0
                out[nid] = [x / norm for x in vec]
            return out


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
        # Auto-seed from disease data if KG is empty
        if self._graph.number_of_nodes() == 0:
            self._seed_from_disease_data()

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

    def _seed_from_disease_data(self):
        """Auto-populate KG from disease data in drugsynth.db when empty."""
        try:
            from config import settings
            main_db = settings.sqlite_db_path
            if not os.path.exists(main_db):
                return
            conn = sqlite3.connect(main_db)
            conn.row_factory = sqlite3.Row

            # 1. Build disease nodes from disease_queries
            diseases = conn.execute(
                "SELECT DISTINCT normalized_label FROM disease_queries WHERE normalized_label IS NOT NULL AND normalized_label != ''"
            ).fetchall()
            disease_set = set()
            for d in diseases:
                name = d["normalized_label"]
                nid = f"disease:{name.lower().replace(' ', '_')}"
                disease_set.add(nid)
                self._graph.add_node(nid, label="Disease", name=name)

            # 2. Build gene nodes from disease_candidate_genes (top scoring per disease)
            gene_rows = conn.execute("""
                SELECT dcg.gene_symbol, dcg.score, dcg.source_count,
                       dq.normalized_label as disease_name
                FROM disease_candidate_genes dcg
                JOIN disease_queries dq ON dcg.disease_query_id = dq.id
                WHERE dcg.gene_symbol IS NOT NULL AND dcg.gene_symbol != ''
                ORDER BY dcg.score DESC
                LIMIT 2000
            """).fetchall()

            gene_disease_pairs = set()
            for row in gene_rows:
                gene = row["gene_symbol"]
                gene_nid = f"gene:{gene}"
                disease_name = row["disease_name"]
                disease_nid = f"disease:{disease_name.lower().replace(' ', '_')}"

                if not self._graph.has_node(gene_nid):
                    self._graph.add_node(gene_nid, label="Gene", name=gene,
                                         score=row["score"],
                                         source_count=row["source_count"])

                pair = (disease_nid, gene_nid)
                if pair not in gene_disease_pairs and disease_nid in disease_set:
                    gene_disease_pairs.add(pair)
                    self._graph.add_edge(disease_nid, gene_nid,
                                         rel_type="ASSOCIATED_GENE",
                                         src_label="Disease",
                                         dst_label="Gene",
                                         score=row["score"])

            # 3. Build protein nodes from uniprot_mappings
            protein_rows = conn.execute("""
                SELECT um.gene_symbol, um.uniprot_id, um.mapping_confidence
                FROM uniprot_mappings um
                WHERE um.uniprot_id IS NOT NULL AND um.uniprot_id != ''
                  AND um.gene_symbol IN (
                    SELECT DISTINCT gene_symbol FROM disease_candidate_genes
                    ORDER BY score DESC LIMIT 2000
                  )
                LIMIT 2000
            """).fetchall()

            for row in protein_rows:
                gene = row["gene_symbol"]
                uniprot = row["uniprot_id"]
                gene_nid = f"gene:{gene}"
                prot_nid = f"protein:{uniprot}"

                if not self._graph.has_node(prot_nid):
                    self._graph.add_node(prot_nid, label="Protein",
                                         name=uniprot, uniprot_id=uniprot)
                if self._graph.has_node(gene_nid):
                    self._graph.add_edge(gene_nid, prot_nid,
                                         rel_type="ENCODES",
                                         src_label="Gene",
                                         dst_label="Protein",
                                         confidence=row["mapping_confidence"])

            # 4. Build target ranking nodes and edges
            target_rows = conn.execute("""
                SELECT tr.gene_symbol, tr.rank, tr.composite_score,
                       tr.druggability_score, tr.gwas_score, tr.safety_score,
                       tr.novelty_score, tr.literature_score
                FROM target_rankings tr
                WHERE tr.gene_symbol IS NOT NULL
                ORDER BY tr.composite_score DESC
            """).fetchall()

            for row in target_rows:
                gene = row["gene_symbol"]
                gene_nid = f"gene:{gene}"
                target_nid = f"target:{gene}"

                if not self._graph.has_node(target_nid):
                    self._graph.add_node(target_nid, label="Target",
                                         name=gene,
                                         rank=row["rank"],
                                         composite_score=row["composite_score"],
                                         druggability=row["druggability_score"],
                                         safety=row["safety_score"])
                if self._graph.has_node(gene_nid):
                    self._graph.add_edge(gene_nid, target_nid,
                                         rel_type="RANKED_TARGET",
                                         src_label="Gene",
                                         dst_label="Target",
                                         rank=row["rank"],
                                         score=row["composite_score"])

            # 5. Add gene-gene interaction edges for top genes
            # Connect genes associated with the same disease
            from collections import defaultdict
            disease_genes: dict = defaultdict(list)
            for d_nid, g_nid in gene_disease_pairs:
                disease_genes[d_nid].append(g_nid)

            for d_nid, genes in disease_genes.items():
                top_genes = genes[:30]  # top 30 per disease for edges
                for i in range(len(top_genes)):
                    for j in range(i + 1, min(i + 5, len(top_genes))):
                        self._graph.add_edge(top_genes[i], top_genes[j],
                                             rel_type="CO_ASSOCIATED",
                                             src_label="Gene",
                                             dst_label="Gene",
                                             context=d_nid)

            # 6. Build source nodes
            source_rows = conn.execute("""
                SELECT DISTINCT source_name FROM disease_source_hits
                WHERE source_name IS NOT NULL AND source_name != ''
            """).fetchall()

            for row in source_rows:
                src = row["source_name"]
                src_nid = f"source:{src.lower().replace(' ', '_')}"
                if not self._graph.has_node(src_nid):
                    self._graph.add_node(src_nid, label="Source", name=src)

            conn.close()

            # Persist to KG database
            self._persist_graph()
            log.info("KG seeded from disease data: %d nodes, %d edges",
                     self._graph.number_of_nodes(), self._graph.number_of_edges())

        except Exception as e:
            log.warning("Failed to seed KG from disease data: %s", str(e))

    def _persist_graph(self):
        """Persist in-memory graph to kg_nodes and kg_edges tables."""
        with self._conn() as conn:
            for nid, data in self._graph.nodes(data=True):
                node_data = dict(data)
                label = node_data.pop("label", "Unknown")
                props_json = json.dumps(node_data, default=str)
                conn.execute(
                    "INSERT OR REPLACE INTO kg_nodes (node_id, label, properties) VALUES (?, ?, ?)",
                    (nid, label, props_json),
                )
            for u, v, data in self._graph.edges(data=True):
                edge_data = dict(data)
                rel_type = edge_data.pop("rel_type", "REL")
                src_label = edge_data.pop("src_label", "")
                dst_label = edge_data.pop("dst_label", "")
                props_json = json.dumps(edge_data, default=str)
                conn.execute(
                    "INSERT OR REPLACE INTO kg_edges (src_id, dst_id, rel_type, src_label, dst_label, properties) VALUES (?, ?, ?, ?, ?, ?)",
                    (u, v, rel_type, src_label, dst_label, props_json),
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
                "label": label,
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
                "label": label,
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

        # Evidence count and entity counts from DB
        evidence_count = 0
        entity_counts = {}
        try:
            import sqlite3
            from config import settings
            conn = sqlite3.connect(settings.sqlite_db_path)
            for tbl, key in [
                ("evidence_items", "evidence_count"),
                ("disease_candidate_genes", "candidate_genes"),
                ("target_rankings", "target_rankings"),
                ("dossiers", "dossiers"),
                ("runs", "runs"),
                ("disease_queries", "disease_queries"),
            ]:
                try:
                    val = conn.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
                    entity_counts[key] = val
                except Exception:
                    pass
            evidence_count = entity_counts.get("evidence_count", 0)
            conn.close()
        except Exception:
            pass

        return {
            "backend": "networkx",
            "total_nodes": self._graph.number_of_nodes(),
            "total_edges": self._graph.number_of_edges(),
            "nodes": label_counts,
            "edges": edge_type_counts,
            "node_labels": label_counts,
            "edge_types": edge_type_counts,
            "evidence_count": evidence_count,
            **entity_counts,
        }

    def sample(self, limit: int = 50) -> Dict[str, Any]:
        """Return a connected subgraph sample via BFS from seed nodes."""
        import random

        if self._graph.number_of_nodes() == 0:
            return {"nodes": [], "edges": []}

        # Pick diverse seed nodes (one per label type)
        label_groups: Dict[str, List[str]] = {}
        for nid, data in self._graph.nodes(data=True):
            lbl = data.get("label", "Unknown")
            label_groups.setdefault(lbl, []).append(nid)

        seeds: List[str] = []
        for lbl, nids in label_groups.items():
            pick = min(3, len(nids))
            seeds.extend(random.sample(nids, pick))

        # BFS from seeds to collect connected nodes up to limit
        visited: set = set()
        frontier = list(seeds)
        random.shuffle(frontier)
        undirected = self._graph.to_undirected()

        while frontier and len(visited) < limit:
            nid = frontier.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            if len(visited) >= limit:
                break
            for neighbor in undirected.neighbors(nid):
                if neighbor not in visited:
                    frontier.append(neighbor)

        # Build output
        nodes_out = []
        for nid in visited:
            data = dict(self._graph.nodes[nid])
            label = data.pop("label", "Unknown")
            nodes_out.append({
                "id": nid,
                "label": label,
                "properties": data,
            })

        sampled_ids = visited
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
