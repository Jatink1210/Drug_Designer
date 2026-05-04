"""DGIdb (Drug Gene Interaction Database) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class DGIdbConnector(BaseConnector):
    """
    DGIdb (Drug Gene Interaction Database) connector.
    
    DGIdb mines existing resources that generate hypotheses about how
    mutated genes might be targeted therapeutically or prioritized for
    drug development.
    
    Provides:
    - Drug-gene interactions
    - Interaction types (inhibitor, activator, etc.)
    - FDA approval status
    - Clinical trial information
    - Source databases
    
    Integrates data from 30+ sources including:
    - ChEMBL
    - DrugBank
    - PharmGKB
    - CIViC
    - And many more
    """
    
    name = "DGIdb"
    BASE_URL = "https://dgidb.org/api/v2"
    SEARCH_URL = "https://dgidb.org/api/v2/interactions.json"
    cache_ttl = 86400  # 24h (interaction data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 10.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search DGIdb for drug-gene interactions.
        
        Args:
            query: Search query string (gene name, drug name)
            limit: Maximum number of results
            
        Returns:
            List of drug-gene interaction dictionaries
        """
        params = {
            "genes": query
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        matched_terms = data.get("matchedTerms", [])
        
        for term in matched_terms[:limit]:
            if not isinstance(term, dict):
                continue
                
            gene_name = term.get("geneName", "")
            interactions = term.get("interactions", [])
            
            for interaction in interactions:
                if not isinstance(interaction, dict):
                    continue
                    
                drug_name = interaction.get("drugName", "")
                interaction_types = interaction.get("interactionTypes", [])
                sources = interaction.get("sources", [])
                
                # Get PMIDs
                pmids = interaction.get("pmids", [])
                
                interaction_id = f"{gene_name}_{drug_name}"
                description = f"{drug_name} interacts with {gene_name}"
                
                results.append({
                    "id": f"DGIdb:{interaction_id}",
                    "entity_type": "drug_gene_interaction",
                    "canonical_name": description,
                    "name": description,
                    "gene_name": gene_name,
                    "drug_name": drug_name,
                    "interaction_types": interaction_types[:5] if isinstance(interaction_types, list) else [],
                    "sources": sources[:5] if isinstance(sources, list) else [],
                    "pmids": pmids[:5] if isinstance(pmids, list) else [],
                    "description": description,
                    "url": f"https://dgidb.org/interaction_search_results?genes={gene_name}",
                    "snippet": f"{description} ({', '.join(interaction_types[:3]) if interaction_types else 'interaction'})",
                    "source": self.name,
                    "provenance": [self._prov(
                        url=f"https://dgidb.org/interaction_search_results?genes={gene_name}",
                        ext_id=interaction_id,
                        confidence=0.92,
                        reasoning=f"DGIdb drug-gene interaction from {len(sources)} sources"
                    ).to_dict()],
                })
                
                if len(results) >= limit:
                    break
            
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
        params = {
            "genes": query
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        # Count total interactions across all matched terms
        total = 0
        matched_terms = data.get("matchedTerms", [])
        for term in matched_terms:
            if isinstance(term, dict):
                interactions = term.get("interactions", [])
                total += len(interactions) if isinstance(interactions, list) else 0
        
        return total
