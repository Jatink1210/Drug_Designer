"""KEGG (Kyoto Encyclopedia of Genes and Genomes) connector."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from .base import BaseConnector


class KEGGConnector(BaseConnector):
    """Query KEGG REST API for pathways, compounds, and diseases."""

    name = "kegg"
    BASE_URL = "https://rest.kegg.jp"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/find/pathway/{query}"
        body, meta = await self._cached_get(url)
        if body is None:
            return []

        results = []
        text = body if isinstance(body, str) else str(body)
        for line in text.strip().split("\n")[:limit]:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                results.append({
                    "id": parts[0].strip(),
                    "name": parts[1].strip(),
                    "source": "kegg",
                    "type": "pathway",
                    "url": f"https://www.kegg.jp/entry/{parts[0].strip()}",
                })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/get/{entity_id}"
        body, meta = await self._cached_get(url)
        if body:
            return {"id": entity_id, "data": body, "source": "kegg"}
        return None

    async def count(self, query: str) -> Optional[int]:
        results = await self.search(query, limit=1000)
        return len(results)
