"""Ensembl REST API connector — genomic data access."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from .base import BaseConnector


class EnsemblConnector(BaseConnector):
    """Query Ensembl REST API for gene, transcript, and variant data."""

    name = "ensembl"
    BASE_URL = "https://rest.ensembl.org"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Use xrefs endpoint to look up gene symbols
        url = f"{self.BASE_URL}/xrefs/symbol/homo_sapiens/{query}"
        params = {"content-type": "application/json"}
        body, meta = await self._cached_get(url, params=params)

        if body is None or not isinstance(body, list):
            return []

        results = []
        for item in body[:limit]:
            ensembl_id = item.get("id", "")
            results.append({
                "id": ensembl_id,
                "type": item.get("type", ""),
                "source": "ensembl",
                "url": f"https://www.ensembl.org/Homo_sapiens/Gene/Summary?g={ensembl_id}",
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/lookup/id/{entity_id}"
        params = {"content-type": "application/json", "expand": "1"}
        body, meta = await self._cached_get(url, params=params)
        if body and isinstance(body, dict):
            return {
                "id": body.get("id", entity_id),
                "display_name": body.get("display_name", ""),
                "species": body.get("species", ""),
                "biotype": body.get("biotype", ""),
                "description": body.get("description", ""),
                "strand": body.get("strand"),
                "seq_region_name": body.get("seq_region_name", ""),
                "start": body.get("start"),
                "end": body.get("end"),
                "source": "ensembl",
            }
        return None

    async def count(self, query: str) -> Optional[int]:
        results = await self.search(query)
        return len(results)
