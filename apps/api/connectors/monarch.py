"""
Monarch Initiative Connector - Disease & Ontology Family

Implements FR-CONN-001: Connector Portfolio
Task 8.2.2: Implement Monarch Initiative connector

Monarch Initiative integrates genotype-phenotype data across species.
Provides disease-gene-phenotype associations.

API Documentation: https://api.monarchinitiative.org/api/
Rate Limits: 10 requests/second
Authentication: None required (public API)
Performance Target: p95 <3s
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger()

MONARCH_API = "https://api.monarchinitiative.org/api"


class MonarchConnector(BaseConnector):
    """
    Search Monarch Initiative for disease-gene-phenotype associations.
    
    Features:
    - Circuit breaker pattern (via ResilientClient)
    - Rate limiting (10 RPS)
    - Provenance tracking
    - Two-tier caching (Redis + in-memory)
    - Performance: p95 <3s
    """

    name = "monarch"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 10.0
    rate_limit_burst = 20
    http_timeout = 15.0
    max_retries = 3
    degradation_mode = "degrade"

    async def search(
        self, 
        query: str, 
        limit: int = 20,
        category: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search Monarch Initiative.
        
        Args:
            query: Search query string
            limit: Maximum number of results (default: 20)
            category: Filter by category (disease, gene, phenotype, etc.)
        
        Returns:
            List of normalized entity records
        
        Performance: p95 <3s
        """
        params = {
            "q": query,
            "rows": limit,
            "start": 0
        }
        
        if category:
            params["category"] = category
        
        url = f"{MONARCH_API}/search/entity"
        body, meta = await self._cached_get(url, params=params, extra_key=query)
        
        if body is None or "docs" not in body:
            log.warning(
                "monarch_search_failed",
                query=query,
                meta=meta
            )
            return []
        
        results = []
        for doc in body.get("docs", [])[:limit]:
            normalized = self.normalize(doc)
            
            # Add provenance
            normalized["provenance"] = self._prov(
                url=url,
                phash=meta.get("payload_hash", ""),
                confidence=0.95,
                reasoning="Retrieved from Monarch Initiative API",
                ext_id=doc.get("id", "")
            ).dict()
            
            results.append(normalized)
        
        log.info(
            "monarch_search_complete",
            query=query,
            results_count=len(results),
            cache_hit=meta.get("cache_hit", False)
        )
        
        return results

    async def fetch_by_id(self, monarch_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific Monarch entity by ID.
        
        Args:
            monarch_id: Monarch entity ID (e.g., "MONDO:0005148")
        
        Returns:
            Normalized entity record or None if not found
        
        Performance: p95 <3s
        """
        url = f"{MONARCH_API}/bioentity/{monarch_id}"
        body, meta = await self._cached_get(url)
        
        if body is None:
            log.warning(
                "monarch_fetch_failed",
                monarch_id=monarch_id,
                meta=meta
            )
            return None
        
        normalized = self.normalize(body)
        
        # Add provenance
        normalized["provenance"] = self._prov(
            url=url,
            phash=meta.get("payload_hash", ""),
            confidence=1.0,
            reasoning="Retrieved by ID from Monarch Initiative API",
            ext_id=monarch_id
        ).dict()
        
        log.info(
            "monarch_fetch_complete",
            monarch_id=monarch_id,
            cache_hit=meta.get("cache_hit", False)
        )
        
        return normalized

    async def extract_evidence(self, monarch_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records from a Monarch entity.
        
        Args:
            monarch_id: Monarch entity ID
        
        Returns:
            List of evidence records
        """
        entity = await self.fetch_by_id(monarch_id)
        if not entity:
            return []
        
        evidence = []
        
        if entity.get("description"):
            evidence.append({
                "type": "description",
                "content": entity["description"],
                "source": "monarch",
                "monarch_id": monarch_id,
                "confidence": 0.95
            })
        
        if entity.get("label"):
            evidence.append({
                "type": "label",
                "content": entity["label"],
                "source": "monarch",
                "monarch_id": monarch_id,
                "confidence": 0.95
            })
        
        return evidence

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Monarch API response to standard format.
        
        Args:
            raw_data: Raw API response item
        
        Returns:
            Normalized entity record
        """
        return {
            "id": raw_data.get("id", ""),
            "monarch_id": raw_data.get("id", ""),
            "label": strip_html(raw_data.get("label", "")),
            "description": strip_html(raw_data.get("description", "")),
            "category": raw_data.get("category", []),
            "taxon": raw_data.get("taxon", {}),
            "synonyms": raw_data.get("synonyms", []),
            "source": "monarch",
            "resource_type": "bioentity",
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Monarch API health and availability.
        
        Returns:
            Health status with response time and availability
        """
        import time
        
        start_time = time.time()
        
        try:
            params = {"q": "diabetes", "rows": 1}
            url = f"{MONARCH_API}/search/entity"
            body, meta = await self._cached_get(url, params=params)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if body is not None and "docs" in body:
                return {
                    "status": "healthy",
                    "response_time_ms": response_time_ms,
                    "available": True,
                    "error": None,
                    "cache_hit": meta.get("cache_hit", False)
                }
            else:
                return {
                    "status": "degraded",
                    "response_time_ms": response_time_ms,
                    "available": True,
                    "error": "Unexpected response format",
                    "cache_hit": meta.get("cache_hit", False)
                }
        
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            log.error(
                "monarch_health_check_failed",
                error=str(e),
                response_time_ms=response_time_ms
            )
            return {
                "status": "unhealthy",
                "response_time_ms": response_time_ms,
                "available": False,
                "error": str(e)
            }
