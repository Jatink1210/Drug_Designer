"""PANTHER (Protein ANalysis THrough Evolutionary Relationships) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PANTHERConnector(BaseConnector):
    """
    PANTHER connector for protein classification and pathway data.
    
    PANTHER provides:
    - Protein family classifications
    - Phylogenetic trees
    - Functional annotations
    - Pathway data
    - Gene ontology associations
    
    Particularly useful for:
    - Evolutionary analysis
    - Functional classification
    - Pathway analysis
    - Gene list analysis
    """
    
    name = "PANTHER"
    BASE_URL = "http://www.pantherdb.org/services/oai/pantherdb"
    SEARCH_URL = "http://www.pantherdb.org/services/oai/pantherdb/search"
    cache_ttl = 86400  # 24h (PANTHER updates infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search PANTHER for protein families and pathways.
        
        Args:
            query: Search query string (gene name, protein ID)
            limit: Maximum number of results
            
        Returns:
            List of PANTHER classification dictionaries
        """
        # PANTHER API endpoint for gene/protein search
        params = {
            "search": query,
            "searchType": "gene",
            "organism": "9606",  # Human
            "limit": min(limit, 100)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        search_results = data.get("search", {}).get("mapped_genes", {})
        genes = search_results.get("gene", []) if isinstance(search_results, dict) else []
        
        if isinstance(genes, dict):
            genes = [genes]
        
        for gene in genes[:limit]:
            if not isinstance(gene, dict):
                continue
                
            gene_id = gene.get("id", "")
            gene_name = gene.get("label", "")
            
            # Get PANTHER family
            panther_family = gene.get("panther_family", "")
            subfamily = gene.get("subfamily", "")
            
            # Get pathways
            pathways = gene.get("pathway", [])
            if isinstance(pathways, dict):
                pathways = [pathways]
            
            pathway_names = [p.get("label", "") for p in pathways if isinstance(p, dict)]
            
            results.append({
                "id": f"PANTHER:{gene_id}",
                "entity_type": "protein_classification",
                "canonical_name": gene_name,
                "name": gene_name,
                "gene_id": gene_id,
                "panther_family": panther_family,
                "subfamily": subfamily,
                "pathways": pathway_names[:5],
                "description": f"{gene_name} - {panther_family}",
                "url": f"http://www.pantherdb.org/genes/gene.do?acc={gene_id}",
                "snippet": f"{gene_name} classified in {panther_family}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"http://www.pantherdb.org/genes/gene.do?acc={gene_id}",
                    ext_id=gene_id,
                    confidence=0.96,
                    reasoning="PANTHER evolutionary protein classification"
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
            "search": query,
            "searchType": "gene",
            "organism": "9606",
            "limit": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        search_results = data.get("search", {})
        return search_results.get("number_of_matches", 0) if isinstance(search_results, dict) else None
