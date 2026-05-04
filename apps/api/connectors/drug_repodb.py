"""RepoDB connector for drug repurposing database."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class RepoDBConnector(BaseConnector):
    """
    RepoDB connector for drug repurposing information.
    
    RepoDB is a standard database for drug repositioning, providing a
    comprehensive resource of approved and failed drugs with their
    indications.
    
    Provides:
    - Approved drug-indication pairs
    - Failed drug-indication pairs
    - Clinical trial status
    - Drug repurposing opportunities
    
    Particularly useful for:
    - Drug repurposing research
    - Identifying new indications for existing drugs
    - Understanding drug failure patterns
    
    Data source: Brown University
    """
    
    name = "RepoDB"
    BASE_URL = "http://apps.chiragjpgroup.org/repoDB/api"
    SEARCH_URL = "http://apps.chiragjpgroup.org/repoDB/api/search"
    cache_ttl = 86400  # 24h (repurposing data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search RepoDB for drug repurposing opportunities.
        
        Args:
            query: Search query string (drug name, indication)
            limit: Maximum number of results
            
        Returns:
            List of drug-indication pair dictionaries
        """
        params = {
            "query": query,
            "limit": min(limit, 100)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        items = data.get("results", []) if isinstance(data, dict) else []
        
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
                
            drug_name = item.get("drug_name", "")
            indication = item.get("indication", "")
            status = item.get("status", "")  # "Approved" or "Failed"
            
            # Get additional information
            phase = item.get("phase", "")
            nct_id = item.get("nct_id", "")
            
            pair_id = f"{drug_name}_{indication}".replace(" ", "_")
            description = f"{drug_name} for {indication} ({status})"
            
            results.append({
                "id": f"RepoDB:{pair_id}",
                "entity_type": "drug_indication_pair",
                "canonical_name": description,
                "name": description,
                "drug_name": drug_name,
                "indication": indication,
                "status": status,
                "phase": phase,
                "nct_id": nct_id,
                "description": description,
                "url": f"http://apps.chiragjpgroup.org/repoDB/#drug={drug_name}",
                "snippet": description,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"http://apps.chiragjpgroup.org/repoDB/#drug={drug_name}",
                    ext_id=pair_id,
                    confidence=0.94,
                    reasoning=f"RepoDB {status.lower()} drug-indication pair"
                ).to_dict()],
            })
        
        return results
    
    async def get_approved_indications(self, drug_name: str) -> List[Dict[str, Any]]:
        """
        Get all approved indications for a drug.
        
        Args:
            drug_name: Drug name
            
        Returns:
            List of approved indication dictionaries
        """
        params = {
            "drug": drug_name,
            "status": "Approved"
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        return data.get("results", [])
    
    async def get_failed_indications(self, drug_name: str) -> List[Dict[str, Any]]:
        """
        Get all failed indications for a drug.
        
        Args:
            drug_name: Drug name
            
        Returns:
            List of failed indication dictionaries
        """
        params = {
            "drug": drug_name,
            "status": "Failed"
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        return data.get("results", [])
    
    async def count(self, query: str) -> Optional[int]:
        """
        Get count of search results.
        
        Args:
            query: Search query string
            
        Returns:
            Number of results or None
        """
        params = {
            "query": query,
            "limit": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("total", 0)
