"""ChEMBL Targets connector for protein target data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ChEMBLTargetsConnector(BaseConnector):
    """
    ChEMBL Targets connector for protein target information and drug-target relationships.
    
    ChEMBL (https://www.ebi.ac.uk/chembl/) is a manually curated database of bioactive
    molecules with drug-like properties. This connector focuses on target data including
    protein targets, target classifications, and target-compound activities.
    
    API: RESTful web services at ebi.ac.uk/chembl/api
    No authentication required (free public API).
    """
    
    name = "ChEMBL_Targets"
    BASE = "https://www.ebi.ac.uk/chembl/api/data"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 3.0  # Conservative rate limit for EBI services
    rate_limit_burst = 6
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for protein targets by name, gene symbol, or UniProt ID.
        
        Args:
            query: Target name, gene symbol, or UniProt accession
            limit: Maximum number of results to return
            
        Returns:
            List of target records with classification and activity data
        """
        url = f"{self.BASE}/target/search.json"
        params = {
            "q": query,
            "limit": min(limit, 50)
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "targets" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        
        for target in data["targets"][:limit]:
            target_chembl_id = target.get("target_chembl_id", "")
            pref_name = target.get("pref_name", "")
            target_type = target.get("target_type", "")
            organism = target.get("organism", "")
            
            # Extract UniProt accessions
            target_components = target.get("target_components", [])
            uniprot_ids = []
            gene_symbols = []
            
            for component in target_components:
                accessions = component.get("target_component_xrefs", [])
                for xref in accessions:
                    if xref.get("xref_src_db") == "UniProt":
                        uniprot_ids.append(xref.get("xref_id", ""))
                
                # Get gene symbol
                gene_name = component.get("component_synonym", "")
                if gene_name:
                    gene_symbols.append(gene_name)
            
            results.append({
                "id": target_chembl_id,
                "entity_type": "protein_target",
                "canonical_name": pref_name or target_chembl_id,
                "name": pref_name or target_chembl_id,
                "description": strip_html(target.get("pref_name", "")),
                "target_type": target_type,
                "organism": organism,
                "gene_symbols": gene_symbols,
                "uniprot_ids": uniprot_ids,
                "source": self.name,
                "url": f"https://www.ebi.ac.uk/chembl/target_report_card/{target_chembl_id}/",
                "provenance": [self._prov(
                    url=f"https://www.ebi.ac.uk/chembl/target_report_card/{target_chembl_id}/",
                    ext_id=target_chembl_id,
                    confidence=0.98,
                    reasoning="ChEMBL manually curated target data"
                ).to_dict()],
            })
        
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed target data by ChEMBL target ID.
        
        Args:
            entity_id: ChEMBL target ID (e.g., CHEMBL1824)
            
        Returns:
            Detailed target record with classification and cross-references
        """
        url = f"{self.BASE}/target/{entity_id}.json"
        
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        target_chembl_id = data.get("target_chembl_id", entity_id)
        pref_name = data.get("pref_name", "")
        target_type = data.get("target_type", "")
        organism = data.get("organism", "")
        
        # Extract detailed component information
        target_components = data.get("target_components", [])
        uniprot_ids = []
        gene_symbols = []
        protein_sequences = []
        
        for component in target_components:
            # Get UniProt cross-references
            accessions = component.get("target_component_xrefs", [])
            for xref in accessions:
                if xref.get("xref_src_db") == "UniProt":
                    uniprot_ids.append(xref.get("xref_id", ""))
            
            # Get gene symbols
            gene_name = component.get("component_synonym", "")
            if gene_name:
                gene_symbols.append(gene_name)
            
            # Get protein sequences
            sequence = component.get("sequence", "")
            if sequence:
                protein_sequences.append(sequence)
        
        return {
            "id": target_chembl_id,
            "entity_type": "protein_target",
            "canonical_name": pref_name or target_chembl_id,
            "name": pref_name or target_chembl_id,
            "description": strip_html(data.get("pref_name", "")),
            "target_type": target_type,
            "organism": organism,
            "gene_symbols": gene_symbols,
            "uniprot_ids": uniprot_ids,
            "protein_sequences": protein_sequences,
            "cross_references": data.get("cross_references", []),
            "source": self.name,
            "url": f"https://www.ebi.ac.uk/chembl/target_report_card/{target_chembl_id}/",
            "provenance": [self._prov(
                url=f"https://www.ebi.ac.uk/chembl/target_report_card/{target_chembl_id}/",
                ext_id=target_chembl_id,
                confidence=0.98,
                reasoning="ChEMBL manually curated target data with detailed annotations"
            ).to_dict()],
        }

    async def get_target_activities(
        self, 
        target_chembl_id: str,
        activity_type: Optional[str] = None,
        min_activity: Optional[float] = None,
        limit: int = 100
    ) -> Optional[Dict[str, Any]]:
        """
        Get bioactivity data for a target.
        
        Args:
            target_chembl_id: ChEMBL target ID
            activity_type: Filter by activity type (e.g., IC50, Ki, Kd, EC50)
            min_activity: Minimum activity value threshold (nM)
            limit: Maximum number of activities to return
            
        Returns:
            Bioactivity records for the target
        """
        url = f"{self.BASE}/activity.json"
        params = {
            "target_chembl_id": target_chembl_id,
            "limit": min(limit, 1000)
        }
        
        if activity_type:
            params["standard_type"] = activity_type
        
        if min_activity:
            params["standard_value__lte"] = str(min_activity)
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "activities" not in data:
            return None
        
        activities = []
        for activity in data["activities"]:
            activities.append({
                "activity_id": activity.get("activity_id"),
                "molecule_chembl_id": activity.get("molecule_chembl_id"),
                "standard_type": activity.get("standard_type"),
                "standard_value": activity.get("standard_value"),
                "standard_units": activity.get("standard_units"),
                "pchembl_value": activity.get("pchembl_value"),
                "activity_comment": activity.get("activity_comment"),
                "assay_chembl_id": activity.get("assay_chembl_id"),
                "document_chembl_id": activity.get("document_chembl_id"),
            })
        
        return {
            "target_chembl_id": target_chembl_id,
            "activity_type": activity_type,
            "min_activity": min_activity,
            "activity_count": len(activities),
            "activities": activities,
            "url": f"https://www.ebi.ac.uk/chembl/target_report_card/{target_chembl_id}/"
        }

    async def get_target_mechanisms(
        self, 
        target_chembl_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get mechanism of action data for drugs targeting this protein.
        
        Args:
            target_chembl_id: ChEMBL target ID
            
        Returns:
            Mechanism of action records
        """
        url = f"{self.BASE}/mechanism.json"
        params = {
            "target_chembl_id": target_chembl_id,
            "limit": 100
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "mechanisms" not in data:
            return None
        
        mechanisms = []
        for mechanism in data["mechanisms"]:
            mechanisms.append({
                "mechanism_id": mechanism.get("mec_id"),
                "molecule_chembl_id": mechanism.get("molecule_chembl_id"),
                "mechanism_of_action": mechanism.get("mechanism_of_action"),
                "action_type": mechanism.get("action_type"),
                "direct_interaction": mechanism.get("direct_interaction"),
                "disease_efficacy": mechanism.get("disease_efficacy"),
                "mechanism_comment": mechanism.get("mechanism_comment"),
            })
        
        return {
            "target_chembl_id": target_chembl_id,
            "mechanism_count": len(mechanisms),
            "mechanisms": mechanisms,
            "url": f"https://www.ebi.ac.uk/chembl/target_report_card/{target_chembl_id}/"
        }

    async def get_target_by_uniprot(
        self, 
        uniprot_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find ChEMBL target by UniProt accession.
        
        Args:
            uniprot_id: UniProt accession (e.g., P00533)
            
        Returns:
            ChEMBL target record
        """
        url = f"{self.BASE}/target.json"
        params = {
            "target_components__accession": uniprot_id,
            "limit": 1
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "targets" not in data or len(data["targets"]) == 0:
            return None
        
        target = data["targets"][0]
        target_chembl_id = target.get("target_chembl_id", "")
        
        # Fetch full details
        return await self.fetch_by_id(target_chembl_id)

    async def search_by_gene_symbol(
        self, 
        gene_symbol: str
    ) -> List[Dict[str, Any]]:
        """
        Search for targets by gene symbol.
        
        Args:
            gene_symbol: Gene symbol (e.g., EGFR, TP53)
            
        Returns:
            List of matching targets
        """
        # ChEMBL search supports gene symbols in the query
        return await self.search(gene_symbol, limit=20)

    async def get_target_classification(
        self, 
        target_chembl_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get protein family classification for a target.
        
        Args:
            target_chembl_id: ChEMBL target ID
            
        Returns:
            Target classification data
        """
        target_data = await self.fetch_by_id(target_chembl_id)
        if not target_data:
            return None
        
        # Extract classification from cross-references
        classifications = []
        for xref in target_data.get("cross_references", []):
            if xref.get("xref_src_db") in ["Pfam", "InterPro", "PANTHER"]:
                classifications.append({
                    "database": xref.get("xref_src_db"),
                    "id": xref.get("xref_id"),
                    "name": xref.get("xref_name", "")
                })
        
        return {
            "target_chembl_id": target_chembl_id,
            "target_type": target_data.get("target_type"),
            "organism": target_data.get("organism"),
            "classifications": classifications,
            "url": f"https://www.ebi.ac.uk/chembl/target_report_card/{target_chembl_id}/"
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records for target data from ChEMBL.
        
        Args:
            entity_id: ChEMBL target ID
            
        Returns:
            List of evidence records with bioactivity and mechanism data
        """
        target_data = await self.fetch_by_id(entity_id)
        if not target_data:
            return []
        
        evidence_items = []
        
        # Add target evidence
        evidence_items.append({
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "protein_target",
            "confidence": 0.98,
            "url": target_data.get("url"),
            "provenance": self._prov(
                url=target_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.98,
                reasoning="ChEMBL manually curated target with bioactivity data"
            ).to_dict()
        })
        
        # Add mechanism evidence if available
        mechanisms = await self.get_target_mechanisms(entity_id)
        if mechanisms and mechanisms.get("mechanism_count", 0) > 0:
            evidence_items.append({
                "source": self.name,
                "entity_id": entity_id,
                "evidence_type": "mechanism_of_action",
                "confidence": 0.95,
                "mechanism_count": mechanisms["mechanism_count"],
                "url": mechanisms.get("url"),
                "provenance": self._prov(
                    url=mechanisms.get("url", ""),
                    ext_id=entity_id,
                    confidence=0.95,
                    reasoning=f"ChEMBL mechanism of action data ({mechanisms['mechanism_count']} mechanisms)"
                ).to_dict()
            })
        
        # Add bioactivity evidence if available
        activities = await self.get_target_activities(entity_id, limit=10)
        if activities and activities.get("activity_count", 0) > 0:
            evidence_items.append({
                "source": self.name,
                "entity_id": entity_id,
                "evidence_type": "bioactivity",
                "confidence": 0.95,
                "activity_count": activities["activity_count"],
                "url": activities.get("url"),
                "provenance": self._prov(
                    url=activities.get("url", ""),
                    ext_id=entity_id,
                    confidence=0.95,
                    reasoning=f"ChEMBL bioactivity data ({activities['activity_count']} activities)"
                ).to_dict()
            })
        
        return evidence_items
