"""TCGA (The Cancer Genome Atlas) connector for cancer genomics data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class TCGAConnector(BaseConnector):
    """
    TCGA (The Cancer Genome Atlas) connector.
    
    TCGA is a landmark cancer genomics program that molecularly characterized
    over 20,000 primary cancer and matched normal samples spanning 33 cancer
    types.
    
    Provides:
    - Somatic mutations
    - Copy number variations
    - Gene expression
    - DNA methylation
    - Clinical data
    - Survival data
    
    Data source: NCI Genomic Data Commons (GDC)
    """
    
    name = "TCGA"
    BASE_URL = "https://api.gdc.cancer.gov"
    SEARCH_URL = "https://api.gdc.cancer.gov/ssms"
    cache_ttl = 86400  # 24h (TCGA data is archived, changes infrequently)
    http_timeout = 30.0
    rate_limit_rps = 10.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search TCGA for cancer mutations via GDC API.
        
        Args:
            query: Search query string (gene symbol)
            limit: Maximum number of results
            
        Returns:
            List of mutation dictionaries
        """
        # GDC API uses JSON filters
        filters = {
            "op": "and",
            "content": [
                {
                    "op": "in",
                    "content": {
                        "field": "consequence.transcript.gene.symbol",
                        "value": [query]
                    }
                }
            ]
        }
        
        params = {
            "filters": str(filters).replace("'", '"'),
            "size": min(limit, 100),
            "from": 0,
            "format": "json"
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        hits = data.get("data", {}).get("hits", [])
        
        for hit in hits[:limit]:
            if not isinstance(hit, dict):
                continue
                
            mutation_id = hit.get("ssm_id", "")
            genomic_dna_change = hit.get("genomic_dna_change", "")
            mutation_type = hit.get("mutation_type", "")
            
            # Get consequence information
            consequences = hit.get("consequence", [])
            gene_symbols = []
            consequence_types = []
            
            if isinstance(consequences, list):
                for cons in consequences[:3]:
                    if isinstance(cons, dict):
                        transcript = cons.get("transcript", {})
                        if isinstance(transcript, dict):
                            gene = transcript.get("gene", {})
                            if isinstance(gene, dict):
                                symbol = gene.get("symbol", "")
                                if symbol:
                                    gene_symbols.append(symbol)
                        
                        cons_type = cons.get("transcript", {}).get("consequence_type", "")
                        if cons_type:
                            consequence_types.append(cons_type)
            
            # Get number of cases
            num_cases = hit.get("occurrence", [{}])[0].get("case", {}).get("project", {}).get("project_id", "")
            
            description = f"{genomic_dna_change} ({mutation_type})"
            
            results.append({
                "id": f"TCGA:{mutation_id}",
                "entity_type": "cancer_mutation",
                "canonical_name": description,
                "name": description,
                "mutation_id": mutation_id,
                "genomic_dna_change": genomic_dna_change,
                "mutation_type": mutation_type,
                "gene_symbols": gene_symbols[:5],
                "consequence_types": consequence_types[:5],
                "description": description,
                "url": f"https://portal.gdc.cancer.gov/ssms/{mutation_id}",
                "snippet": f"{description} - {', '.join(gene_symbols[:2])}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://portal.gdc.cancer.gov/ssms/{mutation_id}",
                    ext_id=mutation_id,
                    confidence=0.98,
                    reasoning="TCGA cancer genome mutation via GDC"
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
        filters = {
            "op": "and",
            "content": [
                {
                    "op": "in",
                    "content": {
                        "field": "consequence.transcript.gene.symbol",
                        "value": [query]
                    }
                }
            ]
        }
        
        params = {
            "filters": str(filters).replace("'", '"'),
            "size": 0,
            "format": "json"
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        pagination = data.get("data", {}).get("pagination", {})
        return pagination.get("total", 0)
