"""InterPro connector — free, no API key.

Protein families, domains, and functional sites. 46K+ entries.
API Reference: https://www.ebi.ac.uk/interpro/api/
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector


class InterProConnector(BaseConnector):
    name = "InterPro"
    BASE_URL = "https://www.ebi.ac.uk/interpro/api"
    cache_ttl = 86400

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {"search": query, "page_size": min(limit, 50)}
        data, meta = await self._cached_get(f"{self.BASE_URL}/entry/interpro", params=params)
        if not data or "results" not in data:
            return []
        results = []
        for item in data["results"]:
            meta_info = item.get("metadata", {})
            results.append({
                "id": meta_info.get("accession", ""),
                "entity_type": "protein_domain",
                "canonical_name": meta_info.get("name", ""),
                "description": (meta_info.get("description") or [{}])[0].get("text", "") if meta_info.get("description") else "",
                "entry_type": meta_info.get("type", ""),
                "member_databases": meta_info.get("member_databases", {}),
                "provenance": [self._prov(
                    url=f"https://www.ebi.ac.uk/interpro/entry/InterPro/{meta_info.get('accession', '')}",
                    ext_id=meta_info.get("accession", ""), confidence=1.0, reasoning="InterPro EBI"
                ).to_dict()],
            })
        return results[:limit]

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        data, _ = await self._cached_get(f"{self.BASE_URL}/entry/interpro/{entity_id}")
        return data
