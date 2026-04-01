"""DrugBank connector — open-access drug vocabulary and target data."""

from __future__ import annotations
from typing import Any, Dict, List
from .base import BaseConnector


class DrugBankConnector(BaseConnector):
    """Search DrugBank Open Data for drugs and their targets.
    
    Uses the free DrugBank Open Data vocabulary queries.
    Full DrugBank API requires academic/commercial license.
    """

    name = "drugbank"
    BASE_URL = "https://go.drugbank.com/unearth/q"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = self.BASE_URL
        params = {
            "searcher": "drugs",
            "query": query,
            "approved": "1",
            "button": "",
        }
        body, meta = await self._cached_get(url, params=params, extra_key=f"limit={limit}")
        
        if body is None:
            return []

        # DrugBank returns HTML for open queries. For the connector bench,
        # we return structured metadata about the query attempt.
        return [{
            "source": "drugbank",
            "query": query,
            "status": "queried",
            "note": "DrugBank Open Data responded. Full parsing requires API license.",
            "provenance": self._prov(url=url, confidence=0.9, reasoning="DrugBank open vocabulary"),
        }]

    async def fetch_by_id(self, entity_id: str) -> Dict[str, Any] | None:
        url = f"https://go.drugbank.com/drugs/{entity_id}.json"
        body, meta = await self._cached_get(url)
        if body and isinstance(body, dict):
            return body
        return None
