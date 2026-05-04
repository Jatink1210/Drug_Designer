"""TOPMed connector for Trans-Omics for Precision Medicine data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class TOPMedConnector(BaseConnector):
    """
    TOPMed (Trans-Omics for Precision Medicine) connector.
    
    TOPMed (https://www.nhlbiwgs.org) is a program to generate scientific resources
    to enhance understanding of fundamental biological processes and the genomic basis
    of heart, lung, blood, and sleep disorders.
    """
    
    name = "TOPMed"
    BASE = "https://bravo.sph.umich.edu/freeze8/hg38/api"
    cache_ttl = 86400
    rate_limit_rps = 2.0
    rate_limit_burst = 4
    http_timeout = 30.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/variants"
        params = {"q": query, "limit": min(limit, 50)}
        data, meta = await self._cached_get(url, params=params)
        if not data or "data" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        for variant in data["data"][:limit]:
            variant_id = variant.get("variant_id", "")
            results.append({
                "id": variant_id,
                "entity_type": "genetic_variant",
                "canonical_name": variant_id,
                "name": variant_id,
                "description": f"TOPMed variant: {variant_id}",
                "variant_id": variant_id,
                "allele_freq": variant.get("allele_freq"),
                "source": self.name,
                "url": f"https://bravo.sph.umich.edu/freeze8/hg38/variant/{variant_id}",
                "provenance": [self._prov(
                    url=f"https://bravo.sph.umich.edu/freeze8/hg38/variant/{variant_id}",
                    ext_id=variant_id,
                    confidence=0.94,
                    reasoning="TOPMed whole genome sequencing data"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE}/variant/{entity_id}"
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        return {
            "id": entity_id,
            "entity_type": "genetic_variant",
            "canonical_name": entity_id,
            "name": entity_id,
            "description": f"TOPMed variant: {entity_id}",
            "variant_id": entity_id,
            "allele_freq": data.get("allele_freq"),
            "source": self.name,
            "url": f"https://bravo.sph.umich.edu/freeze8/hg38/variant/{entity_id}",
            "provenance": [self._prov(
                url=f"https://bravo.sph.umich.edu/freeze8/hg38/variant/{entity_id}",
                ext_id=entity_id,
                confidence=0.94,
                reasoning="TOPMed detailed variant data"
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
            "confidence": 0.94,
            "url": variant_data.get("url"),
            "provenance": self._prov(
                url=variant_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.94,
                reasoning="TOPMed whole genome sequencing data"
            ).to_dict()
        }]
