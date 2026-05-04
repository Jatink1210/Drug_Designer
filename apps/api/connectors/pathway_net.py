"""PathwayNet connector for pathway crosstalk and network analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PathwayNetConnector(BaseConnector):
    """
    PathwayNet connector for pathway crosstalk and network-based pathway analysis.
    
    PathwayNet provides pathway-pathway interaction networks, crosstalk analysis,
    and network-based pathway enrichment. It integrates data from multiple pathway
    databases to identify pathway relationships and communication.
    
    API: RESTful web services
    No authentication required (free public API).
    """
    
    name = "PathwayNet"
    BASE = "https://pathwaynet.org/api"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 2.0  # Conservative rate limit
    rate_limit_burst = 4
    http_timeout = 30.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for pathways by name or description.
        
        Args:
            query: Pathway name or keyword
            limit: Maximum number of results to return
            
        Returns:
            List of pathway records
        """
        url = f"{self.BASE}/pathways/search"
        params = {
            "q": query,
            "limit": min(limit, 50)
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        results: List[Dict[str, Any]] = []
        
        # Parse pathway results
        pathways = data.get("pathways", []) if isinstance(data, dict) else data
        
        for pathway in pathways[:limit]:
            pathway_id = pathway.get("pathway_id", "")
            pathway_name = pathway.get("name", query)
            pathway_source = pathway.get("source", "PathwayNet")
            
            results.append({
                "id": pathway_id,
                "entity_type": "pathway",
                "canonical_name": pathway_name,
                "name": pathway_name,
                "description": pathway.get("description", ""),
                "pathway_source": pathway_source,
                "gene_count": pathway.get("gene_count"),
                "organism": pathway.get("organism", "Homo sapiens"),
                "source": self.name,
                "url": f"https://pathwaynet.org/pathway/{pathway_id}",
                "provenance": [self._prov(
                    url=f"https://pathwaynet.org/pathway/{pathway_id}",
                    ext_id=pathway_id,
                    confidence=0.90,
                    reasoning="PathwayNet integrated pathway data"
                ).to_dict()],
            })
        
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed pathway data by PathwayNet ID.
        
        Args:
            entity_id: PathwayNet pathway ID
            
        Returns:
            Detailed pathway record
        """
        url = f"{self.BASE}/pathways/{entity_id}"
        
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        pathway_name = data.get("name", entity_id)
        pathway_source = data.get("source", "PathwayNet")
        
        return {
            "id": entity_id,
            "entity_type": "pathway",
            "canonical_name": pathway_name,
            "name": pathway_name,
            "description": data.get("description", ""),
            "pathway_source": pathway_source,
            "gene_count": data.get("gene_count"),
            "genes": data.get("genes", []),
            "organism": data.get("organism", "Homo sapiens"),
            "source": self.name,
            "url": f"https://pathwaynet.org/pathway/{entity_id}",
            "provenance": [self._prov(
                url=f"https://pathwaynet.org/pathway/{entity_id}",
                ext_id=entity_id,
                confidence=0.90,
                reasoning="PathwayNet pathway with gene annotations"
            ).to_dict()],
        }

    async def get_pathway_crosstalk(
        self, 
        pathway_id: str,
        min_overlap: int = 2,
        limit: int = 50
    ) -> Optional[Dict[str, Any]]:
        """
        Get pathway crosstalk relationships.
        
        Args:
            pathway_id: PathwayNet pathway ID
            min_overlap: Minimum number of shared genes for crosstalk
            limit: Maximum number of crosstalk pathways to return
            
        Returns:
            Pathway crosstalk data
        """
        url = f"{self.BASE}/crosstalk/{pathway_id}"
        params = {
            "min_overlap": min_overlap,
            "limit": min(limit, 100)
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        crosstalk_pathways = []
        pathways = data.get("crosstalk", []) if isinstance(data, dict) else data
        
        for pathway in pathways[:limit]:
            crosstalk_pathways.append({
                "pathway_id": pathway.get("pathway_id"),
                "pathway_name": pathway.get("name"),
                "overlap_size": pathway.get("overlap_size"),
                "jaccard_index": pathway.get("jaccard_index"),
                "shared_genes": pathway.get("shared_genes", []),
                "crosstalk_score": pathway.get("crosstalk_score"),
            })
        
        return {
            "pathway_id": pathway_id,
            "min_overlap": min_overlap,
            "crosstalk_count": len(crosstalk_pathways),
            "crosstalk_pathways": crosstalk_pathways,
            "url": f"https://pathwaynet.org/pathway/{pathway_id}"
        }

    async def get_pathway_network(
        self, 
        pathway_ids: List[str],
        min_crosstalk_score: float = 0.1
    ) -> Optional[Dict[str, Any]]:
        """
        Build pathway-pathway interaction network.
        
        Args:
            pathway_ids: List of PathwayNet pathway IDs
            min_crosstalk_score: Minimum crosstalk score threshold
            
        Returns:
            Pathway network with nodes and edges
        """
        url = f"{self.BASE}/network"
        json_body = {
            "pathway_ids": pathway_ids,
            "min_crosstalk_score": min_crosstalk_score
        }
        
        data, meta = await self._cached_post(url, json_body=json_body)
        if not data:
            return None
        
        nodes = []
        edges = []
        
        # Parse network data
        for node in data.get("nodes", []):
            nodes.append({
                "pathway_id": node.get("id"),
                "pathway_name": node.get("name"),
                "gene_count": node.get("gene_count"),
                "centrality": node.get("centrality"),
            })
        
        for edge in data.get("edges", []):
            edges.append({
                "source": edge.get("source"),
                "target": edge.get("target"),
                "crosstalk_score": edge.get("crosstalk_score"),
                "overlap_size": edge.get("overlap_size"),
                "shared_genes": edge.get("shared_genes", []),
            })
        
        return {
            "pathway_count": len(pathway_ids),
            "min_crosstalk_score": min_crosstalk_score,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

    async def get_pathway_enrichment(
        self, 
        gene_list: List[str],
        pathway_source: Optional[str] = None,
        p_value_cutoff: float = 0.05,
        use_network: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Perform network-based pathway enrichment analysis.
        
        Args:
            gene_list: List of gene symbols
            pathway_source: Filter by source database
            p_value_cutoff: P-value threshold
            use_network: Use network propagation for enrichment
            
        Returns:
            Enriched pathways with network context
        """
        url = f"{self.BASE}/enrichment"
        json_body = {
            "genes": gene_list,
            "p_value_cutoff": p_value_cutoff,
            "use_network": use_network
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
                "network_score": pathway.get("network_score"),
                "connected_pathways": pathway.get("connected_pathways", []),
            })
        
        return {
            "gene_count": len(gene_list),
            "pathway_source": pathway_source,
            "p_value_cutoff": p_value_cutoff,
            "use_network": use_network,
            "enriched_pathway_count": len(enriched_pathways),
            "enriched_pathways": enriched_pathways,
        }

    async def get_pathway_communities(
        self, 
        pathway_ids: Optional[List[str]] = None,
        min_community_size: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Detect pathway communities (modules) in the pathway network.
        
        Args:
            pathway_ids: Optional list of pathway IDs (if None, use all pathways)
            min_community_size: Minimum number of pathways per community
            
        Returns:
            Pathway communities with member pathways
        """
        url = f"{self.BASE}/communities"
        params = {"min_size": min_community_size}
        
        if pathway_ids:
            json_body = {"pathway_ids": pathway_ids}
            data, meta = await self._cached_post(url, json_body=json_body, extra_key=str(params))
        else:
            data, meta = await self._cached_get(url, params=params)
        
        if not data:
            return None
        
        communities = []
        community_list = data.get("communities", [])
        
        for community in community_list:
            communities.append({
                "community_id": community.get("id"),
                "community_name": community.get("name"),
                "pathway_count": community.get("pathway_count"),
                "pathways": community.get("pathways", []),
                "functional_theme": community.get("functional_theme"),
                "modularity_score": community.get("modularity_score"),
            })
        
        return {
            "community_count": len(communities),
            "min_community_size": min_community_size,
            "communities": communities,
        }

    async def get_pathway_hierarchy(
        self, 
        pathway_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get hierarchical relationships for a pathway.
        
        Args:
            pathway_id: PathwayNet pathway ID
            
        Returns:
            Parent and child pathways in hierarchy
        """
        url = f"{self.BASE}/hierarchy/{pathway_id}"
        
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        return {
            "pathway_id": pathway_id,
            "parent_pathways": data.get("parents", []),
            "child_pathways": data.get("children", []),
            "level": data.get("level"),
            "url": f"https://pathwaynet.org/pathway/{pathway_id}"
        }

    async def search_by_genes(
        self, 
        gene_list: List[str],
        min_overlap: int = 2,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for pathways containing specific genes.
        
        Args:
            gene_list: List of gene symbols
            min_overlap: Minimum number of genes that must be in pathway
            limit: Maximum number of results
            
        Returns:
            List of matching pathways
        """
        url = f"{self.BASE}/pathways/by-genes"
        json_body = {
            "genes": gene_list,
            "min_overlap": min_overlap,
            "limit": min(limit, 50)
        }
        
        data, meta = await self._cached_post(url, json_body=json_body)
        if not data:
            return []
        
        results: List[Dict[str, Any]] = []
        pathways = data.get("pathways", [])
        
        for pathway in pathways[:limit]:
            pathway_id = pathway.get("pathway_id", "")
            pathway_name = pathway.get("name", "")
            
            results.append({
                "id": pathway_id,
                "entity_type": "pathway",
                "canonical_name": pathway_name,
                "name": pathway_name,
                "description": pathway.get("description", ""),
                "overlap_size": pathway.get("overlap_size"),
                "pathway_size": pathway.get("pathway_size"),
                "overlap_genes": pathway.get("overlap_genes", []),
                "source": self.name,
                "url": f"https://pathwaynet.org/pathway/{pathway_id}",
                "provenance": [self._prov(
                    url=f"https://pathwaynet.org/pathway/{pathway_id}",
                    ext_id=pathway_id,
                    confidence=0.88,
                    reasoning=f"PathwayNet pathway with {pathway.get('overlap_size')} matching genes"
                ).to_dict()],
            })
        
        return results

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records for pathway data.
        
        Args:
            entity_id: PathwayNet pathway ID
            
        Returns:
            List of evidence records
        """
        pathway_data = await self.fetch_by_id(entity_id)
        if not pathway_data:
            return []
        
        evidence_items = []
        
        # Add pathway evidence
        evidence_items.append({
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "pathway",
            "confidence": 0.90,
            "gene_count": pathway_data.get("gene_count"),
            "url": pathway_data.get("url"),
            "provenance": self._prov(
                url=pathway_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.90,
                reasoning="PathwayNet pathway with gene annotations"
            ).to_dict()
        })
        
        # Add crosstalk evidence
        crosstalk = await self.get_pathway_crosstalk(entity_id, limit=20)
        if crosstalk and crosstalk.get("crosstalk_count", 0) > 0:
            evidence_items.append({
                "source": self.name,
                "entity_id": entity_id,
                "evidence_type": "pathway_crosstalk",
                "confidence": 0.85,
                "crosstalk_count": crosstalk["crosstalk_count"],
                "url": crosstalk.get("url"),
                "provenance": self._prov(
                    url=crosstalk.get("url", ""),
                    ext_id=entity_id,
                    confidence=0.85,
                    reasoning=f"PathwayNet pathway crosstalk ({crosstalk['crosstalk_count']} interactions)"
                ).to_dict()
            })
        
        return evidence_items
