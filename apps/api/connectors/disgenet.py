"""DisGeNET connector — gene-disease associations via Monarch Initiative.

Original DisGeNET API requires an API key. This connector uses the
Monarch Initiative knowledge graph (free, no key) as an alternative,
providing equivalent gene-disease association data from multiple
curated sources (OMIM, Orphanet, ClinVar, etc.).
API: https://api-v3.monarchinitiative.org/v3/docs
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from .base import BaseConnector

log = logging.getLogger(__name__)


class DisGeNETConnector(BaseConnector):
    """Gene-disease associations via Monarch Initiative (free alternative)."""

    name = "disgenet"
    BASE_URL = "https://api-v3.monarchinitiative.org/v3/api"
    cache_ttl = 86400

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Step 1: Search Monarch for the query (genes, diseases, phenotypes)
        data, meta = await self._cached_get(
            f"{self.BASE_URL}/search",
            params={"q": query, "limit": min(limit, 50)},
        )
        if not data or not isinstance(data, dict):
            return []
        items = data.get("items", [])
        results: List[Dict[str, Any]] = []
        for item in items:
            category = item.get("category", "")
            entity_type = "gene" if "Gene" in category else "disease" if "Disease" in category else "phenotype"
            monarch_id = item.get("id", "")
            results.append({
                "id": monarch_id,
                "entity_type": entity_type,
                "canonical_name": item.get("name", ""),
                "description": item.get("description", ""),
                "gene_symbol": item.get("symbol", ""),
                "disease_name": item.get("name", "") if entity_type == "disease" else "",
                "category": category,
                "source": "disgenet",
                "source_db": "Monarch Initiative",
                "url": f"https://monarchinitiative.org/{monarch_id}",
                "provenance": [self._prov(
                    url=f"https://monarchinitiative.org/{monarch_id}",
                    ext_id=monarch_id, confidence=0.9,
                    reasoning="Monarch Initiative (DisGeNET alternative)"
                ).to_dict()],
            })
        return results[:limit]

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        data, meta = await self._cached_get(f"{self.BASE_URL}/entity/{entity_id}")
        if not data or not isinstance(data, dict):
            return None
        return {
            "id": entity_id,
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "category": data.get("category", ""),
            "symbol": data.get("symbol", ""),
            "source": "disgenet",
            "source_db": "Monarch Initiative",
            "url": f"https://monarchinitiative.org/{entity_id}",
        }
