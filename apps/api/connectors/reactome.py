"""Reactome pathway API connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class ReactomeConnector(BaseConnector):
    name = "Reactome"
    BASE = "https://reactome.org/ContentService"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = "%s/search/query" % self.BASE
        params = {"query": query, "types": "Pathway", "cluster": "true"}
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        results: List[Dict[str, Any]] = []
        entries = data.get("results", [])
        for group in entries:
            for entry in group.get("entries", [])[:limit]:
                st_id = entry.get("stId", "")
                name = entry.get("name", "")
                species = entry.get("species", ["Homo sapiens"])
                sp = species[0] if species else "Homo sapiens"
                results.append({
                    "id": st_id,
                    "entity_type": "pathway",
                    "canonical_name": name,
                    "name": name,
                    "description": entry.get("summation", [""])[0] if entry.get("summation") else "",
                    "pathway_id": st_id,
                    "source_db": "Reactome",
                    "species": sp,
                    "url": "https://reactome.org/content/detail/%s" % st_id,
                    "provenance": [self._prov(
                        url="https://reactome.org/content/detail/%s" % st_id,
                        ext_id=st_id, confidence=0.95, reasoning="Reactome curated pathway"
                    ).to_dict()],
                })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = "%s/data/pathway/%s/containedEvents" % (self.BASE, entity_id)
        data, meta = await self._cached_get(url)
        if not data:
            return None
        genes: List[str] = []
        if isinstance(data, list):
            for ev in data:
                display = ev.get("displayName", "")
                if display:
                    genes.append(display)
        return {
            "id": entity_id,
            "entity_type": "pathway",
            "canonical_name": entity_id,
            "pathway_id": entity_id,
            "source_db": "Reactome",
            "genes": genes[:50],
            "gene_count": len(genes),
            "url": "https://reactome.org/content/detail/%s" % entity_id,
        }


