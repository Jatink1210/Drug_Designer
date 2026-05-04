"""cBioPortal connector for cancer genomics."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class cBioPortalConnector(BaseConnector):
    name = "cBioPortal"
    SEARCH_URL = "https://www.cbioportal.org/api/mutations"
    cache_ttl = 86400
    http_timeout = 15.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {"keyword": query, "pageSize": min(limit, 50)}
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, list):
            return []
        
        results: List[Dict[str, Any]] = []
        
        for mutation in data[:limit]:
            mutation_id = mutation.get("mutationEventId", "")
            gene = mutation.get("gene", {}).get("hugoGeneSymbol", "")
            
            results.append({
                "id": f"cBioPortal:{mutation_id}",
                "entity_type": "variant",
                "canonical_name": f"{gene} {mutation.get('proteinChange', '')}",
                "name": f"{gene} {mutation.get('proteinChange', '')}",
                "mutation_id": str(mutation_id),
                "gene": gene,
                "protein_change": mutation.get("proteinChange", ""),
                "url": f"https://www.cbioportal.org/mutation_mapper?gene={gene}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.cbioportal.org/mutation_mapper?gene={gene}",
                    ext_id=str(mutation_id),
                    confidence=1.0,
                    reasoning="cBioPortal mutation"
                ).to_dict()],
            })
        
        return results
