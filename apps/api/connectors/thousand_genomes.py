"""1000 Genomes Project connector for human genetic variation data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ThousandGenomesConnector(BaseConnector):
    """
    1000 Genomes Project connector for human genetic variation.
    
    The 1000 Genomes Project created a catalogue of common human genetic
    variation, using whole genome sequencing of 2,504 individuals from
    26 populations.
    
    Provides:
    - SNPs (Single Nucleotide Polymorphisms)
    - Indels (Insertions/Deletions)
    - Structural variants
    - Population allele frequencies
    - Phased haplotypes
    
    Data source: International Genome Sample Resource (IGSR)
    """
    
    name = "1000 Genomes"
    BASE_URL = "https://www.internationalgenome.org/api"
    SEARCH_URL = "https://www.internationalgenome.org/api/beta/variant"
    cache_ttl = 86400  # 24h (variant data changes infrequently)
    http_timeout = 30.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search 1000 Genomes for variants.
        
        Args:
            query: Search query string (rsID, genomic region)
            limit: Maximum number of results
            
        Returns:
            List of variant dictionaries
        """
        # Parse query - could be rsID or genomic region
        params = {}
        
        if query.startswith('rs'):
            # rsID search
            params["id"] = query
        else:
            # Assume genomic region (chr:start-end)
            params["region"] = query
        
        params["limit"] = min(limit, 100)
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        variants = data.get("variants", []) if isinstance(data, dict) else []
        
        for variant in variants[:limit]:
            if not isinstance(variant, dict):
                continue
                
            variant_id = variant.get("id", "")
            chrom = variant.get("chr", "")
            pos = variant.get("pos", 0)
            ref = variant.get("ref", "")
            alt = variant.get("alt", "")
            
            # Get allele frequencies
            frequencies = variant.get("frequencies", {})
            
            description = f"{chrom}:{pos} {ref}>{alt}"
            
            results.append({
                "id": f"1000G:{variant_id}",
                "entity_type": "genetic_variant",
                "canonical_name": variant_id,
                "name": variant_id,
                "variant_id": variant_id,
                "chromosome": chrom,
                "position": pos,
                "reference": ref,
                "alternate": alt,
                "frequencies": frequencies,
                "description": description,
                "url": f"https://www.internationalgenome.org/variant/{variant_id}",
                "snippet": description,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.internationalgenome.org/variant/{variant_id}",
                    ext_id=variant_id,
                    confidence=0.99,
                    reasoning="1000 Genomes Project sequenced variant"
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
        return None  # 1000 Genomes API doesn't provide count
