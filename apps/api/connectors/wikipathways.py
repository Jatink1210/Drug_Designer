"""WikiPathways connector — free, no API key.

Community-curated biological pathways. ~3K pathways for human.
API Reference: https://www.wikipathways.org/
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector


class WikiPathwaysConnector(BaseConnector):
    name = "WikiPathways"
    BASE_URL = "https://www.wikipathways.org/json"
    cache_ttl = 86400

    def __init__(self) -> None:
        super().__init__()
        import httpx
        from core.http_client import ResilientClient
        self._client = ResilientClient(timeout=self.http_timeout)
        self._client._client = httpx.AsyncClient(
            timeout=self.http_timeout, follow_redirects=True,
            headers={"User-Agent": "DrugDesigner/1.0"},
        )

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        # New static JSON endpoint (old SOAP/REST service shut down May 2026)
        data, meta = await self._cached_get(
            f"{self.BASE_URL}/findPathwaysByText.json",
        )
        if not data or not isinstance(data, dict):
            return []
        pathways = data.get("pathwayInfo", [])
        if not isinstance(pathways, list):
            return []
        # Client-side filter: match query against pathway name and datanodes
        query_lower = query.lower()
        results = []
        for pw in pathways:
            if not isinstance(pw, dict):
                continue
            name = pw.get("name", "")
            raw_dn = pw.get("datanodes", "")
            datanodes = " ".join(raw_dn) if isinstance(raw_dn, list) else str(raw_dn)
            if query_lower in name.lower() or query_lower in datanodes.lower():
                wp_id = pw.get("id", "")
                results.append({
                    "id": wp_id,
                    "entity_type": "pathway",
                    "canonical_name": name,
                    "pathway_id": wp_id,
                    "source_db": "WikiPathways",
                    "species": pw.get("species", "Homo sapiens"),
                    "url": pw.get("url", f"https://www.wikipathways.org/pathways/{wp_id}"),
                    "provenance": [self._prov(
                        url=f"https://www.wikipathways.org/pathways/{wp_id}",
                        ext_id=wp_id, confidence=1.0, reasoning="WikiPathways"
                    ).to_dict()],
                })
                if len(results) >= limit:
                    break
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch pathway info from the cached full pathway list."""
        data, _ = await self._cached_get(
            f"{self.BASE_URL}/findPathwaysByText.json",
        )
        name = entity_id
        description = ""
        genes: list[str] = []
        if data and isinstance(data, dict):
            for pw in data.get("pathwayInfo", []):
                if isinstance(pw, dict) and pw.get("id") == entity_id:
                    name = pw.get("name", entity_id)
                    description = pw.get("description", "")
                    raw_dn = pw.get("datanodes", "")
                    if isinstance(raw_dn, str):
                        genes = [g.strip() for g in raw_dn.split(",") if g.strip()]
                    elif isinstance(raw_dn, list):
                        genes = [str(g) for g in raw_dn if g]
                    break

        return {
            "id": entity_id,
            "entity_type": "pathway",
            "canonical_name": name,
            "pathway_id": entity_id,
            "source_db": "WikiPathways",
            "genes": genes[:200],
            "gene_count": len(genes),
            "description": description,
            "url": f"https://www.wikipathways.org/pathways/{entity_id}",
        }
