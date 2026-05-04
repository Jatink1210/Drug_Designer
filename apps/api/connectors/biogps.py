"""BioGPS gene expression atlas connector.

Provides tissue/cell-type-specific gene expression profiles from BioGPS.
API Reference: http://biogps.org/api/
Rate Limits: ~5 req/s, no API key required.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class BioGPSConnector(BaseConnector):
    """Query BioGPS for tissue-specific expression profiles."""

    name = "biogps"
    BASE_URL = "https://biogps.org/api"
    cache_ttl = 86400 * 3
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search genes or datasets in BioGPS."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/gene/search/",
            params={"q": query, "limit": min(limit, 50), "format": "json"},
        )
        if not data or not isinstance(data, dict):
            return []
        results = []
        for hit in data.get("hits", {}).get("hits", [])[:limit]:
            src = hit.get("_source", {})
            symbol = src.get("symbol", "")
            entrez_id = str(src.get("entrezgene", ""))
            results.append({
                "id": entrez_id,
                "entity_type": "gene",
                "canonical_name": symbol,
                "name": src.get("name", symbol),
                "description": src.get("summary", ""),
                "taxid": src.get("taxid", ""),
                "chromosome": src.get("genomic_pos", {}).get("chr", ""),
                "synonyms": src.get("alias", []),
                "source_db": "BioGPS",
                "url": f"https://biogps.org/#goto=genereport&id={entrez_id}",
                "provenance": [self._prov(
                    url=f"https://biogps.org/#goto=genereport&id={entrez_id}",
                    ext_id=entrez_id,
                    confidence=0.85,
                    reasoning="BioGPS expression atlas gene entry",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entrez_id: str) -> Optional[Dict[str, Any]]:
        """Fetch gene expression profile by Entrez Gene ID."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/gene/{entrez_id}",
            params={"format": "json"},
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "id": entrez_id,
            "symbol": data.get("symbol", ""),
            "name": data.get("name", ""),
            "summary": data.get("summary", ""),
            "taxid": data.get("taxid", ""),
            "go_terms": data.get("go", {}),
            "refseq": data.get("refseq", {}),
            "source_db": "BioGPS",
        }

    async def get_expression_profile(self, entrez_id: str, dataset: str = "HBU133A") -> List[Dict[str, Any]]:
        """Get expression values across tissues for a gene from a dataset."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/gene/{entrez_id}/",
            params={"dataset": dataset, "format": "json"},
            extra_key=entrez_id + dataset,
        )
        if not data or not isinstance(data, dict):
            return []
        profiles = []
        for tissue, value in data.get("expression", {}).items():
            profiles.append({
                "tissue": tissue,
                "expression_value": value,
                "dataset": dataset,
                "source_db": "BioGPS",
            })
        return sorted(profiles, key=lambda x: x["expression_value"], reverse=True)
