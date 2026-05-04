"""MalaCards connector — disease gene association database.

Comprehensive disease database with gene associations, symptoms, and drugs.
API Reference: https://www.malacards.org/api/
Note: Free API provides limited access; full DB requires subscription.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class MalaCardsConnector(BaseConnector):
    """MalaCards disease-gene associations via REST API."""

    name = "malacards"
    BASE_URL = "https://www.malacards.org/api"
    cache_ttl = 86400 * 3
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search diseases by name or gene symbol."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/search",
            params={"query": query, "maxHits": min(limit, 20)},
        )
        if not data or not isinstance(data, dict):
            return []
        results = []
        for card in data.get("diseases", [])[:limit]:
            mala_id = card.get("id", "")
            results.append({
                "id": mala_id,
                "entity_type": "disease",
                "canonical_name": card.get("name", ""),
                "description": card.get("summary", ""),
                "mim_id": card.get("mimId", ""),
                "aliases": card.get("aliases", []),
                "category": card.get("category", ""),
                "score": card.get("score", 0.0),
                "source_db": "MalaCards",
                "url": f"https://www.malacards.org/card/{mala_id}",
                "provenance": [self._prov(
                    url=f"https://www.malacards.org/card/{mala_id}",
                    ext_id=mala_id,
                    confidence=0.85,
                    reasoning="MalaCards disease gene association",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, disease_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed disease card including gene associations."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/disease/{disease_id}"
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "id": disease_id,
            "name": data.get("name", ""),
            "summary": data.get("summary", ""),
            "genes": data.get("genes", []),
            "drugs": data.get("drugs", []),
            "symptoms": data.get("symptoms", []),
            "categories": data.get("categories", []),
            "mim_id": data.get("mimId", ""),
            "source_db": "MalaCards",
        }

    async def get_disease_genes(self, disease_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get genes associated with a disease card."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/disease/{disease_id}/genes",
            params={"limit": min(limit, 100)},
            extra_key=disease_id,
        )
        if not data or not isinstance(data, list):
            return []
        genes = []
        for gene in data[:limit]:
            genes.append({
                "gene_symbol": gene.get("symbol", ""),
                "gene_name": gene.get("name", ""),
                "association_score": gene.get("score", 0.0),
                "evidence_types": gene.get("evidenceTypes", []),
                "source_db": "MalaCards",
            })
        return genes
