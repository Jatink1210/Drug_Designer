"""IGVDB API connector for Indian Genome Variation Database."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class IGVDBAPIConnector(BaseConnector):
    """IGVDB API connector for Indian Genome Variation Database."""
    
    name = "IGVDB_API"
    BASE = "http://www.igvdb.res.in/api"
    cache_ttl = 86400
    rate_limit_rps = 2.0
    rate_limit_burst = 4
    http_timeout = 30.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/variants/search"
        params = {"q": query, "limit": min(limit, 50)}
        data, meta = await self._cached_get(url, params=params)
        if not data or "variants" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        for variant in data["variants"][:limit]:
            variant_id = variant.get("variant_id", "")
            results.append({
                "id": variant_id,
                "entity_type": "genetic_variant",
                "canonical_name": variant_id,
                "name": variant_id,
                "description": f"IGVDB variant: {variant_id}",
                "variant_id": variant_id,
                "allele_freq_igv": variant.get("allele_freq"),
                "source": self.name,
                "url": "http://www.igvdb.res.in/",
                "provenance": [self._prov(
                    url="http://www.igvdb.res.in/",
                    ext_id=variant_id,
                    confidence=0.89,
                    reasoning="IGVDB Indian genome variation data"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE}/variants/{entity_id}"
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        return {
            "id": entity_id,
            "entity_type": "genetic_variant",
            "canonical_name": entity_id,
            "name": entity_id,
            "description": f"IGVDB variant: {entity_id}",
            "variant_id": entity_id,
            "allele_freq_igv": data.get("allele_freq"),
            "source": self.name,
            "url": "http://www.igvdb.res.in/",
            "provenance": [self._prov(
                url="http://www.igvdb.res.in/",
                ext_id=entity_id,
                confidence=0.89,
                reasoning="IGVDB detailed variant data"
            ).to_dict()],
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        variant_data = await self.fetch_by_id(entity_id)
        if not variant_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "genetic_variant",
            "confidence": 0.89,
            "url": variant_data.get("url"),
            "provenance": self._prov(
                url=variant_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.89,
                reasoning="IGVDB Indian genome variation data"
            ).to_dict()
        }]
