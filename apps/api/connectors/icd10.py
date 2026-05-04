"""ICD-10 (International Classification of Diseases, 10th Revision) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ICD10Connector(BaseConnector):
    """
    ICD-10 connector for disease classification codes.
    
    ICD-10 is the 10th revision of the International Statistical Classification
    of Diseases and Related Health Problems (ICD), a medical classification list
    by the World Health Organization (WHO).
    
    Used for:
    - Disease coding
    - Epidemiological health management
    - Clinical purposes
    - Reimbursement systems
    """
    
    name = "ICD-10"
    BASE_URL = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    cache_ttl = 86400  # 24h (ICD codes change infrequently)
    http_timeout = 20.0
    rate_limit_rps = 10.0  # NLM allows reasonable rate limits
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search ICD-10 for disease codes.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of ICD-10 code dictionaries
        """
        params = {
            "terms": query,
            "maxList": min(limit, 100),
            "sf": "code,name"
        }
        
        data, meta = await self._cached_get(self.BASE_URL, params=params)
        
        if not data or not isinstance(data, list) or len(data) < 4:
            return []
        
        results: List[Dict[str, Any]] = []
        
        # NLM API returns: [total_count, [codes], [names], [extra_data]]
        codes = data[1] if len(data) > 1 and isinstance(data[1], list) else []
        names = data[2] if len(data) > 2 and isinstance(data[2], list) else []
        
        for i, code in enumerate(codes[:limit]):
            if i >= len(names):
                break
                
            name = names[i] if i < len(names) else ""
            
            results.append({
                "id": f"ICD10:{code}",
                "entity_type": "disease_code",
                "canonical_name": name,
                "name": name,
                "code": code,
                "description": name,
                "classification": "ICD-10",
                "url": f"https://icd.who.int/browse10/2019/en#/{code}",
                "snippet": name,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://icd.who.int/browse10/2019/en#/{code}",
                    ext_id=code,
                    confidence=0.99,
                    reasoning="WHO ICD-10 official disease classification code"
                ).to_dict()],
            })
        
        return results
    
    async def count(self, query: str) -> Optional[int]:
        """
        Get count of search results.
        
        Args:
            query: Search query string
            
        Returns:
            Number of results or None
        """
        params = {
            "terms": query,
            "maxList": 0
        }
        
        data, _ = await self._cached_get(self.BASE_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, list) or len(data) < 1:
            return None
        
        return data[0] if isinstance(data[0], int) else None
