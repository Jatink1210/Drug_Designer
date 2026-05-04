"""DECIPHER connector for genomic variant interpretation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class DECIPHERConnector(BaseConnector):
    """
    DECIPHER connector for genomic variant interpretation.
    
    DECIPHER (Database of Chromosomal Imbalance and Phenotype in Humans
    using Ensembl Resources) is an interactive web-based database which
    incorporates a suite of tools designed to aid the interpretation of
    genomic variants.
    
    Provides:
    - Structural variants
    - Copy number variants (CNVs)
    - Phenotype data
    - Gene-disease associations
    - Patient phenotypes
    - Syndrome information
    
    Data source: Wellcome Sanger Institute
    """
    
    name = "DECIPHER"
    BASE_URL = "https://www.deciphergenomics.org/api"
    SEARCH_URL = "https://www.deciphergenomics.org/api/cnv/search"
    cache_ttl = 86400  # 24h (variant data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search DECIPHER for genomic variants.
        
        Args:
            query: Search query string (gene symbol, region)
            limit: Maximum number of results
            
        Returns:
            List of variant dictionaries
        """
        params = {
            "gene": query,
            "limit": min(limit, 100)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        variants = data.get("results", [])
        
        for variant in variants[:limit]:
            if not isinstance(variant, dict):
                continue
                
            variant_id = variant.get("id", "")
            chromosome = variant.get("chr", "")
            start = variant.get("start", 0)
            end = variant.get("end", 0)
            variant_type = variant.get("type", "")  # deletion, duplication, etc.
            
            # Get phenotype information
            phenotypes = variant.get("phenotypes", [])
            if isinstance(phenotypes, str):
                phenotypes = [phenotypes]
            
            # Get pathogenicity
            pathogenicity = variant.get("pathogenicity", "")
            
            description = f"{chromosome}:{start}-{end} {variant_type}"
            
            results.append({
                "id": f"DECIPHER:{variant_id}",
                "entity_type": "structural_variant",
                "canonical_name": description,
                "name": description,
                "variant_id": variant_id,
                "chromosome": chromosome,
                "start": start,
                "end": end,
                "variant_type": variant_type,
                "pathogenicity": pathogenicity,
                "phenotypes": phenotypes[:5] if isinstance(phenotypes, list) else [],
                "description": description,
                "url": f"https://www.deciphergenomics.org/sequence-variant/{variant_id}",
                "snippet": f"{description} - {pathogenicity}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.deciphergenomics.org/sequence-variant/{variant_id}",
                    ext_id=str(variant_id),
                    confidence=0.96,
                    reasoning="DECIPHER curated genomic variant"
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
            "gene": query,
            "limit": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("total", 0)
