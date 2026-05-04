"""PharmGKB (Pharmacogenomics Knowledge Base) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PharmGKBConnector(BaseConnector):
    """
    PharmGKB (Pharmacogenomics Knowledge Base) connector.
    
    PharmGKB is a comprehensive resource that curates knowledge about
    the impact of genetic variation on drug response.
    
    Provides:
    - Drug-gene interactions
    - Pharmacogenomic variants
    - Clinical annotations
    - Drug labels
    - Dosing guidelines
    - Genotype-phenotype relationships
    
    Data source: Stanford University
    """
    
    name = "PharmGKB"
    BASE_URL = "https://api.pharmgkb.org/v1"
    SEARCH_URL = "https://api.pharmgkb.org/v1/data/clinicalAnnotation"
    cache_ttl = 86400  # 24h (pharmacogenomic data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 10.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search PharmGKB for pharmacogenomic annotations.
        
        Args:
            query: Search query string (gene, drug, variant)
            limit: Maximum number of results
            
        Returns:
            List of pharmacogenomic annotation dictionaries
        """
        params = {
            "view": "base",
            "limit": min(limit, 100)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        annotations = data.get("data", [])
        
        # Filter by query
        query_lower = query.lower()
        
        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
                
            # Check if query matches gene, drug, or variant
            gene = annotation.get("gene", {})
            gene_symbol = gene.get("symbol", "") if isinstance(gene, dict) else ""
            
            drug = annotation.get("drug", {})
            drug_name = drug.get("name", "") if isinstance(drug, dict) else ""
            
            variant = annotation.get("variant", {})
            variant_name = variant.get("name", "") if isinstance(variant, dict) else ""
            
            # Filter by query
            if query_lower not in gene_symbol.lower() and \
               query_lower not in drug_name.lower() and \
               query_lower not in variant_name.lower():
                continue
            
            annotation_id = annotation.get("id", "")
            phenotype = annotation.get("phenotype", "")
            level = annotation.get("level", "")
            
            description = f"{gene_symbol} - {drug_name}: {phenotype}"
            
            results.append({
                "id": f"PharmGKB:{annotation_id}",
                "entity_type": "pharmacogenomic_annotation",
                "canonical_name": description,
                "name": description,
                "annotation_id": annotation_id,
                "gene_symbol": gene_symbol,
                "drug_name": drug_name,
                "variant_name": variant_name,
                "phenotype": phenotype,
                "level": level,
                "description": description,
                "url": f"https://www.pharmgkb.org/clinicalAnnotation/{annotation_id}",
                "snippet": f"{description} (Level {level})",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.pharmgkb.org/clinicalAnnotation/{annotation_id}",
                    ext_id=annotation_id,
                    confidence=0.97,
                    reasoning="PharmGKB curated pharmacogenomic annotation"
                ).to_dict()],
            })
            
            if len(results) >= limit:
                break
        
        return results
    
    async def count(self, query: str) -> Optional[int]:
        """
        Get count of search results.
        
        Args:
            query: Search query string
            
        Returns:
            Number of results or None
        """
        return None  # PharmGKB API doesn't provide direct count
