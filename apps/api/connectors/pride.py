"""PRIDE Archive connector for proteomics data repository."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PRIDEConnector(BaseConnector):
    """
    PRIDE Archive connector for mass spectrometry-based proteomics data.
    
    PRIDE (PRoteomics IDEntifications) database is the world's largest data
    repository of mass spectrometry-based proteomics data and a founding member
    of the ProteomeXchange Consortium.
    
    API: RESTful web services at https://www.ebi.ac.uk/pride/ws/archive/v2
    No authentication required (free public API).
    """
    
    name = "PRIDE"
    BASE = "https://www.ebi.ac.uk/pride/ws/archive/v2"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 3.0  # Conservative rate limit
    rate_limit_burst = 5
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for proteomics projects and datasets by keyword, protein, or organism.
        
        Args:
            query: Search term (protein name, gene, organism, or keyword)
            limit: Maximum number of results to return
            
        Returns:
            List of project records with proteomics data
        """
        # PRIDE Archive search API
        url = f"{self.BASE}/search/projects"
        params = {
            "keyword": query,
            "pageSize": min(limit, 100),
            "page": 0,
            "sortDirection": "DESC",
            "sortFields": "submission_date"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        results: List[Dict[str, Any]] = []
        
        # PRIDE returns embedded results
        projects = data.get("_embedded", {}).get("projects", [])
        if not projects:
            projects = data.get("content", [])
        
        for project in projects[:limit]:
            accession = project.get("accession", "")
            title = project.get("title", "")
            description = project.get("projectDescription", "")
            organisms = project.get("organisms", [])
            instruments = project.get("instruments", [])
            submission_date = project.get("submissionDate", "")
            
            results.append({
                "id": accession,
                "entity_type": "proteomics_project",
                "canonical_name": title,
                "name": title,
                "description": strip_html(description[:500]) if description else title,
                "accession": accession,
                "organisms": organisms,
                "instruments": instruments,
                "submission_date": submission_date,
                "source": self.name,
                "url": f"https://www.ebi.ac.uk/pride/archive/projects/{accession}",
                "provenance": [self._prov(
                    url=f"https://www.ebi.ac.uk/pride/archive/projects/{accession}",
                    ext_id=accession,
                    confidence=0.95,
                    reasoning="PRIDE Archive mass spectrometry proteomics project"
                ).to_dict()],
            })
        
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed project information by PRIDE accession.
        
        Args:
            entity_id: PRIDE project accession (e.g., "PXD000001")
            
        Returns:
            Detailed project record with proteomics data
        """
        url = f"{self.BASE}/projects/{entity_id}"
        
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        accession = data.get("accession", entity_id)
        title = data.get("title", "")
        description = data.get("projectDescription", "")
        organisms = data.get("organisms", [])
        instruments = data.get("instruments", [])
        submission_date = data.get("submissionDate", "")
        publication_date = data.get("publicationDate", "")
        
        return {
            "id": accession,
            "entity_type": "proteomics_project",
            "canonical_name": title,
            "name": title,
            "description": strip_html(description) if description else title,
            "accession": accession,
            "organisms": organisms,
            "instruments": instruments,
            "submission_date": submission_date,
            "publication_date": publication_date,
            "source": self.name,
            "url": f"https://www.ebi.ac.uk/pride/archive/projects/{accession}",
            "provenance": [self._prov(
                url=f"https://www.ebi.ac.uk/pride/archive/projects/{accession}",
                ext_id=accession,
                confidence=0.95,
                reasoning="PRIDE Archive proteomics project metadata"
            ).to_dict()],
        }

    async def get_project_files(self, accession: str) -> Optional[Dict[str, Any]]:
        """
        Get file list for a PRIDE project.
        
        Args:
            accession: PRIDE project accession
            
        Returns:
            Project files with metadata
        """
        url = f"{self.BASE}/files/byProject"
        params = {
            "accession": accession,
            "pageSize": 100,
            "page": 0
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        files = data.get("_embedded", {}).get("files", [])
        if not files:
            files = data.get("content", [])
        
        return {
            "accession": accession,
            "files": [{
                "fileName": f.get("fileName", ""),
                "fileSize": f.get("fileSizeBytes", 0),
                "fileCategory": f.get("fileCategory", {}).get("name", ""),
                "publicFileLocations": f.get("publicFileLocations", [])
            } for f in files]
        }

    async def search_proteins(self, protein_query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for proteins across PRIDE projects.
        
        Args:
            protein_query: Protein accession or name
            limit: Maximum number of results
            
        Returns:
            List of protein identifications across projects
        """
        # Search projects mentioning the protein
        url = f"{self.BASE}/search/projects"
        params = {
            "keyword": protein_query,
            "filter": "proteins",
            "pageSize": min(limit, 100),
            "page": 0
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        results: List[Dict[str, Any]] = []
        projects = data.get("_embedded", {}).get("projects", [])
        
        for project in projects[:limit]:
            accession = project.get("accession", "")
            title = project.get("title", "")
            
            results.append({
                "id": f"{accession}_{protein_query}",
                "entity_type": "protein_identification",
                "canonical_name": f"{protein_query} in {accession}",
                "name": f"{protein_query} identification",
                "description": f"Protein {protein_query} identified in {title}",
                "protein_query": protein_query,
                "project_accession": accession,
                "project_title": title,
                "source": self.name,
                "url": f"https://www.ebi.ac.uk/pride/archive/projects/{accession}",
                "provenance": [self._prov(
                    url=f"https://www.ebi.ac.uk/pride/archive/projects/{accession}",
                    ext_id=accession,
                    confidence=0.90,
                    reasoning="Protein identification in PRIDE proteomics project"
                ).to_dict()],
            })
        
        return results

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records for a project from PRIDE Archive.
        
        Args:
            entity_id: PRIDE project accession
            
        Returns:
            List of evidence records with proteomics data
        """
        project_data = await self.fetch_by_id(entity_id)
        if not project_data:
            return []
        
        evidence_items = []
        
        # Project metadata evidence
        evidence_items.append({
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "proteomics_project",
            "title": project_data.get("name"),
            "organisms": project_data.get("organisms"),
            "instruments": project_data.get("instruments"),
            "submission_date": project_data.get("submission_date"),
            "confidence": 0.95,
            "url": project_data.get("url"),
            "provenance": self._prov(
                url=project_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.95,
                reasoning="PRIDE Archive proteomics project with mass spectrometry data"
            ).to_dict()
        })
        
        # File evidence
        files_data = await self.get_project_files(entity_id)
        if files_data and files_data.get("files"):
            evidence_items.append({
                "source": self.name,
                "entity_id": entity_id,
                "evidence_type": "proteomics_files",
                "file_count": len(files_data["files"]),
                "files": files_data["files"][:10],  # Limit to first 10 files
                "confidence": 0.95,
                "url": project_data.get("url"),
                "provenance": self._prov(
                    url=project_data.get("url", ""),
                    ext_id=entity_id,
                    confidence=0.95,
                    reasoning="PRIDE Archive raw proteomics data files"
                ).to_dict()
            })
        
        return evidence_items
