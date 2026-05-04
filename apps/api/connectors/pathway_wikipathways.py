"""WikiPathways connector for community-curated pathway data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class WikiPathwaysConnector(BaseConnector):
    """
    WikiPathways connector for community-curated biological pathways.
    
    WikiPathways (https://www.wikipathways.org) is an open, collaborative platform
    for biological pathway curation. It provides pathways for multiple species with
    community contributions and regular updates.
    
    API: RESTful web services at webservice.wikipathways.org
    No authentication required (free public API).
    """
    
    name = "WikiPathways"
    BASE = "https://webservice.wikipathways.org"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 2.0  # Conservative rate limit
    rate_limit_burst = 4
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
        url = f"{self.BASE}/findPathwaysByText"
        params = {
            "query": query,
            "species": "Homo sapiens",
            "format": "json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "result" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        pathways = data["result"] if isinstance(data["result"], list) else [data["result"]]
        
        for pathway in pathways[:limit]:
            pathway_id = pathway.get("id", "")
            pathway_name = pathway.get("name", query)
            
            results.append({
                "id": pathway_id,
                "entity_type": "pathway",
                "canonical_name": pathway_name,
                "name": pathway_name,
                "description": strip_html(pathway.get("description", "")),
                "species": pathway.get("species", "Homo sapiens"),
                "revision": pathway.get("revision"),
                "url": pathway.get("url", f"https://www.wikipathways.org/pathways/{pathway_id}"),
                "source": self.name,
                "provenance": [self._prov(
                    url=pathway.get("url", f"https://www.wikipathways.org/pathways/{pathway_id}"),
                    ext_id=pathway_id,
                    confidence=0.88,
                    reasoning="WikiPathways community-curated pathway"
                ).to_dict()],
            })
        
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed pathway data by WikiPathways ID.
        
        Args:
            entity_id: WikiPathways identifier (e.g., WP4868)
            
        Returns:
            Detailed pathway record
        """
        url = f"{self.BASE}/getPathwayInfo"
        params = {
            "pwId": entity_id,
            "format": "json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "pathwayInfo" not in data:
            return None
        
        pathway_info = data["pathwayInfo"]
        pathway_name = pathway_info.get("name", entity_id)
        
        return {
            "id": entity_id,
            "entity_type": "pathway",
            "canonical_name": pathway_name,
            "name": pathway_name,
            "description": strip_html(pathway_info.get("description", "")),
            "species": pathway_info.get("species", "Homo sapiens"),
            "revision": pathway_info.get("revision"),
            "url": pathway_info.get("url", f"https://www.wikipathways.org/pathways/{entity_id}"),
            "source": self.name,
            "provenance": [self._prov(
                url=pathway_info.get("url", f"https://www.wikipathways.org/pathways/{entity_id}"),
                ext_id=entity_id,
                confidence=0.88,
                reasoning="WikiPathways community-curated pathway with detailed annotations"
            ).to_dict()],
        }

    async def get_pathway_genes(
        self, 
        pathway_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get all genes in a pathway.
        
        Args:
            pathway_id: WikiPathways identifier
            
        Returns:
            List of genes in the pathway
        """
        url = f"{self.BASE}/getXrefList"
        params = {
            "pwId": pathway_id,
            "code": "L",  # Entrez Gene
            "format": "json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "xrefs" not in data:
            return None
        
        genes = []
        xrefs = data["xrefs"] if isinstance(data["xrefs"], list) else [data["xrefs"]]
        
        for xref in xrefs:
            genes.append({
                "gene_id": xref.get("id"),
                "gene_symbol": xref.get("name"),
                "database": xref.get("dataSource"),
            })
        
        return {
            "pathway_id": pathway_id,
            "gene_count": len(genes),
            "genes": genes,
            "url": f"https://www.wikipathways.org/pathways/{pathway_id}"
        }

    async def search_by_gene(
        self, 
        gene_symbol: str,
        species: str = "Homo sapiens"
    ) -> List[Dict[str, Any]]:
        """
        Find pathways containing a specific gene.
        
        Args:
            gene_symbol: Gene symbol (e.g., TP53, EGFR)
            species: Organism name
            
        Returns:
            List of pathways containing the gene
        """
        url = f"{self.BASE}/findPathwaysByXref"
        params = {
            "ids": gene_symbol,
            "codes": "L",  # Entrez Gene
            "format": "json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "result" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        pathways = data["result"] if isinstance(data["result"], list) else [data["result"]]
        
        for pathway in pathways:
            if pathway.get("species") == species:
                pathway_id = pathway.get("id", "")
                pathway_name = pathway.get("name", "")
                
                results.append({
                    "id": pathway_id,
                    "entity_type": "pathway",
                    "canonical_name": pathway_name,
                    "name": pathway_name,
                    "description": "",
                    "species": pathway.get("species"),
                    "url": pathway.get("url", f"https://www.wikipathways.org/pathways/{pathway_id}"),
                    "source": self.name,
                    "provenance": [self._prov(
                        url=pathway.get("url", ""),
                        ext_id=pathway_id,
                        confidence=0.85,
                        reasoning=f"WikiPathways pathway containing {gene_symbol}"
                    ).to_dict()],
                })
        
        return results

    async def get_pathway_ontology_tags(
        self, 
        pathway_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get ontology tags for a pathway.
        
        Args:
            pathway_id: WikiPathways identifier
            
        Returns:
            Ontology annotations
        """
        url = f"{self.BASE}/getOntologyTermsByPathway"
        params = {
            "pwId": pathway_id,
            "format": "json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "terms" not in data:
            return None
        
        ontology_terms = []
        terms = data["terms"] if isinstance(data["terms"], list) else [data["terms"]]
        
        for term in terms:
            ontology_terms.append({
                "term_id": term.get("id"),
                "term_name": term.get("name"),
                "ontology": term.get("ontology"),
            })
        
        return {
            "pathway_id": pathway_id,
            "ontology_term_count": len(ontology_terms),
            "ontology_terms": ontology_terms,
            "url": f"https://www.wikipathways.org/pathways/{pathway_id}"
        }

    async def get_pathway_by_ontology(
        self, 
        ontology_term: str,
        species: str = "Homo sapiens"
    ) -> List[Dict[str, Any]]:
        """
        Find pathways by ontology term.
        
        Args:
            ontology_term: Ontology term ID (e.g., PW:0000013)
            species: Organism name
            
        Returns:
            List of pathways with the ontology annotation
        """
        url = f"{self.BASE}/getPathwaysByOntologyTerm"
        params = {
            "term": ontology_term,
            "format": "json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "result" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        pathways = data["result"] if isinstance(data["result"], list) else [data["result"]]
        
        for pathway in pathways:
            if pathway.get("species") == species:
                pathway_id = pathway.get("id", "")
                pathway_name = pathway.get("name", "")
                
                results.append({
                    "id": pathway_id,
                    "entity_type": "pathway",
                    "canonical_name": pathway_name,
                    "name": pathway_name,
                    "description": "",
                    "species": pathway.get("species"),
                    "url": pathway.get("url", f"https://www.wikipathways.org/pathways/{pathway_id}"),
                    "source": self.name,
                    "provenance": [self._prov(
                        url=pathway.get("url", ""),
                        ext_id=pathway_id,
                        confidence=0.87,
                        reasoning=f"WikiPathways pathway annotated with {ontology_term}"
                    ).to_dict()],
                })
        
        return results

    async def get_pathway_history(
        self, 
        pathway_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get revision history for a pathway.
        
        Args:
            pathway_id: WikiPathways identifier
            
        Returns:
            Pathway revision history
        """
        url = f"{self.BASE}/getPathwayHistory"
        params = {
            "pwId": pathway_id,
            "format": "json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "history" not in data:
            return None
        
        revisions = []
        history = data["history"] if isinstance(data["history"], list) else [data["history"]]
        
        for revision in history:
            revisions.append({
                "revision": revision.get("revision"),
                "timestamp": revision.get("timestamp"),
                "user": revision.get("user"),
                "comment": revision.get("comment"),
            })
        
        return {
            "pathway_id": pathway_id,
            "revision_count": len(revisions),
            "revisions": revisions,
            "url": f"https://www.wikipathways.org/pathways/{pathway_id}"
        }

    async def get_recently_changed_pathways(
        self, 
        timestamp: str,
        species: str = "Homo sapiens"
    ) -> List[Dict[str, Any]]:
        """
        Get pathways changed since a timestamp.
        
        Args:
            timestamp: ISO format timestamp (e.g., 20240101000000)
            species: Organism name
            
        Returns:
            List of recently changed pathways
        """
        url = f"{self.BASE}/getRecentChanges"
        params = {
            "timestamp": timestamp,
            "format": "json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "pathways" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        pathways = data["pathways"] if isinstance(data["pathways"], list) else [data["pathways"]]
        
        for pathway in pathways:
            if pathway.get("species") == species:
                pathway_id = pathway.get("id", "")
                pathway_name = pathway.get("name", "")
                
                results.append({
                    "id": pathway_id,
                    "entity_type": "pathway",
                    "canonical_name": pathway_name,
                    "name": pathway_name,
                    "description": "",
                    "species": pathway.get("species"),
                    "revision": pathway.get("revision"),
                    "url": pathway.get("url", f"https://www.wikipathways.org/pathways/{pathway_id}"),
                    "source": self.name,
                    "provenance": [self._prov(
                        url=pathway.get("url", ""),
                        ext_id=pathway_id,
                        confidence=0.88,
                        reasoning="WikiPathways recently updated pathway"
                    ).to_dict()],
                })
        
        return results

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records for pathway data.
        
        Args:
            entity_id: WikiPathways identifier
            
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
            "confidence": 0.88,
            "url": pathway_data.get("url"),
            "provenance": self._prov(
                url=pathway_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.88,
                reasoning="WikiPathways community-curated pathway"
            ).to_dict()
        })
        
        # Add gene evidence
        genes = await self.get_pathway_genes(entity_id)
        if genes and genes.get("gene_count", 0) > 0:
            evidence_items.append({
                "source": self.name,
                "entity_id": entity_id,
                "evidence_type": "pathway_genes",
                "confidence": 0.85,
                "gene_count": genes["gene_count"],
                "url": genes.get("url"),
                "provenance": self._prov(
                    url=genes.get("url", ""),
                    ext_id=entity_id,
                    confidence=0.85,
                    reasoning=f"WikiPathways pathway with {genes['gene_count']} genes"
                ).to_dict()
            })
        
        return evidence_items
