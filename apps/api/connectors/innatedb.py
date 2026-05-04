"""InnateDB innate immunity interactions connector (F-12).

InnateDB is a curated database of the genes, proteins, and interactions
involved in the innate immune response.

API: https://www.innatedb.com/RESTful/
Rate Limits: 5 req/s
Auth: None required
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger(__name__)

INNATEDB_BASE = "https://www.innatedb.com/RESTful"


class InnateDBConnector(BaseConnector):
    """InnateDB innate immunity PPI + pathway connector.

    Provides:
    - Gene/protein annotations for innate immune molecules
    - Experimentally validated PPIs from innate immunity context
    - Pathway enrichment data
    """

    name = "innatedb"
    cache_ttl = 86400 * 7  # 7 days — curated, stable
    rate_limit_rps = 3.0
    rate_limit_burst = 6
    http_timeout = 20.0
    max_retries = 3
    degradation_mode = "degrade"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search InnateDB by gene/protein symbol."""
        return await self.get_gene(query, limit=limit)

    async def get_gene(self, symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch gene annotation from InnateDB.

        Args:
            symbol: Gene symbol (e.g. "TLR4", "MYD88")
            limit: Max interactions to return

        Returns:
            List of interaction records for the gene
        """
        params = {"gene": symbol, "limit": min(limit, 100)}
        url = f"{INNATEDB_BASE}/gene/{symbol}"
        body, meta = await self._cached_get(url, params=params, extra_key=symbol)
        if not body:
            log.warning("innatedb_gene_empty", symbol=symbol, meta=meta)
            return []

        # InnateDB returns varied formats; handle list or dict
        if isinstance(body, list):
            items = body
        elif isinstance(body, dict):
            items = body.get("interactions", body.get("results", [body]))
        else:
            items = []

        results: List[Dict[str, Any]] = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            results.append(self._normalize(item, symbol))
        return results

    async def get_interactions(
        self, gene_symbol: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch PPI interactions involving a gene from InnateDB."""
        params = {"query": gene_symbol, "species": "9606", "limit": min(limit, 500)}
        url = f"{INNATEDB_BASE}/interactions"
        body, meta = await self._cached_get(url, params=params, extra_key=f"interactions_{gene_symbol}")
        if not body:
            return []
        items = body if isinstance(body, list) else body.get("interactions", [])
        return [self._normalize(i, gene_symbol) for i in items[:limit] if isinstance(i, dict)]

    def _normalize(self, item: Dict[str, Any], query_gene: str = "") -> Dict[str, Any]:
        return {
            "gene_symbol": item.get("geneA", item.get("gene_symbol", query_gene)),
            "interactor": item.get("geneB", item.get("interactor", "")),
            "interaction_type": item.get("interaction_type", "ppi"),
            "evidence_code": item.get("evidence_code", ""),
            "detection_method": item.get("detection_method", ""),
            "pubmed_id": item.get("pmid", item.get("pubmed_id", "")),
            "immune_role": item.get("immune_role", "innate_immunity"),
            "pathway": item.get("pathway", ""),
            "source_db": "innatedb",
        }

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        results = await self.get_gene(entity_id, limit=5)
        return results[0] if results else None
