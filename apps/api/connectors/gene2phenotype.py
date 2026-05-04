"""Gene2Phenotype developmental disorder connector (F-8).

Gene2Phenotype (G2P) maps genes to developmental disorders with
confidence ratings and allelic requirement information.

API: https://www.ebi.ac.uk/gene2phenotype/api/v1/
Rate Limits: 10 req/s
Auth: None (public)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger(__name__)

G2P_BASE = "https://www.ebi.ac.uk/gene2phenotype/api/v1"


class Gene2PhenotypeConnector(BaseConnector):
    """Gene2Phenotype (G2P) developmental disorder connector.

    Provides:
    - Gene-disease associations with confidence levels
    - Allelic requirement (biallelic, monoallelic, etc.)
    - Mutation consequence types
    - DD panel, Eye panel, Skin panel, Cancer panel data
    """

    name = "gene2phenotype"
    cache_ttl = 86400 * 7  # 7 days — manually curated, infrequent updates
    rate_limit_rps = 5.0
    rate_limit_burst = 10
    http_timeout = 20.0
    max_retries = 3
    degradation_mode = "degrade"

    # G2P panels
    PANELS = ["DD", "Eye", "Skin", "Cancer", "Cardiac"]

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search G2P for gene-disease entries by gene symbol or disease name."""
        params: Dict[str, Any] = {"search": query, "page": 1, "limit": min(limit, 100)}
        url = f"{G2P_BASE}/genes"
        body, meta = await self._cached_get(url, params=params, extra_key=query)
        if not body:
            log.warning("g2p_search_failed", query=query, meta=meta)
            return []

        items = (
            body.get("results", [])
            if isinstance(body, dict)
            else body
            if isinstance(body, list)
            else []
        )
        results: List[Dict[str, Any]] = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            results.append(self._normalize(item, query=query))
        return results

    async def get_gene_entries(
        self, gene_symbol: str, panel: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all G2P entries for a specific gene symbol.

        Args:
            gene_symbol: HGNC symbol (e.g. "BRCA2")
            panel: Optional panel filter ("DD", "Eye", "Skin", "Cancer")
        """
        params: Dict[str, Any] = {"gene_symbol": gene_symbol, "limit": 100}
        if panel and panel in self.PANELS:
            params["panel"] = panel
        url = f"{G2P_BASE}/gene/{gene_symbol}/entries"
        body, meta = await self._cached_get(url, params=params, extra_key=f"entries_{gene_symbol}_{panel}")
        if not body:
            return []
        items = (
            body.get("results", [])
            if isinstance(body, dict)
            else body
            if isinstance(body, list)
            else []
        )
        return [self._normalize(item, query=gene_symbol) for item in items if isinstance(item, dict)]

    def _normalize(self, item: Dict[str, Any], query: str = "") -> Dict[str, Any]:
        return {
            "gene_symbol": item.get("gene_symbol", query),
            "disease_name": strip_html(item.get("disease_name", item.get("disease", ""))),
            "panel": item.get("panel", ""),
            "confidence": item.get("confidence", item.get("confidence_category", "")),
            "allelic_requirement": item.get("allelic_requirement", ""),
            "mutation_consequence": item.get("mutation_consequence", ""),
            "hpo_terms": item.get("phenotypes", []),
            "omim_id": item.get("omim_id", ""),
            "source_db": "gene2phenotype",
        }

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        results = await self.get_gene_entries(entity_id)
        return {"gene": entity_id, "entries": results} if results else None
