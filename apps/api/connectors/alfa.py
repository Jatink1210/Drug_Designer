"""ALFA (Allele Frequency Aggregator) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class ALFAConnector(BaseConnector):
    name = "ALFA"
    SEARCH_URL = "https://api.ncbi.nlm.nih.gov/variation/v0/refsnp"
    cache_ttl = 86400
    http_timeout = 15.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        rs_id = query.replace("rs", "")
        data, meta = await self._cached_get(f"{self.SEARCH_URL}/{rs_id}/frequency")
        
        if not data or not isinstance(data, dict):
            return []
        
        return [{
            "id": f"ALFA:{query}",
            "entity_type": "variant",
            "canonical_name": query,
            "name": query,
            "rs_id": query,
            "allele_frequency": data.get("allele_frequency", {}),
            "url": f"https://www.ncbi.nlm.nih.gov/snp/{query}",
            "source": self.name,
            "provenance": [self._prov(
                url=f"https://www.ncbi.nlm.nih.gov/snp/{query}",
                ext_id=query,
                confidence=1.0,
                reasoning="ALFA allele frequency"
            ).to_dict()],
        }]
