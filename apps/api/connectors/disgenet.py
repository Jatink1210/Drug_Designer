"""DisGeNET connector — disease-gene association database."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from .base import BaseConnector


class DisGeNETConnector(BaseConnector):
    """Query DisGeNET for disease-gene associations.
    
    Uses the public REST API (rate-limited without API key).
    """

    name = "disgenet"
    BASE_URL = "https://www.disgenet.org/api"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/gda/disease/{query}"
        params = {"limit": min(limit, 100), "format": "json"}
        body, meta = await self._cached_get(url, params=params)

        if body is None or not isinstance(body, list):
            # Fallback: search by gene symbol
            url_gene = f"{self.BASE_URL}/gda/gene/{query}"
            body, meta = await self._cached_get(url_gene, params=params)

        if body is None or not isinstance(body, list):
            return []

        return [
            {
                "gene_symbol": item.get("gene_symbol", ""),
                "disease_name": item.get("disease_name", ""),
                "score": item.get("score", 0),
                "pmid_count": item.get("Npmids", 0),
                "source": "disgenet",
                "disease_id": item.get("diseaseid", ""),
                "gene_id": item.get("geneid", ""),
            }
            for item in body[:limit]
        ]

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/gda/gene/{entity_id}"
        params = {"format": "json"}
        body, meta = await self._cached_get(url, params=params)
        if body and isinstance(body, list) and len(body) > 0:
            return {"gene_id": entity_id, "associations": body, "source": "disgenet"}
        return None
