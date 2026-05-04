"""BioGRID connector — free with API key (free registration).

Protein-protein and genetic interactions. 2M+ interactions.
Register for a free API key at https://webservice.thebiogrid.org/
Set BIOGRID_API_KEY env var to enable this connector.
"""

from __future__ import annotations
import logging
import os
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector

log = logging.getLogger(__name__)


class BioGRIDConnector(BaseConnector):
    name = "BioGRID"
    BASE_URL = "https://webservice.thebiogrid.org/interactions"
    cache_ttl = 86400

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        api_key = os.environ.get("BIOGRID_API_KEY", "")
        if not api_key:
            log.warning("BioGRID requires a free API key. Set BIOGRID_API_KEY env var. "
                        "Register at https://webservice.thebiogrid.org/")
            return []
        params = {
            "accessKey": api_key,
            "searchNames": "true",
            "geneList": query,
            "organism": "9606",  # Homo sapiens
            "format": "json",
            "max": min(limit, 100),
            "includeInteractors": "true",
        }
        data, meta = await self._cached_get(self.BASE_URL, params=params)
        if not data or not isinstance(data, dict):
            return []
        results = []
        for interaction_id, entry in data.items():
            results.append({
                "id": f"BioGRID:{interaction_id}",
                "entity_type": "interaction",
                "source_entity": entry.get("OFFICIAL_SYMBOL_A", ""),
                "target_entity": entry.get("OFFICIAL_SYMBOL_B", ""),
                "interaction_type": entry.get("EXPERIMENTAL_SYSTEM", ""),
                "detection_method": entry.get("EXPERIMENTAL_SYSTEM_TYPE", ""),
                "score": entry.get("SCORE", None),
                "pubmed_id": entry.get("PUBMED_ID", ""),
                "provenance": [self._prov(
                    url=f"https://thebiogrid.org/interaction/{interaction_id}",
                    ext_id=interaction_id, confidence=1.0, reasoning="BioGRID"
                ).to_dict()],
            })
        return results[:limit]
