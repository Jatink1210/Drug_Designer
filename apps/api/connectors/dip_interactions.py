"""DIP (Database of Interacting Proteins) connector.

Curated experimental protein-protein interactions.
API Reference: https://dip.doe-mbi.ucla.edu/dip/REST.cgi
Rate Limits: ~5 req/s, no API key required.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class DIPInteractionsConnector(BaseConnector):
    """Query DIP for experimentally determined protein-protein interactions."""

    name = "dip_interactions"
    BASE_URL = "https://dip.doe-mbi.ucla.edu/dip/REST.cgi"
    cache_ttl = 86400 * 7
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search DIP for interactions involving a gene/protein."""
        data, _meta = await self._cached_get(
            self.BASE_URL,
            params={
                "query": query,
                "format": "json",
                "limit": min(limit, 100),
            },
        )
        if not data or not isinstance(data, dict):
            return []
        results = []
        for interaction in data.get("interactions", [])[:limit]:
            dip_id = interaction.get("id", "")
            interactors = interaction.get("interactors", [])
            interactor_names = [i.get("uniprotAC", i.get("geneSymbol", "")) for i in interactors]
            results.append({
                "id": dip_id,
                "entity_type": "protein_interaction",
                "canonical_name": " — ".join(interactors[:2]) if interactors else dip_id,
                "description": f"DIP interaction {dip_id}",
                "interactors": interactor_names,
                "interactor_count": len(interactors),
                "detection_methods": interaction.get("detectionMethods", []),
                "experiment_types": interaction.get("experimentTypes", []),
                "pmids": interaction.get("pmids", []),
                "taxid": interaction.get("taxId", ""),
                "source_db": "DIP",
                "url": f"https://dip.doe-mbi.ucla.edu/dip/Detail?id={dip_id}",
                "provenance": [self._prov(
                    url=f"https://dip.doe-mbi.ucla.edu/dip/Detail?id={dip_id}",
                    ext_id=dip_id,
                    confidence=0.90,
                    reasoning="DIP experimentally curated PPI",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, dip_id: str) -> Optional[Dict[str, Any]]:
        """Fetch interaction details by DIP ID."""
        data, _meta = await self._cached_get(
            self.BASE_URL,
            params={"id": dip_id, "format": "json"},
            extra_key=dip_id,
        )
        if not data or not isinstance(data, dict):
            return None
        interaction = data.get("interaction", {})
        if not interaction:
            return None
        return {
            "id": dip_id,
            "interactors": interaction.get("interactors", []),
            "detection_methods": interaction.get("detectionMethods", []),
            "experiment_types": interaction.get("experimentTypes", []),
            "pmids": interaction.get("pmids", []),
            "taxid": interaction.get("taxId", ""),
            "source_db": "DIP",
        }
