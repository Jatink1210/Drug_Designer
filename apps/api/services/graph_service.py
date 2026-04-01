"""Knowledge Graph Service — delegates to pluggable graph store.

In embedded/workbench mode uses NetworkX+SQLite.
In full/studio mode uses Neo4j.
"""

import logging
from typing import Dict, Any

from services.graph_store import get_graph_store

log = logging.getLogger(__name__)


class GraphService:
    """Facade that delegates to the active graph store backend."""

    def __init__(self):
        self._store = get_graph_store()

    async def setup_constraints(self):
        await self._store.setup_constraints()

    async def create_node(self, label: str, node_id: str, properties: Dict[str, Any]):
        await self._store.create_node(label, node_id, properties)

    async def create_edge(
        self,
        src_label: str,
        src_id: str,
        rel_type: str,
        dst_label: str,
        dst_id: str,
        properties: Dict[str, Any] = None,
    ):
        await self._store.create_edge(
            src_label, src_id, rel_type, dst_label, dst_id, properties
        )

    async def get_neighborhood(self, node_id: str, depth: int = 1) -> Dict[str, Any]:
        return await self._store.get_neighborhood(node_id, depth)

    async def get_shortest_path(self, src_id: str, dst_id: str) -> Dict[str, Any]:
        return await self._store.get_shortest_path(src_id, dst_id)

    async def close(self):
        await self._store.close()
