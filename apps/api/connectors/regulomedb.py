"""RegulomeDB connector — regulatory variant scoring.

Maps variants to regulatory elements using functional genomics data.
API Reference: https://regulomedb.org/regulome-help/
Rate Limits: ~10 req/s, no API key required.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class RegulomeDBConnector(BaseConnector):
    """Query RegulomeDB for regulatory variant scores and annotations."""

    name = "regulomedb"
    BASE_URL = "https://regulomedb.org/regulome-search"
    cache_ttl = 86400 * 7

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search variants by rsID or genomic region (chrom:start-end)."""
        data, _meta = await self._cached_get(
            self.BASE_URL,
            params={
                "regions": query,
                "genome": "GRCh38",
                "maf": 0.01,
                "format": "json",
                "limit": min(limit, 50),
            },
        )
        if not data or not isinstance(data, dict):
            return []
        results = []
        for variant in data.get("variants", {}).get("results", [])[:limit]:
            chrom = variant.get("chrom", "")
            pos = variant.get("start", "")
            rsid = variant.get("rsid", "")
            results.append({
                "id": rsid or f"{chrom}:{pos}",
                "entity_type": "variant",
                "canonical_name": rsid or f"chr{chrom}:{pos}",
                "chromosome": chrom,
                "position": pos,
                "rsid": rsid,
                "regulome_score": variant.get("score", ""),
                "regulome_rank": variant.get("rank", ""),
                "assembly": "GRCh38",
                "description": f"RegulomeDB score: {variant.get('score', 'N/A')}",
                "source_db": "RegulomeDB",
                "url": f"https://regulomedb.org/regulome-search/?regions={rsid or f'chr{chrom}:{pos}-{pos}'}",
                "provenance": [self._prov(
                    url=f"https://regulomedb.org/regulome-search/?regions={rsid}",
                    ext_id=rsid,
                    confidence=0.80,
                    reasoning="RegulomeDB regulatory variant annotation",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, rsid: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed regulatory annotation for a single variant by rsID."""
        data, _meta = await self._cached_get(
            self.BASE_URL,
            params={"regions": rsid, "genome": "GRCh38", "format": "json", "limit": 1},
            extra_key=rsid,
        )
        if not data or not isinstance(data, dict):
            return None
        variants = data.get("variants", {}).get("results", [])
        if not variants:
            return None
        v = variants[0]
        return {
            "id": rsid,
            "rsid": rsid,
            "chromosome": v.get("chrom", ""),
            "position": v.get("start", ""),
            "regulome_score": v.get("score", ""),
            "regulome_rank": v.get("rank", ""),
            "assembly": "GRCh38",
            "datasets": v.get("datasets", {}),
            "source_db": "RegulomeDB",
        }
