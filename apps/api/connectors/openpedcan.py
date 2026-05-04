"""OpenPedCan connector — pediatric cancer variant and expression data.

Access to pediatric cancer genomics data from the OpenPedCan project
(Children's Hospital of Philadelphia / Broad Institute).
API Reference: https://pedcbioportal.kidsfirstdrc.org/api/swagger-ui.html
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class OpenPedCanConnector(BaseConnector):
    """OpenPedCan pediatric cancer genomics data via cBioPortal-compatible API."""

    name = "openpedcan"
    BASE_URL = "https://pedcbioportal.kidsfirstdrc.org/api/v2"
    cache_ttl = 86400 * 2
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search pediatric cancer studies and gene-level data."""
        # Search cancer studies
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/studies",
            params={"keyword": query, "pageSize": min(limit, 500), "pageNumber": 0, "direction": "ASC"},
        )
        if not data or not isinstance(data, list):
            return []
        results = []
        for study in data[:limit]:
            study_id = study.get("studyId", "")
            results.append({
                "id": study_id,
                "entity_type": "cancer_study",
                "canonical_name": study.get("name", study_id),
                "description": study.get("description", ""),
                "cancer_type": study.get("cancerType", {}).get("name", ""),
                "reference_genome": study.get("referenceGenome", ""),
                "sample_count": study.get("allSampleCount", 0),
                "public": study.get("publicStudy", False),
                "source_db": "OpenPedCan",
                "url": f"https://pedcbioportal.kidsfirstdrc.org/study/summary?id={study_id}",
                "provenance": [self._prov(
                    url=f"https://pedcbioportal.kidsfirstdrc.org/study/summary?id={study_id}",
                    ext_id=study_id,
                    confidence=0.90,
                    reasoning="OpenPedCan pediatric cancer cohort",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, study_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed study metadata."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/studies/{study_id}"
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "id": study_id,
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "cancer_type": data.get("cancerType", {}).get("name", ""),
            "short_name": data.get("shortName", ""),
            "reference_genome": data.get("referenceGenome", ""),
            "sample_count": data.get("allSampleCount", 0),
            "source_db": "OpenPedCan",
        }

    async def get_gene_mutations(self, study_id: str, gene_symbol: str) -> List[Dict[str, Any]]:
        """Get mutation frequencies for a gene in a pediatric study."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/molecular-profiles/{study_id}_mutations/mutations",
            params={"sampleListId": f"{study_id}_all", "geneId": gene_symbol},
            extra_key=study_id + gene_symbol,
        )
        if not data or not isinstance(data, list):
            return []
        mutations = []
        for mut in data[:100]:
            mutations.append({
                "gene_symbol": mut.get("gene", {}).get("hugoGeneSymbol", gene_symbol),
                "mutation_type": mut.get("mutationType", ""),
                "protein_change": mut.get("proteinChange", ""),
                "chromosome": mut.get("chr", ""),
                "start_position": mut.get("startPosition", ""),
                "reference_allele": mut.get("referenceAllele", ""),
                "variant_allele": mut.get("variantAllele", ""),
                "source_db": "OpenPedCan",
            })
        return mutations
