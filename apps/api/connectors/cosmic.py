"""COSMIC (Catalogue of Somatic Mutations in Cancer) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class COSMICConnector(BaseConnector):
    name = "COSMIC"
    SEARCH_URL = "https://cancer.sanger.ac.uk/cosmic/search"
    cache_ttl = 86400
    http_timeout = 15.0
    rate_limit_rps = 2.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {"q": query, "limit": min(limit, 50)}
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        mutations = data.get("mutations", [])
        
        for mutation in mutations[:limit]:
            mutation_id = mutation.get("id", "")
            results.append({
                "id": f"COSMIC:{mutation_id}",
                "entity_type": "variant",
                "canonical_name": mutation.get("name", mutation_id),
                "name": mutation.get("name", mutation_id),
                "mutation_id": mutation_id,
                "gene": mutation.get("gene", ""),
                "url": f"https://cancer.sanger.ac.uk/cosmic/mutation/overview?id={mutation_id}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://cancer.sanger.ac.uk/cosmic/mutation/overview?id={mutation_id}",
                    ext_id=mutation_id,
                    confidence=1.0,
                    reasoning="COSMIC mutation"
                ).to_dict()],
            })
        
        return results
