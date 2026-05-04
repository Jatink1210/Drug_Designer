"""Reactome connector for curated pathway data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ReactomeConnector(BaseConnector):
    """
    Reactome connector for manually curated biological pathways.
    
    Reactome (https://reactome.org) is a free, open-source, curated and peer-reviewed
    pathway database covering human biological processes including metabolism, signaling,
    gene expression, and disease pathways.
    
    API: RESTful web services at reactome.org
    No authentication required (free public API).
    """
    
    name = "Reactome"
    BASE = "https://reactome.org/ContentService"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 3.0  # Conservative rate limit
    rate_limit_burst = 6
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for pathways by name or description.
        
        Args:
            query: Pathway name or keyword
            limit: Maximum number of results to return
            
        Returns:
            List of pathway records
        """
        url = f"{self.BASE}/search/query"
        params = {
            "query": query,
            "species": "Homo sapiens",
            "types": "Pathway"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "results" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        
        for entry in data["results"][:limit]:
            pathway_id = entry.get("stId", entry.get("dbId", ""))
            pathway_name = entry.get("name", query)
            
            results.append({
                "id": pathway_id,
                "entity_type": "pathway",
                "canonical_name": pathway_name,
                "name": pathway_name,
                "description": strip_html(entry.get("summation", "")),
                "species": entry.get("species", "Homo sapiens"),
                "pathway_type": entry.get("type", "Pathway"),
                "source": self.name,
                "url": f"https://reactome.org/content/detail/{pathway_id}",
                "provenance": [self._prov(
                    url=f"https://reactome.org/content/detail/{pathway_id}",
                    ext_id=pathway_id,
                    confidence=0.95,
                    reasoning="Reactome manually curated pathway"
                ).to_dict()],
            })
        
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed pathway data by Reactome ID.
        
        Args:
            entity_id: Reactome stable identifier (e.g., R-HSA-109582)
            
        Returns:
            Detailed pathway record
        """
        url = f"{self.BASE}/data/query/{entity_id}"
        
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        pathway_name = data.get("displayName", entity_id)
        
        return {
            "id": entity_id,
            "entity_type": "pathway",
            "canonical_name": pathway_name,
            "name": pathway_name,
            "description": strip_html(data.get("summation", [{}])[0].get("text", "") if data.get("summation") else ""),
            "species": data.get("speciesName", "Homo sapiens"),
            "pathway_type": data.get("schemaClass", "Pathway"),
            "has_diagram": data.get("hasDiagram", False),
            "source": self.name,
            "url": f"https://reactome.org/content/detail/{entity_id}",
            "provenance": [self._prov(
                url=f"https://reactome.org/content/detail/{entity_id}",
                ext_id=entity_id,
                confidence=0.95,
                reasoning="Reactome manually curated pathway with detailed annotations"
            ).to_dict()],
        }

    async def get_pathway_participants(
        self, 
        pathway_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get all molecular participants in a pathway.
        
        Args:
            pathway_id: Reactome stable identifier
            
        Returns:
            List of proteins, genes, and molecules in pathway
        """
        url = f"{self.BASE}/data/participants/{pathway_id}"
        
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        participants = []
        participant_list = data if isinstance(data, list) else [data]
        
        for participant in participant_list:
            participants.append({
                "id": participant.get("stId", participant.get("dbId")),
                "name": participant.get("displayName"),
                "type": participant.get("schemaClass"),
                "gene_names": participant.get("geneName", []),
                "uniprot_ids": participant.get("identifier", []),
            })
        
        return {
            "pathway_id": pathway_id,
            "participant_count": len(participants),
            "participants": participants,
            "url": f"https://reactome.org/content/detail/{pathway_id}"
        }

    async def get_pathway_hierarchy(
        self, 
        pathway_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get pathway hierarchy (parent and child pathways).
        
        Args:
            pathway_id: Reactome stable identifier
            
        Returns:
            Hierarchical pathway relationships
        """
        url = f"{self.BASE}/data/pathway/{pathway_id}/containedEvents"
        
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        child_pathways = []
        events = data if isinstance(data, list) else [data]
        
        for event in events:
            if event.get("schemaClass") == "Pathway":
                child_pathways.append({
                    "pathway_id": event.get("stId"),
                    "pathway_name": event.get("displayName"),
                    "has_diagram": event.get("hasDiagram", False),
                })
        
        return {
            "pathway_id": pathway_id,
            "child_pathway_count": len(child_pathways),
            "child_pathways": child_pathways,
            "url": f"https://reactome.org/content/detail/{pathway_id}"
        }

    async def get_pathway_diagram(
        self, 
        pathway_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get pathway diagram information.
        
        Args:
            pathway_id: Reactome stable identifier
            
        Returns:
            Pathway diagram metadata and URL
        """
        url = f"{self.BASE}/data/pathway/{pathway_id}/containedEvents"
        
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        return {
            "pathway_id": pathway_id,
            "diagram_url": f"https://reactome.org/ContentService/exporter/diagram/{pathway_id}.png",
            "svg_url": f"https://reactome.org/ContentService/exporter/diagram/{pathway_id}.svg",
            "sbgn_url": f"https://reactome.org/ContentService/exporter/sbgn/{pathway_id}.sbgn",
            "url": f"https://reactome.org/PathwayBrowser/#/{pathway_id}"
        }

    async def analyze_gene_list(
        self, 
        gene_list: List[str],
        p_value_cutoff: float = 0.05,
        include_disease: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Perform pathway over-representation analysis.
        
        Args:
            gene_list: List of gene symbols or UniProt IDs
            p_value_cutoff: P-value threshold
            include_disease: Include disease pathways in results
            
        Returns:
            Over-represented pathways with statistics
        """
        url = f"{self.BASE}/analysis/identifiers"
        params = {
            "pageSize": 100,
            "page": 1,
            "sortBy": "ENTITIES_PVALUE",
            "order": "ASC",
            "resource": "TOTAL",
            "pValue": p_value_cutoff,
            "includeDisease": str(include_disease).lower()
        }
        
        # Post gene list
        gene_data = "\n".join(gene_list)
        data, meta = await self._cached_post(url, json_body={"identifiers": gene_data}, extra_key=str(params))
        
        if not data or "pathways" not in data:
            return None
        
        enriched_pathways = []
        for pathway in data["pathways"]:
            enriched_pathways.append({
                "pathway_id": pathway.get("stId"),
                "pathway_name": pathway.get("name"),
                "p_value": pathway.get("entities", {}).get("pValue"),
                "fdr": pathway.get("entities", {}).get("fdr"),
                "found_entities": pathway.get("entities", {}).get("found"),
                "total_entities": pathway.get("entities", {}).get("total"),
                "ratio": pathway.get("entities", {}).get("ratio"),
                "species": pathway.get("species", {}).get("name"),
            })
        
        return {
            "gene_count": len(gene_list),
            "p_value_cutoff": p_value_cutoff,
            "include_disease": include_disease,
            "enriched_pathway_count": len(enriched_pathways),
            "enriched_pathways": enriched_pathways,
        }

    async def search_by_gene(
        self, 
        gene_symbol: str
    ) -> List[Dict[str, Any]]:
        """
        Find pathways containing a specific gene.
        
        Args:
            gene_symbol: Gene symbol (e.g., TP53, EGFR)
            
        Returns:
            List of pathways containing the gene
        """
        url = f"{self.BASE}/data/pathways/low/entity/{gene_symbol}"
        params = {"species": "Homo sapiens"}
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        results: List[Dict[str, Any]] = []
        pathways = data if isinstance(data, list) else [data]
        
        for pathway in pathways:
            pathway_id = pathway.get("stId", "")
            pathway_name = pathway.get("displayName", "")
            
            results.append({
                "id": pathway_id,
                "entity_type": "pathway",
                "canonical_name": pathway_name,
                "name": pathway_name,
                "description": "",
                "has_diagram": pathway.get("hasDiagram", False),
                "source": self.name,
                "url": f"https://reactome.org/content/detail/{pathway_id}",
                "provenance": [self._prov(
                    url=f"https://reactome.org/content/detail/{pathway_id}",
                    ext_id=pathway_id,
                    confidence=0.93,
                    reasoning=f"Reactome pathway containing {gene_symbol}"
                ).to_dict()],
            })
        
        return results

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records for pathway data.
        
        Args:
            entity_id: Reactome stable identifier
            
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
            "confidence": 0.95,
            "url": pathway_data.get("url"),
            "provenance": self._prov(
                url=pathway_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.95,
                reasoning="Reactome manually curated and peer-reviewed pathway"
            ).to_dict()
        })
        
        # Add participant evidence
        participants = await self.get_pathway_participants(entity_id)
        if participants and participants.get("participant_count", 0) > 0:
            evidence_items.append({
                "source": self.name,
                "entity_id": entity_id,
                "evidence_type": "pathway_participants",
                "confidence": 0.93,
                "participant_count": participants["participant_count"],
                "url": participants.get("url"),
                "provenance": self._prov(
                    url=participants.get("url", ""),
                    ext_id=entity_id,
                    confidence=0.93,
                    reasoning=f"Reactome pathway with {participants['participant_count']} molecular participants"
                ).to_dict()
            })
        
        return evidence_items
