"""GenomeAsia API connector for Asian population genomics."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class GenomeAsiaAPIConnector(BaseConnector):
    """GenomeAsia API connector for Asian population genomics data."""
    
    name = "GenomeAsia_API"
    BASE = "https://browser.genomeasia100k.org/api"
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
                "description": f"GenomeAsia variant: {variant_id}",
                "variant_id": variant_id,
                "allele_freq_asia": variant.get("allele_freq"),
                "source": self.name,
                "url": f"https://browser.genomeasia100k.org/variant/{variant_id}",
                "provenance": [self._prov(
                    url=f"https://browser.genomeasia100k.org/variant/{variant_id}",
                    ext_id=variant_id,
                    confidence=0.91,
                    reasoning="GenomeAsia Asian population genomics"
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
            "description": f"GenomeAsia variant: {entity_id}",
            "variant_id": entity_id,
            "allele_freq_asia": data.get("allele_freq"),
            "source": self.name,
            "url": f"https://browser.genomeasia100k.org/variant/{entity_id}",
            "provenance": [self._prov(
                url=f"https://browser.genomeasia100k.org/variant/{entity_id}",
                ext_id=entity_id,
                confidence=0.91,
                reasoning="GenomeAsia detailed variant data"
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
            "confidence": 0.91,
            "url": variant_data.get("url"),
            "provenance": self._prov(
                url=variant_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.91,
                reasoning="GenomeAsia Asian population genomics"
            ).to_dict()
        }]
