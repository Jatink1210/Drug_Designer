"""LOVD (Leiden Open Variation Database) connector for genetic variant data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class LOVDConnector(BaseConnector):
    """
    LOVD (Leiden Open Variation Database) connector.
    
    LOVD provides a flexible, freely available tool for gene-centered
    collection and display of DNA variations. It is used by many
    gene-specific databases worldwide.
    
    Provides:
    - Gene-specific variant databases
    - Variant classifications
    - Phenotype information
    - Frequency data
    - Functional predictions
    
    Data source: Leiden University Medical Center
    """
    
    name = "LOVD"
    BASE_URL = "https://databases.lovd.nl/shared"
    SEARCH_URL = "https://databases.lovd.nl/shared/api/rest/variants"
    cache_ttl = 86400  # 24h (variant data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search LOVD for genetic variants.
        
        Args:
            query: Search query string (gene symbol, variant)
            limit: Maximum number of results
            
        Returns:
            List of variant dictionaries
        """
        params = {
            "search_gene": query,
            "format": "application/json",
            "page_size": min(limit, 100)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, list):
            return []
        
        results: List[Dict[str, Any]] = []
        
        for variant in data[:limit]:
            if not isinstance(variant, dict):
                continue
                
            variant_id = variant.get("id", "")
            gene = variant.get("gene", "")
            dna_change = variant.get("VariantOnGenome/DNA", "")
            protein_change = variant.get("VariantOnTranscript/Protein", "")
            
            # Get classification
            classification = variant.get("VariantOnGenome/Classification", "")
            
            # Get phenotype
            phenotype = variant.get("Individual/Phenotype", "")
            
            description = f"{gene} {dna_change}"
            if protein_change:
                description += f" ({protein_change})"
            
            results.append({
                "id": f"LOVD:{variant_id}",
                "entity_type": "genetic_variant",
                "canonical_name": description,
                "name": description,
                "variant_id": variant_id,
                "gene": gene,
                "dna_change": dna_change,
                "protein_change": protein_change,
                "classification": classification,
                "phenotype": phenotype,
                "description": description,
                "url": f"https://databases.lovd.nl/shared/variants/{variant_id}",
                "snippet": f"{description} - {classification}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://databases.lovd.nl/shared/variants/{variant_id}",
                    ext_id=str(variant_id),
                    confidence=0.94,
                    reasoning="LOVD gene-specific variant database"
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
            "search_gene": query,
            "format": "application/json",
            "page_size": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if isinstance(data, dict):
            return data.get("total", 0)
        
        return None
