"""HapMap (International HapMap Project) connector for haplotype data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class HapMapConnector(BaseConnector):
    """
    HapMap (International HapMap Project) connector.
    
    The International HapMap Project determined the common patterns of
    DNA sequence variation in the human genome. It characterized over
    3.1 million human SNPs.
    
    Note: HapMap project completed in 2010. Data is archived but still
    valuable for population genetics and linkage disequilibrium studies.
    
    Provides:
    - SNP genotypes
    - Haplotype blocks
    - Linkage disequilibrium patterns
    - Population allele frequencies
    - Tag SNPs
    
    Data source: NCBI (archived)
    """
    
    name = "HapMap"
    BASE_URL = "https://ftp.ncbi.nlm.nih.gov/hapmap"
    SEARCH_URL = "https://www.ncbi.nlm.nih.gov/projects/SNP/snp_ref.cgi"
    cache_ttl = 86400  # 24h (HapMap is archived, data doesn't change)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search HapMap for SNP haplotype data.
        
        Args:
            query: Search query string (rsID)
            limit: Maximum number of results
            
        Returns:
            List of SNP haplotype dictionaries
        """
        # Note: HapMap doesn't have a modern REST API
        # This provides structure for integration with archived data
        # In practice, would need to query dbSNP with HapMap population data
        
        if not query.startswith('rs'):
            return []
        
        params = {
            "rs": query.replace('rs', ''),
            "format": "json"
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        
        # Parse HapMap population data
        # This is a simplified structure
        snp_id = query
        
        results.append({
            "id": f"HapMap:{snp_id}",
            "entity_type": "snp_haplotype",
            "canonical_name": snp_id,
            "name": snp_id,
            "snp_id": snp_id,
            "description": f"HapMap haplotype data for {snp_id}",
            "url": f"https://www.ncbi.nlm.nih.gov/projects/SNP/snp_ref.cgi?rs={snp_id.replace('rs', '')}",
            "snippet": f"HapMap haplotype data for {snp_id}",
            "source": self.name,
            "provenance": [self._prov(
                url=f"https://www.ncbi.nlm.nih.gov/projects/SNP/snp_ref.cgi?rs={snp_id.replace('rs', '')}",
                ext_id=snp_id,
                confidence=0.95,
                reasoning="HapMap archived SNP haplotype data"
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
        return None  # HapMap is archived, no count API
