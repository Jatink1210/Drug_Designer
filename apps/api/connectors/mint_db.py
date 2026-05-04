"""MINT (Molecular INTeraction database) connector.

Curated molecular interactions from scientific literature.
API Reference: https://mint.bio.uniroma2.it/download.html
Uses PSICQUIC (Proteomics Standard Initiative Common QUery Interface).
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class MINTDbConnector(BaseConnector):
    """Query MINT via PSICQUIC REST API for molecular interactions."""

    name = "mint_db"
    BASE_URL = "https://mint.bio.uniroma2.it/psicquic/webservices/current/search"
    cache_ttl = 86400 * 7
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search MINT for interactions by gene symbol or UniProt ID."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/query/{query}",
            params={"format": "json", "firstResult": 0, "maxResults": min(limit, 200)},
        )
        if not data or not isinstance(data, dict):
            return []
        results = []
        for interaction in data.get("data", [])[:limit]:
            cols = interaction if isinstance(interaction, list) else []
            if len(cols) < 8:
                continue
            int_id = cols[0] if cols else ""
            interactor_a = cols[2] if len(cols) > 2 else ""
            interactor_b = cols[3] if len(cols) > 3 else ""
            pmids = [cols[8]] if len(cols) > 8 else []
            results.append({
                "id": int_id,
                "entity_type": "protein_interaction",
                "canonical_name": f"{interactor_a} — {interactor_b}",
                "description": f"MINT interaction: {interactor_a} with {interactor_b}",
                "interactor_a": interactor_a,
                "interactor_b": interactor_b,
                "pmids": pmids,
                "detection_method": cols[6] if len(cols) > 6 else "",
                "interaction_type": cols[11] if len(cols) > 11 else "",
                "confidence_score": cols[14] if len(cols) > 14 else "",
                "source_db": "MINT",
                "url": f"https://mint.bio.uniroma2.it/mint/interactions/show.do?ac={int_id}",
                "provenance": [self._prov(
                    url=f"https://mint.bio.uniroma2.it/mint/interactions/show.do?ac={int_id}",
                    ext_id=int_id,
                    confidence=0.88,
                    reasoning="MINT literature-curated molecular interaction",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, mint_id: str) -> Optional[Dict[str, Any]]:
        """Fetch interaction by MINT ID."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/interactor/{mint_id}",
            params={"format": "json"},
            extra_key=mint_id,
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "id": mint_id,
            "interactions": data.get("data", []),
            "source_db": "MINT",
        }
