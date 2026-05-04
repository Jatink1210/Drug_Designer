"""ICGC (International Cancer Genome Consortium) connector for cancer genomics data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ICGCConnector(BaseConnector):
    """
    ICGC (International Cancer Genome Consortium) connector.
    
    ICGC coordinates large-scale cancer genome studies in tumours from
    50 different cancer types and/or subtypes.
    
    Provides:
    - Somatic mutations
    - Copy number alterations
    - Structural variants
    - Gene expression data
    - Epigenetic modifications
    - Clinical data
    
    Data from 25,000+ cancer genomes across multiple cancer types.
    """
    
    name = "ICGC"
    BASE_URL = "https://dcc.icgc.org/api/v1"
    SEARCH_URL = "https://dcc.icgc.org/api/v1/mutations"
    cache_ttl = 86400  # 24h (cancer genomics data changes infrequently)
    http_timeout = 30.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search ICGC for cancer mutations.
        
        Args:
            query: Search query string (gene symbol, mutation ID)
            limit: Maximum number of results
            
        Returns:
            List of mutation dictionaries
        """
        params = {
            "filters": f'{{"gene":{{"symbol":{{"is":["{query}"]}}}}}}',
            "size": min(limit, 100),
            "from": 0
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        hits = data.get("hits", [])
        
        for hit in hits[:limit]:
            if not isinstance(hit, dict):
                continue
                
            mutation_id = hit.get("id", "")
            gene_symbol = hit.get("geneSymbol", "")
            chromosome = hit.get("chromosome", "")
            start = hit.get("start", 0)
            end = hit.get("end", 0)
            mutation_type = hit.get("type", "")
            
            # Get mutation details
            mutation = hit.get("mutation", "")
            consequence_type = hit.get("consequenceType", "")
            
            # Get affected donors count
            affected_donors = hit.get("affectedDonorCountTotal", 0)
            
            description = f"{gene_symbol} {mutation} ({consequence_type})"
            
            results.append({
                "id": f"ICGC:{mutation_id}",
                "entity_type": "cancer_mutation",
                "canonical_name": description,
                "name": description,
                "mutation_id": mutation_id,
                "gene_symbol": gene_symbol,
                "chromosome": chromosome,
                "start": start,
                "end": end,
                "mutation_type": mutation_type,
                "mutation": mutation,
                "consequence_type": consequence_type,
                "affected_donors": affected_donors,
                "description": description,
                "url": f"https://dcc.icgc.org/mutations/{mutation_id}",
                "snippet": f"{description} - {affected_donors} affected donors",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://dcc.icgc.org/mutations/{mutation_id}",
                    ext_id=mutation_id,
                    confidence=0.97,
                    reasoning="ICGC cancer genome mutation"
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
            "filters": f'{{"gene":{{"symbol":{{"is":["{query}"]}}}}}}',
            "size": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("pagination", {}).get("total", 0)
