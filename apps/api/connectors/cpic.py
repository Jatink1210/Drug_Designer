"""CPIC Clinical Pharmacogenomics connector (F-3).

CPIC provides evidence-based guidelines for using genetic test results
to optimize drug therapy.

API: https://api.cpicpgx.org/v1/
Rate Limits: 10 req/s
Auth: None (public)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger(__name__)

CPIC_BASE = "https://api.cpicpgx.org/v1"


class CPICConnector(BaseConnector):
    """CPIC clinical pharmacogenomics guideline connector.

    Provides:
    - Gene-drug pairs with CPIC classification level (A/B/C/D)
    - Prescribing recommendations per diplotype
    - Drug-gene interaction evidence
    """

    name = "cpic"
    cache_ttl = 86400 * 3  # 3 days
    rate_limit_rps = 5.0
    rate_limit_burst = 10
    http_timeout = 15.0
    max_retries = 3
    degradation_mode = "degrade"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search CPIC guidelines by gene or drug name."""
        gene_results = await self.get_gene_drug_pairs(gene=query, limit=limit)
        if gene_results:
            return gene_results
        return await self.get_gene_drug_pairs(drug=query, limit=limit)

    async def get_gene_drug_pairs(
        self,
        gene: Optional[str] = None,
        drug: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve CPIC gene-drug pairs and their classification level.

        Returns:
            List of dicts with keys:
            gene_symbol, drug_name, cpic_level, pgkb_level,
            pgx_on_fda_label, has_cpic_guideline, citations
        """
        params: Dict[str, Any] = {"select": "*", "limit": min(limit, 200)}
        if gene:
            params["geneSymbol"] = f"eq.{gene}"
        elif drug:
            params["drugName"] = f"ilike.*{drug}*"

        url = f"{CPIC_BASE}/pair"
        body, meta = await self._cached_get(url, params=params, extra_key=f"{gene}_{drug}")
        if not body:
            log.warning("cpic_no_data", gene=gene, drug=drug, meta=meta)
            return []

        rows = body if isinstance(body, list) else []
        results: List[Dict[str, Any]] = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            results.append({
                "gene_symbol": row.get("geneSymbol", ""),
                "drug_name": row.get("drugName", ""),
                "cpic_level": row.get("cpicLevel", ""),
                "pgkb_level": row.get("pgkbLevel", ""),
                "pgx_on_fda_label": row.get("pgxOnFdaLabel", ""),
                "has_cpic_guideline": bool(row.get("hasCpicGuideline", False)),
                "guideline_url": f"https://cpicpgx.org/guidelines/{row.get('guideline', {}).get('urlSlug', '')}",
                "n_publications": row.get("nPublications", 0),
                "source_db": "cpic",
            })
        return results

    async def get_guideline(self, gene: str, drug: str) -> Optional[Dict[str, Any]]:
        """Fetch full CPIC guideline recommendation for a gene-drug pair."""
        params = {
            "geneSymbol": f"eq.{gene}",
            "drugName": f"ilike.{drug}",
            "select": "*",
        }
        url = f"{CPIC_BASE}/recommendation"
        body, meta = await self._cached_get(url, params=params, extra_key=f"rec_{gene}_{drug}")
        if not body or not isinstance(body, list) or not body:
            return None
        rec = body[0]
        return {
            "gene": gene,
            "drug": drug,
            "classification": rec.get("classification", ""),
            "recommendation": strip_html(rec.get("recommendation", "")),
            "implications": rec.get("implications", ""),
            "source_db": "cpic",
        }

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        results = await self.search(entity_id, limit=10)
        return results[0] if results else None
