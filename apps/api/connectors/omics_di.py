"""OmicsDI (Multi-omics Dataset Index) connector.

Aggregates omics datasets from ArrayExpress, PRIDE, MetaboLights, etc.
API Reference: https://www.omicsdi.org/ws/
Rate Limits: ~10 req/s, no API key required.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class OmicsDIConnector(BaseConnector):
    """Query OmicsDI for multi-omics datasets across repositories."""

    name = "omics_di"
    BASE_URL = "https://www.omicsdi.org/ws"
    cache_ttl = 86400 * 2
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search omics datasets by keyword, gene, or disease."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/dataset/search",
            params={
                "query": query,
                "size": min(limit, 100),
                "start": 0,
                "sortField": "id",
                "order": "desc",
            },
        )
        if not data or not isinstance(data, dict):
            return []
        results = []
        for dataset in data.get("datasets", [])[:limit]:
            acc = dataset.get("accession", "")
            db = dataset.get("database", "")
            results.append({
                "id": f"{db}:{acc}",
                "entity_type": "omics_dataset",
                "canonical_name": dataset.get("name", acc),
                "description": dataset.get("description", ""),
                "accession": acc,
                "database": db,
                "omics_type": dataset.get("omicsType", []),
                "organism": dataset.get("organism", []),
                "tissue": dataset.get("tissue", []),
                "disease": dataset.get("disease", []),
                "submitter": dataset.get("submitter", ""),
                "publication_date": dataset.get("publicationDate", ""),
                "source_db": "OmicsDI",
                "url": f"https://www.omicsdi.org/dataset/{db}/{acc}",
                "provenance": [self._prov(
                    url=f"https://www.omicsdi.org/dataset/{db}/{acc}",
                    ext_id=acc,
                    confidence=0.80,
                    reasoning="OmicsDI aggregated omics dataset",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, database: str, accession: str) -> Optional[Dict[str, Any]]:
        """Fetch full dataset metadata by database + accession."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/dataset/{database}/{accession}"
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "accession": accession,
            "database": database,
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "omics_type": data.get("omicsType", []),
            "organism": data.get("organism", []),
            "tissue": data.get("tissue", []),
            "disease": data.get("disease", []),
            "sample_count": data.get("sampleCount", 0),
            "assay_count": data.get("assayCount", 0),
            "full_dataset_link": data.get("fullDatasetLink", ""),
            "source_db": "OmicsDI",
        }
