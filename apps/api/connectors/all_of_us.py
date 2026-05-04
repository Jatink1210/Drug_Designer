"""All of Us Research Program connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class AllOfUsConnector(BaseConnector):
    """
    All of Us Research Program connector for diverse population genomics.
    
    All of Us (https://allofus.nih.gov) is a historic effort to gather data from
    one million or more people living in the United States to accelerate research
    and improve health, with emphasis on diversity.
    
    API: All of Us Public Data Browser API
    No authentication required for public data.
    """
    
    name = "All_of_Us"
    BASE = "https://public.api.researchallofus.org"
    cache_ttl = 86400
    rate_limit_rps = 2.0
    rate_limit_burst = 4
    http_timeout = 30.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/v1/concepts/search"
        params = {"query": query, "limit": min(limit, 50)}
        data, meta = await self._cached_get(url, params=params)
        if not data or "items" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        for concept in data["items"][:limit]:
            concept_id = concept.get("concept_id", "")
            results.append({
                "id": str(concept_id),
                "entity_type": "genomic_concept",
                "canonical_name": concept.get("concept_name", query),
                "name": concept.get("concept_name", query),
                "description": concept.get("concept_code", ""),
                "concept_id": concept_id,
                "domain": concept.get("domain_id", ""),
                "vocabulary": concept.get("vocabulary_id", ""),
                "source": self.name,
                "url": f"https://databrowser.researchallofus.org/",
                "provenance": [self._prov(
                    url="https://databrowser.researchallofus.org/",
                    ext_id=str(concept_id),
                    confidence=0.93,
                    reasoning="All of Us diverse population genomics"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE}/v1/concepts/{entity_id}"
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        return {
            "id": entity_id,
            "entity_type": "genomic_concept",
            "canonical_name": data.get("concept_name", entity_id),
            "name": data.get("concept_name", entity_id),
            "description": data.get("concept_code", ""),
            "concept_id": entity_id,
            "domain": data.get("domain_id", ""),
            "vocabulary": data.get("vocabulary_id", ""),
            "source": self.name,
            "url": "https://databrowser.researchallofus.org/",
            "provenance": [self._prov(
                url="https://databrowser.researchallofus.org/",
                ext_id=entity_id,
                confidence=0.93,
                reasoning="All of Us detailed concept data"
            ).to_dict()],
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        concept_data = await self.fetch_by_id(entity_id)
        if not concept_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "population_genomics",
            "confidence": 0.93,
            "url": concept_data.get("url"),
            "provenance": self._prov(
                url=concept_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.93,
                reasoning="All of Us diverse population genomics"
            ).to_dict()
        }]
