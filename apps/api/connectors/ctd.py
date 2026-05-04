"""CTD (Comparative Toxicogenomics Database) connector.

Gene-chemical, gene-disease, and chemical-disease associations.
API Reference: http://ctdbase.org/tools/batchQuery.go
Rate Limits: ~5 req/s. No API key required.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class CTDConnector(BaseConnector):
    """CTD gene-chemical-disease associations."""

    name = "ctd"
    BASE_URL = "http://ctdbase.org/tools/batchQuery.go"
    cache_ttl = 86400 * 3
    http_timeout = 25.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search CTD for gene-disease or chemical-disease associations."""
        # gene-disease associations
        data, _meta = await self._cached_get(
            self.BASE_URL,
            params={
                "q": query,
                "inputType": "gene",
                "report": "diseases_curated",
                "format": "json",
                "perPage": min(limit, 100),
            },
        )
        if not data or not isinstance(data, list):
            return []
        results = []
        for assoc in data[:limit]:
            gene_symbol = assoc.get("GeneSymbol", "")
            disease_name = assoc.get("DiseaseName", "")
            omim_id = assoc.get("OmimIDs", "")
            results.append({
                "id": f"ctd:{gene_symbol}:{assoc.get('DiseaseID', '')}",
                "entity_type": "gene_disease_association",
                "canonical_name": f"{gene_symbol} — {disease_name}",
                "gene_symbol": gene_symbol,
                "gene_id": assoc.get("GeneID", ""),
                "disease_name": disease_name,
                "disease_id": assoc.get("DiseaseID", ""),
                "omim_ids": omim_id.split("|") if omim_id else [],
                "inference_score": assoc.get("InferenceScore", 0.0),
                "inference_genes_symbol": assoc.get("InferenceGeneSymbols", ""),
                "direct_evidence": assoc.get("DirectEvidence", ""),
                "pmids": assoc.get("PubMedIDs", "").split("|") if assoc.get("PubMedIDs") else [],
                "source_db": "CTD",
                "url": f"http://ctdbase.org/detail.go?type=disease&acc={assoc.get('DiseaseID', '')}",
                "provenance": [self._prov(
                    url=f"http://ctdbase.org/detail.go?type=gene&acc={assoc.get('GeneID', '')}",
                    ext_id=assoc.get("GeneID", ""),
                    confidence=0.85,
                    reasoning="CTD curated gene-disease association",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, gene_symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch all disease + chemical associations for a gene."""
        data, _meta = await self._cached_get(
            self.BASE_URL,
            params={
                "q": gene_symbol,
                "inputType": "gene",
                "report": "diseases_curated",
                "format": "json",
                "perPage": 200,
            },
            extra_key=gene_symbol,
        )
        if not data or not isinstance(data, list):
            return None
        return {
            "gene_symbol": gene_symbol,
            "disease_associations": data,
            "count": len(data),
            "source_db": "CTD",
        }
