"""ChemSpider connector for chemical structures."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ChemSpiderConnector(BaseConnector):
    """ChemSpider connector for chemical database."""
    
    name = "ChemSpider"
    SEARCH_URL = "https://www.chemspider.com/Search.asmx/SimpleSearch"
    cache_ttl = 86400  # 24h
    http_timeout = 15.0
    rate_limit_rps = 2.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Note: ChemSpider requires API key
        params = {
            "query": query,
            "token": "PLACEHOLDER"
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        compounds = data.get("Results", [])
        
        for compound_id in compounds[:limit]:
            results.append({
                "id": f"ChemSpider:{compound_id}",
                "entity_type": "compound",
                "canonical_name": f"CSID{compound_id}",
                "name": f"CSID{compound_id}",
                "chemspider_id": compound_id,
                "url": f"https://www.chemspider.com/Chemical-Structure.{compound_id}.html",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.chemspider.com/Chemical-Structure.{compound_id}.html",
                    ext_id=str(compound_id),
                    confidence=0.9,
                    reasoning="ChemSpider compound"
                ).to_dict()],
            })
        
        return results
