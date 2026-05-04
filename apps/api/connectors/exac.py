"""ExAC (Exome Aggregation Consortium) connector for exome variant data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ExACConnector(BaseConnector):
    """
    ExAC (Exome Aggregation Consortium) connector.
    
    ExAC aggregated exome sequencing data from 60,706 unrelated individuals
    sequenced as part of various disease-specific and population genetic
    studies.
    
    Note: ExAC has been superseded by gnomAD, but ExAC data is still
    valuable for historical comparisons.
    
    Provides:
    - Exome variant frequencies
    - Population-specific allele frequencies
    - Constraint metrics
    - Loss-of-function variants
    
    Data source: Broad Institute
    """
    
    name = "ExAC"
    BASE_URL = "http://exac.broadinstitute.org/api"
    SEARCH_URL = "http://exac.broadinstitute.org/api/variant"
    cache_ttl = 86400  # 24h (ExAC is archived, data doesn't change)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search ExAC for exome variants.
        
        Args:
            query: Search query string (variant ID: chr-pos-ref-alt)
            limit: Maximum number of results
            
        Returns:
            List of variant dictionaries
        """
        # ExAC uses variant ID format: chr-pos-ref-alt
        # Example: 1-55516888-G-GA
        
        url = f"{self.SEARCH_URL}/{query}"
        
        data, meta = await self._cached_get(url)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        
        variant = data.get("variant", {})
        if not variant:
            return results
        
        variant_id = variant.get("variant_id", query)
        chrom = variant.get("chrom", "")
        pos = variant.get("pos", 0)
        ref = variant.get("ref", "")
        alt = variant.get("alt", "")
        
        # Get allele frequencies
        allele_freq = variant.get("allele_freq", 0)
        allele_count = variant.get("allele_count", 0)
        allele_num = variant.get("allele_num", 0)
        
        # Get population frequencies
        pop_freqs = variant.get("pop_afs", {})
        
        description = f"{chrom}:{pos} {ref}>{alt} (AF={allele_freq:.6f})"
        
        results.append({
            "id": f"ExAC:{variant_id}",
            "entity_type": "exome_variant",
            "canonical_name": variant_id,
            "name": variant_id,
            "variant_id": variant_id,
            "chromosome": chrom,
            "position": pos,
            "reference": ref,
            "alternate": alt,
            "allele_frequency": allele_freq,
            "allele_count": allele_count,
            "allele_number": allele_num,
            "population_frequencies": pop_freqs,
            "description": description,
            "url": f"http://exac.broadinstitute.org/variant/{variant_id}",
            "snippet": description,
            "source": self.name,
            "provenance": [self._prov(
                url=f"http://exac.broadinstitute.org/variant/{variant_id}",
                ext_id=variant_id,
                confidence=0.98,
                reasoning="ExAC exome sequencing variant"
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
        return None  # ExAC API returns single variant per query
