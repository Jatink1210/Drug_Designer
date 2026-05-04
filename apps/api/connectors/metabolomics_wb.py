"""Metabolomics Workbench connector.

Access metabolomics studies, compounds, and reference data.
API Reference: https://www.metabolomicsworkbench.org/tools/MWRestAPIv1.0.pdf
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class MetabolomicsWorkbenchConnector(BaseConnector):
    """Query Metabolomics Workbench for studies and metabolite reference data."""

    name = "metabolomics_wb"
    BASE_URL = "https://www.metabolomicsworkbench.org/rest"
    cache_ttl = 86400 * 3
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search metabolomics studies by title or species."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/study/study_title/{query}/summary",
        )
        if not data:
            return []
        if isinstance(data, dict):
            # Single study returned
            data = [data]
        if not isinstance(data, list):
            return []
        results = []
        for study in data[:limit]:
            study_id = study.get("study_id", "")
            results.append({
                "id": study_id,
                "entity_type": "metabolomics_study",
                "canonical_name": study.get("study_title", study_id),
                "description": study.get("study_summary", ""),
                "study_id": study_id,
                "institute": study.get("institute", ""),
                "department": study.get("department", ""),
                "laboratory": study.get("laboratory", ""),
                "pi_first_name": study.get("last_name", ""),
                "species": study.get("subject_species", ""),
                "sample_source": study.get("subject_source", ""),
                "doi": study.get("doi", ""),
                "analysis_type": study.get("analysis_type", ""),
                "metabolite_count": study.get("metabolite_count", 0),
                "source_db": "Metabolomics Workbench",
                "url": f"https://www.metabolomicsworkbench.org/data/DRCCStudySummary.php?Mode=SetupStudyAnalysis&StudyID={study_id}",
                "provenance": [self._prov(
                    url=f"https://www.metabolomicsworkbench.org/rest/study/study_id/{study_id}/summary",
                    ext_id=study_id,
                    confidence=0.85,
                    reasoning="Metabolomics Workbench public metabolomics study",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, study_id: str) -> Optional[Dict[str, Any]]:
        """Fetch metabolomics study details by study ID (e.g., ST000001)."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/study/study_id/{study_id}/summary"
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "study_id": study_id,
            "title": data.get("study_title", ""),
            "summary": data.get("study_summary", ""),
            "institute": data.get("institute", ""),
            "species": data.get("subject_species", ""),
            "sample_count": data.get("sample_count", 0),
            "analysis_type": data.get("analysis_type", ""),
            "source_db": "Metabolomics Workbench",
        }

    async def get_compound(self, regno: str) -> Optional[Dict[str, Any]]:
        """Get metabolite/compound reference data by MW regno."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/compound/regno/{regno}/all",
            extra_key=f"compound_{regno}",
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "regno": regno,
            "name": data.get("name", ""),
            "formula": data.get("formula", ""),
            "exactmass": data.get("exactmass", ""),
            "smiles": data.get("smiles", ""),
            "inchi": data.get("inchi", ""),
            "inchi_key": data.get("inchi_key", ""),
            "pubchem_cid": data.get("pubchem_cid", ""),
            "hmdb_id": data.get("hmdb_id", ""),
            "kegg_id": data.get("kegg_id", ""),
            "source_db": "Metabolomics Workbench",
        }
