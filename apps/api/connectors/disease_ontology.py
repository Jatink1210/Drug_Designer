"""Disease Ontology (DO) connector — free, no API key.

OBO Foundry disease ontology with DOID identifiers.
API Reference: https://www.disease-ontology.org/do-kb/api_doc
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector


class DiseaseOntologyConnector(BaseConnector):
    name = "DiseaseOntology"
    BASE_URL = "https://api.disease-ontology.org/v1"
    cache_ttl = 86400  # 24h

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Use POST /terms/search endpoint
        body = {"searchText": query, "searchType": "name", "size": min(limit, 50)}
        data, meta = await self._cached_post(f"{self.BASE_URL}/terms/search", json_body=body, extra_key=query)
        if not data:
            # Fallback: try label-based lookup
            data, meta = await self._cached_get(
                f"{self.BASE_URL}/terms/label/{query.replace(' ', '%20')}"
            )
            if data and isinstance(data, dict):
                data = [data]
            elif not data:
                return []
        results = []
        items = data if isinstance(data, list) else data.get("results", data.get("terms", [])) if isinstance(data, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            doid = item.get("id", item.get("obo_id", item.get("doid", "")))
            name = item.get("name", item.get("label", ""))
            results.append({
                "id": doid,
                "entity_type": "disease",
                "canonical_name": name,
                "description": item.get("definition", item.get("description", "")),
                "synonyms": item.get("synonyms", item.get("exactSynonyms", [])),
                "ontology_ids": {"DOID": doid},
                "url": f"https://disease-ontology.org/term/{doid}",
                "source_db": "DiseaseOntology",
                "provenance": [self._prov(
                    url=f"https://disease-ontology.org/term/{doid}",
                    confidence=1.0, reasoning="Disease Ontology DO-KB API"
                ).to_dict()],
            })
        return results[:limit]
