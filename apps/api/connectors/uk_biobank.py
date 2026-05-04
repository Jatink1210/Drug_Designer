"""UK Biobank connector for population genomics data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class UKBiobankConnector(BaseConnector):
    """
    UK Biobank connector for large-scale population genomics and health data.
    
    UK Biobank (https://www.ukbiobank.ac.uk) is a large-scale biomedical database
    containing genetic and health information from half a million UK participants.
    
    API: UK Biobank Data Showcase API
    Authentication required for full data access.
    """
    
    name = "UK_Biobank"
    BASE = "https://biobank.ndph.ox.ac.uk/showcase/api"
    cache_ttl = 86400
    rate_limit_rps = 2.0
    rate_limit_burst = 4
    http_timeout = 30.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/search"
        params = {"q": query, "limit": min(limit, 50)}
        data, meta = await self._cached_get(url, params=params)
        if not data or "fields" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        for field in data["fields"][:limit]:
            field_id = field.get("field_id", "")
            results.append({
                "id": field_id,
                "entity_type": "biobank_field",
                "canonical_name": field.get("title", query),
                "name": field.get("title", query),
                "description": strip_html(field.get("description", "")),
                "field_id": field_id,
                "category": field.get("category", ""),
                "value_type": field.get("value_type", ""),
                "source": self.name,
                "url": f"https://biobank.ndph.ox.ac.uk/showcase/field.cgi?id={field_id}",
                "provenance": [self._prov(
                    url=f"https://biobank.ndph.ox.ac.uk/showcase/field.cgi?id={field_id}",
                    ext_id=field_id,
                    confidence=0.95,
                    reasoning="UK Biobank population genomics data"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE}/field/{entity_id}"
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        return {
            "id": entity_id,
            "entity_type": "biobank_field",
            "canonical_name": data.get("title", entity_id),
            "name": data.get("title", entity_id),
            "description": strip_html(data.get("description", "")),
            "field_id": entity_id,
            "category": data.get("category", ""),
            "value_type": data.get("value_type", ""),
            "participants": data.get("participants", 0),
            "source": self.name,
            "url": f"https://biobank.ndph.ox.ac.uk/showcase/field.cgi?id={entity_id}",
            "provenance": [self._prov(
                url=f"https://biobank.ndph.ox.ac.uk/showcase/field.cgi?id={entity_id}",
                ext_id=entity_id,
                confidence=0.95,
                reasoning="UK Biobank detailed field data"
            ).to_dict()],
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        field_data = await self.fetch_by_id(entity_id)
        if not field_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "population_genomics",
            "confidence": 0.95,
            "participants": field_data.get("participants"),
            "url": field_data.get("url"),
            "provenance": self._prov(
                url=field_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.95,
                reasoning="UK Biobank population genomics data"
            ).to_dict()
        }]
