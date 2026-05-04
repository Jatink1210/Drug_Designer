"""PharmVar connector for pharmacogene variation data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PharmVarConnector(BaseConnector):
    """
    PharmVar connector for pharmacogene variation.
    
    PharmVar is a central repository for pharmacogene (PGx) variation that
    focuses on haplotype structure and allelic variation. It serves as the
    official repository for PGx allele nomenclature.
    
    Provides:
    - Star allele nomenclature
    - Haplotype definitions
    - Variant annotations
    - Gene-specific information
    - Reference sequences
    
    Data source: PharmVar Consortium
    """
    
    name = "PharmVar"
    BASE_URL = "https://www.pharmvar.org/api"
    SEARCH_URL = "https://www.pharmvar.org/api/genes"
    cache_ttl = 86400  # 24h (allele nomenclature changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search PharmVar for pharmacogene alleles.
        
        Args:
            query: Search query string (gene symbol)
            limit: Maximum number of results
            
        Returns:
            List of allele dictionaries
        """
        # PharmVar API structure
        url = f"{self.SEARCH_URL}/{query}/alleles"
        
        data, meta = await self._cached_get(url)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        alleles = data.get("alleles", [])
        
        for allele in alleles[:limit]:
            if not isinstance(allele, dict):
                continue
                
            allele_name = allele.get("name", "")
            gene = allele.get("gene", query)
            haplotype = allele.get("haplotype", "")
            
            # Get defining variants
            variants = allele.get("variants", [])
            variant_count = len(variants) if isinstance(variants, list) else 0
            
            # Get functional status
            function = allele.get("function", "")
            
            description = f"{gene}*{allele_name}"
            
            results.append({
                "id": f"PharmVar:{gene}_{allele_name}",
                "entity_type": "pharmacogene_allele",
                "canonical_name": description,
                "name": description,
                "allele_name": allele_name,
                "gene": gene,
                "haplotype": haplotype,
                "function": function,
                "variant_count": variant_count,
                "variants": variants[:10] if isinstance(variants, list) else [],
                "description": f"{description} - {function}",
                "url": f"https://www.pharmvar.org/gene/{gene}",
                "snippet": f"{description} - {function} ({variant_count} variants)",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.pharmvar.org/gene/{gene}",
                    ext_id=f"{gene}_{allele_name}",
                    confidence=0.99,
                    reasoning="PharmVar official pharmacogene allele nomenclature"
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
        url = f"{self.SEARCH_URL}/{query}/alleles"
        
        data, _ = await self._cached_get(url, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        alleles = data.get("alleles", [])
        return len(alleles) if isinstance(alleles, list) else None
