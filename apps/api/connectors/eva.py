"""EVA (European Variation Archive) connector for genetic variation data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class EVAConnector(BaseConnector):
    """
    EVA (European Variation Archive) connector.
    
    EVA is an open-access database of all types of genetic variation data
    from all species. It archives:
    - SNPs
    - Short indels
    - Copy number variants
    - Structural variants
    
    Provides:
    - Variant annotations
    - Population frequencies
    - Clinical significance
    - Functional predictions
    
    Data source: EMBL-EBI
    """
    
    name = "EVA"
    BASE_URL = "https://www.ebi.ac.uk/eva/webservices/rest/v1"
    SEARCH_URL = "https://www.ebi.ac.uk/eva/webservices/rest/v1/variants"
    cache_ttl = 86400  # 24h (variant data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 10.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search EVA for genetic variants.
        
        Args:
            query: Search query string (rsID, genomic region)
            limit: Maximum number of results
            
        Returns:
            List of variant dictionaries
        """
        params = {
            "species": "hsapiens",
            "pageSize": min(limit, 100)
        }
        
        # Determine query type
        if query.startswith('rs'):
            # rsID search
            url = f"{self.BASE_URL}/variants/{query}/info"
        else:
            # Region search (format: chr:start-end)
            params["region"] = query
            url = f"{self.SEARCH_URL}"
        
        data, meta = await self._cached_get(url, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        
        # Handle single variant response
        if "id" in data:
            variants = [data]
        else:
            # Handle list response
            response = data.get("response", [])
            variants = response[0].get("result", []) if response else []
        
        for variant in variants[:limit]:
            if not isinstance(variant, dict):
                continue
                
            variant_id = variant.get("id", "")
            chrom = variant.get("chromosome", "")
            start = variant.get("start", 0)
            ref = variant.get("reference", "")
            alt = variant.get("alternate", "")
            
            # Get annotations
            annotation = variant.get("annotation", {})
            consequence_types = annotation.get("consequenceTypes", []) if isinstance(annotation, dict) else []
            
            description = f"{chrom}:{start} {ref}>{alt}"
            
            results.append({
                "id": f"EVA:{variant_id}",
                "entity_type": "genetic_variant",
                "canonical_name": variant_id,
                "name": variant_id,
                "variant_id": variant_id,
                "chromosome": chrom,
                "position": start,
                "reference": ref,
                "alternate": alt,
                "consequence_types": consequence_types[:5],
                "description": description,
                "url": f"https://www.ebi.ac.uk/eva/?variant={variant_id}",
                "snippet": description,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.ebi.ac.uk/eva/?variant={variant_id}",
                    ext_id=variant_id,
                    confidence=0.97,
                    reasoning="EVA archived genetic variant"
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
            "species": "hsapiens",
            "region": query,
            "pageSize": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        response = data.get("response", [])
        if response and isinstance(response, list):
            return response[0].get("numTotalResults", 0)
        
        return None
