"""OpenTargets Genetics connector.

Provides GWAS loci, V2G (variant-to-gene) scores, and colocalization data
from the OpenTargets Genetics portal (separate from main OpenTargets Platform).
API Reference: https://genetics-docs.opentargets.org/data-access/graphql-api
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)

# GraphQL endpoint
_GQL_URL = "https://api.genetics.opentargets.org/graphql"

_GENE_LOCI_QUERY = """
query GeneAssociatedStudies($geneId: String!, $pageIndex: Int!, $pageSize: Int!) {
  geneInfo(geneId: $geneId) {
    id
    symbol
    description
  }
  gwasStudies: studiesAndLeadVariantsForGeneByL2G(geneId: $geneId) {
    study { studyId traitReported pubDate pubTitle pmid }
    variant { id rsId }
    yProbaModel
    yProbaDistance
    yProbaInteraction
    yProbaMolecularQTL
    yProbaPathogenicity
  }
}
"""

_VARIANT_QUERY = """
query VariantInfo($variantId: String!) {
  variantInfo(variantId: $variantId) {
    id
    rsId
    chromosome
    position
    refAllele
    altAllele
    nearestGene { id symbol }
    nearestGeneDistance
    nearestCodingGene { id symbol }
    nearestCodingGeneDistance
    gnomadAFR
    gnomadAMR
    gnomadASJ
    gnomadEAS
    gnomadFIN
    gnomadNFE
    gnomadOTH
    gnomadSAS
  }
}
"""


class OpenTargetsGeneticsConnector(BaseConnector):
    """OpenTargets Genetics GraphQL API — GWAS loci, V2G scores, colocalization."""

    name = "opentargets_genetics"
    BASE_URL = _GQL_URL
    cache_ttl = 86400 * 2
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search GWAS studies by trait or gene symbol."""
        data, _meta = await self._cached_post(
            _GQL_URL,
            json_body={
                "query": _GENE_LOCI_QUERY,
                "variables": {"geneId": query.upper(), "pageIndex": 0, "pageSize": limit},
            },
            extra_key=query + str(limit),
        )
        if not data or not isinstance(data, dict):
            return []
        rows = data.get("data", {}).get("gwasStudies", []) or []
        results = []
        for row in rows[:limit]:
            study = row.get("study", {}) or {}
            variant = row.get("variant", {}) or {}
            results.append({
                "id": study.get("studyId", ""),
                "entity_type": "gwas_study",
                "canonical_name": study.get("traitReported", ""),
                "description": study.get("pubTitle", ""),
                "variant_id": variant.get("id", ""),
                "variant_rsid": variant.get("rsId", ""),
                "l2g_score": row.get("yProbaModel", 0.0),
                "distance_score": row.get("yProbaDistance", 0.0),
                "pmid": study.get("pmid", ""),
                "pub_date": study.get("pubDate", ""),
                "source_db": "OpenTargets Genetics",
                "url": f"https://genetics.opentargets.org/study/{study.get('studyId', '')}",
                "provenance": [self._prov(
                    url=f"https://genetics.opentargets.org/study/{study.get('studyId', '')}",
                    ext_id=study.get("studyId", ""),
                    confidence=float(row.get("yProbaModel", 0.5)),
                    reasoning="OpenTargets Genetics L2G score",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, variant_id: str) -> Optional[Dict[str, Any]]:
        """Fetch variant info by variant ID (chr_pos_ref_alt)."""
        data, _meta = await self._cached_post(
            _GQL_URL,
            json_body={
                "query": _VARIANT_QUERY,
                "variables": {"variantId": variant_id},
            },
            extra_key=variant_id,
        )
        if not data or not isinstance(data, dict):
            return None
        return data.get("data", {}).get("variantInfo")
