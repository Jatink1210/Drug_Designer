"""OmniPath multi-layer interaction aggregation connector (F-1).

OmniPath integrates protein-protein, signaling, gene regulatory, and
metabolic interactions from >100 databases in a unified API.

API: https://omnipathdb.org/
Rate Limits: 1 req/s (public)
Auth: None
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger(__name__)

OMNIPATH_BASE = "https://omnipathdb.org"


class OmniPathConnector(BaseConnector):
    """OmniPath multi-layer interaction database connector.

    Provides access to:
    - PPI (protein–protein interactions)
    - Signaling network (directed, effect-signed)
    - Gene regulatory interactions (TF → target)
    - Metabolic enzyme–substrate relations
    """

    name = "omnipath"
    cache_ttl = 86400 * 7  # 7 days — OmniPath data is stable
    rate_limit_rps = 1.0
    rate_limit_burst = 3
    http_timeout = 30.0
    max_retries = 3
    degradation_mode = "degrade"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search OmniPath interactions by gene/protein symbol."""
        return await self.get_interactions(query, limit=limit)

    async def get_interactions(
        self,
        gene_symbol: str,
        datasets: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fetch interactions involving *gene_symbol*.

        Args:
            gene_symbol: HGNC symbol (e.g. "BRCA1", "TP53")
            datasets: subset of ["omnipath", "pathwayextra", "kinaseextra", "ligrecextra"]
            limit: max rows to return

        Returns:
            List of interaction dicts with keys:
            source, target, is_directed, is_stimulation, is_inhibition,
            consensus_direction, n_references, databases
        """
        datasets = datasets or ["omnipath", "pathwayextra"]
        params: Dict[str, Any] = {
            "partners": gene_symbol,
            "datasets": ",".join(datasets),
            "fields": "sources,references,curation_effort",
            "format": "json",
            "limit": min(limit, 1000),
        }
        url = f"{OMNIPATH_BASE}/interactions"
        body, meta = await self._cached_get(url, params=params, extra_key=gene_symbol)
        if not body:
            log.warning("omnipath_no_data", gene=gene_symbol, meta=meta)
            return []

        rows = body if isinstance(body, list) else body.get("data", [])
        results: List[Dict[str, Any]] = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            results.append({
                "source_gene": row.get("source_genesymbol", row.get("source", "")),
                "target_gene": row.get("target_genesymbol", row.get("target", "")),
                "is_directed": bool(row.get("is_directed", False)),
                "is_stimulation": bool(row.get("is_stimulation", False)),
                "is_inhibition": bool(row.get("is_inhibition", False)),
                "consensus_direction": bool(row.get("consensus_direction", False)),
                "n_references": int(row.get("n_references", 0)),
                "databases": row.get("sources", ""),
                "interaction_type": "signaling",
                "source_db": "omnipath",
                "query_gene": gene_symbol,
            })
        return results

    async def get_pathways(self, gene_symbol: str) -> List[Dict[str, Any]]:
        """Retrieve pathway memberships from Pathway Commons / KEGG via OmniPath."""
        params = {
            "query": gene_symbol,
            "format": "json",
        }
        url = f"{OMNIPATH_BASE}/annotations"
        body, meta = await self._cached_get(url, params=params, extra_key=f"pathways_{gene_symbol}")
        if not body:
            return []
        rows = body if isinstance(body, list) else body.get("annotations", [])
        return [
            {
                "gene": gene_symbol,
                "resource": r.get("resource", ""),
                "label": r.get("label", ""),
                "value": r.get("value", ""),
                "source_db": "omnipath",
            }
            for r in rows[:50]
            if isinstance(r, dict)
        ]

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        results = await self.get_interactions(entity_id, limit=10)
        return {"gene": entity_id, "interactions": results} if results else None
