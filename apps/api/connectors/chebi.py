"""ChEBI connector — free, no API key.

Chemical Entities of Biological Interest. ~60K compounds.
API Reference: https://www.ebi.ac.uk/chebi/
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector


class ChEBIConnector(BaseConnector):
    name = "ChEBI"
    BASE_URL = "https://www.ebi.ac.uk/ols4/api"
    cache_ttl = 86400

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Primary: EBI OLS4 search (ChEBI REST/SOAP deprecated)
        params = {"ontology": "chebi", "q": query, "rows": min(limit, 50)}
        data, meta = await self._cached_get(f"{self.BASE_URL}/search", params=params)
        if not data or not isinstance(data, dict):
            return []
        docs = data.get("response", {}).get("docs", [])
        results = []
        for c in docs:
            chebi_id = c.get("obo_id", c.get("short_form", ""))
            results.append({
                "id": chebi_id,
                "entity_type": "molecule",
                "canonical_name": c.get("label", ""),
                "description": c.get("description", [""])[0] if isinstance(c.get("description"), list) else c.get("description", ""),
                "source_db": "ChEBI",
                "url": f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId={chebi_id}",
                "provenance": [self._prov(
                    url=f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId={chebi_id}",
                    ext_id=chebi_id, confidence=1.0, reasoning="ChEBI via OLS4"
                ).to_dict()],
            })
        return results[:limit]
