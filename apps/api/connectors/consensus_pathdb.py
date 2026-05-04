"""ConsensusPathDB connector for integrated pathway and interaction data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ConsensusPathDBConnector(BaseConnector):
    """
    ConsensusPathDB connector for integrated molecular interaction networks.
    
    ConsensusPathDB (http://cpdb.molgen.mpg.de/) integrates interaction networks
    from 32 public databases including protein-protein, genetic, metabolic, signaling,
    gene regulatory, and drug-target interactions.
    
    API: RESTful web services at cpdb.molgen.mpg.de
    No authentication required (free public API).
    """
    
    name = "ConsensusPathDB"
    BASE = "http://cpdb.molgen.mpg.de/ws"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 2.0  # Conservative rate limit
    rate_limit_burst = 4
    http_timeout = 30.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for pathways and interactions by gene/protein name.
        
        Args:
            query: Gene symbol, protein name, or UniProt ID
            limit: Maximum number of results to return
            
        Returns:
            List of pathway and interaction records
        """
        # Search for entity first
        url = f"{self.BASE}/entities"
        params = {
            "q": query,
            "limit": min(limit, 50)
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        results: List[Dict[str, Any]] = []
        
        # Parse entity results
        entities = data if isinstance(data, list) else [data]
        
        for entity in entities[:limit]:
            entity_id = entity.get("cpdb_id", "")
            entity_name = entity.get("name", query)
            entity_type = entity.get("entity_type", "protein")
            accessions = entity.get("accessions", [])
            
            results.append({
                "id": entity_id,
                "entity_type": "pathway_entity",
                "canonical_name": entity_name,
                "name": entity_name,
                "description": f"{entity_name} pathway and interaction data",
                "cpdb_entity_type": entity_type,
                "accessions": accessions,
                "source": self.name,
                "url": f"http://cpdb.molgen.mpg.de/entity/{entity_id}",
                "provenance": [self._prov(
                    url=f"http://cpdb.molgen.mpg.de/entity/{entity_id}",
                    ext_id=entity_id,
                    confidence=0.92,
                    reasoning="ConsensusPathDB integrated pathway data from 32 databases"
                ).to_dict()],
            })
        
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed entity data by ConsensusPathDB ID.
        
        Args:
            entity_id: ConsensusPathDB entity ID
            
        Returns:
            Detailed entity record with interactions
        """
        url = f"{self.BASE}/entity/{entity_id}"
        
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        entity_name = data.get("name", entity_id)
        entity_type = data.get("entity_type", "protein")
        accessions = data.get("accessions", [])
        
        return {
            "id": entity_id,
            "entity_type": "pathway_entity",
            "canonical_name": entity_name,
            "name": entity_name,
            "description": data.get("description", ""),
            "cpdb_entity_type": entity_type,
            "accessions": accessions,
            "source": self.name,
            "url": f"http://cpdb.molgen.mpg.de/entity/{entity_id}",
            "provenance": [self._prov(
                url=f"http://cpdb.molgen.mpg.de/entity/{entity_id}",
                ext_id=entity_id,
                confidence=0.92,
                reasoning="ConsensusPathDB integrated entity data"
            ).to_dict()],
        }

    async def get_interactions(
        self, 
        entity_id: str,
        interaction_type: Optional[str] = None,
        limit: int = 100
    ) -> Optional[Dict[str, Any]]:
        """
        Get molecular interactions for an entity.
        
        Args:
            entity_id: ConsensusPathDB entity ID
            interaction_type: Filter by type (protein-protein, genetic, metabolic, etc.)
            limit: Maximum number of interactions to return
            
        Returns:
            Interaction records
        """
        url = f"{self.BASE}/interactions/{entity_id}"
        params = {"limit": min(limit, 500)}
        
        if interaction_type:
            params["type"] = interaction_type
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        interactions = []
        interaction_list = data if isinstance(data, list) else [data]
        
        for interaction in interaction_list[:limit]:
            interactions.append({
                "interaction_id": interaction.get("interaction_id"),
                "entity_a": interaction.get("entity_a"),
                "entity_b": interaction.get("entity_b"),
                "interaction_type": interaction.get("type"),
                "confidence": interaction.get("confidence_score"),
                "source_databases": interaction.get("sources", []),
                "pubmed_ids": interaction.get("pubmed_ids", []),
            })
        
        return {
            "entity_id": entity_id,
            "interaction_type": interaction_type,
            "interaction_count": len(interactions),
            "interactions": interactions,
            "url": f"http://cpdb.molgen.mpg.de/entity/{entity_id}"
        }

    async def get_pathways(
        self, 
        entity_id: str,
        pathway_source: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get pathways containing an entity.
        
        Args:
            entity_id: ConsensusPathDB entity ID
            pathway_source: Filter by source database (KEGG, Reactome, WikiPathways, etc.)
            
        Returns:
            Pathway membership records
        """
        url = f"{self.BASE}/pathways/{entity_id}"
        params = {}
        
        if pathway_source:
            params["source"] = pathway_source
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        pathways = []
        pathway_list = data if isinstance(data, list) else [data]
        
        for pathway in pathway_list:
            pathways.append({
                "pathway_id": pathway.get("pathway_id"),
                "pathway_name": pathway.get("name"),
                "pathway_source": pathway.get("source"),
                "entity_count": pathway.get("entity_count"),
                "pathway_url": pathway.get("url"),
            })
        
        return {
            "entity_id": entity_id,
            "pathway_source": pathway_source,
            "pathway_count": len(pathways),
            "pathways": pathways,
            "url": f"http://cpdb.molgen.mpg.de/entity/{entity_id}"
        }

    async def get_neighborhood(
        self, 
        entity_id: str,
        depth: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Get interaction neighborhood for an entity.
        
        Args:
            entity_id: ConsensusPathDB entity ID
            depth: Network depth (1 = direct interactions, 2 = second-degree, etc.)
            
        Returns:
            Network neighborhood data
        """
        url = f"{self.BASE}/neighborhood/{entity_id}"
        params = {"depth": min(depth, 3)}  # Limit to 3 degrees
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        nodes = []
        edges = []
        
        # Parse network data
        if "nodes" in data:
            for node in data["nodes"]:
                nodes.append({
                    "entity_id": node.get("id"),
                    "name": node.get("name"),
                    "entity_type": node.get("type"),
                })
        
        if "edges" in data:
            for edge in data["edges"]:
                edges.append({
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "interaction_type": edge.get("type"),
                    "confidence": edge.get("confidence"),
                })
        
        return {
            "entity_id": entity_id,
            "depth": depth,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
            "url": f"http://cpdb.molgen.mpg.de/entity/{entity_id}"
        }

    async def search_pathways(
        self, 
        query: str,
        pathway_source: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for pathways by name or description.
        
        Args:
            query: Pathway name or keyword
            pathway_source: Filter by source database
            limit: Maximum number of results
            
        Returns:
            List of matching pathways
        """
        url = f"{self.BASE}/pathways/search"
        params = {
            "q": query,
            "limit": min(limit, 50)
        }
        
        if pathway_source:
            params["source"] = pathway_source
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        results: List[Dict[str, Any]] = []
        pathways = data if isinstance(data, list) else [data]
        
        for pathway in pathways[:limit]:
            pathway_id = pathway.get("pathway_id", "")
            pathway_name = pathway.get("name", query)
            
            results.append({
                "id": pathway_id,
                "entity_type": "pathway",
                "canonical_name": pathway_name,
                "name": pathway_name,
                "description": pathway.get("description", ""),
                "pathway_source": pathway.get("source"),
                "entity_count": pathway.get("entity_count"),
                "source": self.name,
                "url": pathway.get("url", f"http://cpdb.molgen.mpg.de/pathway/{pathway_id}"),
                "provenance": [self._prov(
                    url=pathway.get("url", ""),
                    ext_id=pathway_id,
                    confidence=0.90,
                    reasoning=f"ConsensusPathDB pathway from {pathway.get('source', 'multiple sources')}"
                ).to_dict()],
            })
        
        return results

    async def get_over_representation_analysis(
        self, 
        gene_list: List[str],
        pathway_source: Optional[str] = None,
        p_value_cutoff: float = 0.05
    ) -> Optional[Dict[str, Any]]:
        """
        Perform pathway over-representation analysis on a gene list.
        
        Args:
            gene_list: List of gene symbols or IDs
            pathway_source: Filter by source database
            p_value_cutoff: P-value threshold for significance
            
        Returns:
            Over-represented pathways with statistics
        """
        url = f"{self.BASE}/ora"
        json_body = {
            "genes": gene_list,
            "p_value_cutoff": p_value_cutoff
        }
        
        if pathway_source:
            json_body["source"] = pathway_source
        
        data, meta = await self._cached_post(url, json_body=json_body)
        if not data:
            return None
        
        enriched_pathways = []
        pathways = data.get("pathways", [])
        
        for pathway in pathways:
            enriched_pathways.append({
                "pathway_id": pathway.get("pathway_id"),
                "pathway_name": pathway.get("name"),
                "pathway_source": pathway.get("source"),
                "p_value": pathway.get("p_value"),
                "q_value": pathway.get("q_value"),
                "overlap_size": pathway.get("overlap_size"),
                "pathway_size": pathway.get("pathway_size"),
                "overlap_genes": pathway.get("overlap_genes", []),
            })
        
        return {
            "gene_count": len(gene_list),
            "pathway_source": pathway_source,
            "p_value_cutoff": p_value_cutoff,
            "enriched_pathway_count": len(enriched_pathways),
            "enriched_pathways": enriched_pathways,
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records for pathway and interaction data.
        
        Args:
            entity_id: ConsensusPathDB entity ID
            
        Returns:
            List of evidence records
        """
        entity_data = await self.fetch_by_id(entity_id)
        if not entity_data:
            return []
        
        evidence_items = []
        
        # Add entity evidence
        evidence_items.append({
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "pathway_entity",
            "confidence": 0.92,
            "url": entity_data.get("url"),
            "provenance": self._prov(
                url=entity_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.92,
                reasoning="ConsensusPathDB integrated data from 32 databases"
            ).to_dict()
        })
        
        # Add interaction evidence
        interactions = await self.get_interactions(entity_id, limit=50)
        if interactions and interactions.get("interaction_count", 0) > 0:
            evidence_items.append({
                "source": self.name,
                "entity_id": entity_id,
                "evidence_type": "molecular_interactions",
                "confidence": 0.88,
                "interaction_count": interactions["interaction_count"],
                "url": interactions.get("url"),
                "provenance": self._prov(
                    url=interactions.get("url", ""),
                    ext_id=entity_id,
                    confidence=0.88,
                    reasoning=f"ConsensusPathDB molecular interactions ({interactions['interaction_count']} interactions)"
                ).to_dict()
            })
        
        # Add pathway evidence
        pathways = await self.get_pathways(entity_id)
        if pathways and pathways.get("pathway_count", 0) > 0:
            evidence_items.append({
                "source": self.name,
                "entity_id": entity_id,
                "evidence_type": "pathway_membership",
                "confidence": 0.90,
                "pathway_count": pathways["pathway_count"],
                "url": pathways.get("url"),
                "provenance": self._prov(
                    url=pathways.get("url", ""),
                    ext_id=entity_id,
                    confidence=0.90,
                    reasoning=f"ConsensusPathDB pathway membership ({pathways['pathway_count']} pathways)"
                ).to_dict()
            })
        
        return evidence_items
