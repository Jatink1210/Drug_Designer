"""ATC connector for Anatomical Therapeutic Chemical classification."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ATCConnector(BaseConnector):
    """
    ATC (Anatomical Therapeutic Chemical) classification system connector.
    
    ATC is a drug classification system controlled by WHO that classifies drugs
    according to the organ or system on which they act and their therapeutic,
    pharmacological and chemical properties.
    
    API: WHO ATC/DDD Index
    No authentication required (free public API).
    """
    
    name = "ATC"
    BASE = "https://www.whocc.no/atc_ddd_index/api"
    cache_ttl = 172800
    rate_limit_rps = 2.0
    rate_limit_burst = 4
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/search"
        params = {"q": query, "limit": min(limit, 50)}
        data, meta = await self._cached_get(url, params=params)
        if not data or "results" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        for item in data["results"][:limit]:
            atc_code = item.get("atc_code", "")
            results.append({
                "id": atc_code,
                "entity_type": "drug_classification",
                "canonical_name": item.get("name", query),
                "name": item.get("name", query),
                "description": f"ATC classification: {item.get('name', query)}",
                "atc_code": atc_code,
                "atc_level": item.get("level", ""),
                "ddd": item.get("ddd", ""),
                "source": self.name,
                "url": f"https://www.whocc.no/atc_ddd_index/?code={atc_code}",
                "provenance": [self._prov(
                    url=f"https://www.whocc.no/atc_ddd_index/?code={atc_code}",
                    ext_id=atc_code,
                    confidence=0.97,
                    reasoning="WHO ATC classification system"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE}/code/{entity_id}"
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        return {
            "id": entity_id,
            "entity_type": "drug_classification",
            "canonical_name": data.get("name", entity_id),
            "name": data.get("name", entity_id),
            "description": f"ATC classification: {data.get('name', entity_id)}",
            "atc_code": entity_id,
            "atc_level": data.get("level", ""),
            "ddd": data.get("ddd", ""),
            "source": self.name,
            "url": f"https://www.whocc.no/atc_ddd_index/?code={entity_id}",
            "provenance": [self._prov(
                url=f"https://www.whocc.no/atc_ddd_index/?code={entity_id}",
                ext_id=entity_id,
                confidence=0.97,
                reasoning="WHO ATC detailed classification"
            ).to_dict()],
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        atc_data = await self.fetch_by_id(entity_id)
        if not atc_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "drug_classification",
            "confidence": 0.97,
            "url": atc_data.get("url"),
            "provenance": self._prov(
                url=atc_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.97,
                reasoning="WHO ATC classification system"
            ).to_dict()
        }]
