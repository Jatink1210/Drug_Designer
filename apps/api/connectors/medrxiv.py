"""
medRxiv Connector - Literature Family

Implements FR-CONN-001: Connector Portfolio
Task 8.1.1: Implement medRxiv connector

medRxiv is a preprint server for health sciences research.
Uses the bioRxiv Content API (api.biorxiv.org) with server=medrxiv.

API Documentation: https://api.biorxiv.org/
Rate Limits: 5 requests/second
Authentication: None required (public API)
Performance Target: p95 <3s
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger()

MEDRXIV_API = "https://api.biorxiv.org"


class MedRxivConnector(BaseConnector):
    """
    Search medRxiv preprints via the public content API.
    
    Features:
    - Circuit breaker pattern (via ResilientClient)
    - Rate limiting (5 RPS)
    - Provenance tracking
    - Two-tier caching (Redis + in-memory)
    - Performance: p95 <3s
    """

    name = "medrxiv"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 5.0
    rate_limit_burst = 10
    http_timeout = 15.0
    max_retries = 3
    degradation_mode = "degrade"

    async def search(
        self, 
        query: str, 
        limit: int = 20,
        start_date: str = "2020-01-01",
        end_date: str = "2026-12-31",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search medRxiv preprints.
        
        Args:
            query: Search query string (filters by title/abstract)
            limit: Maximum number of results (default: 20)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        
        Returns:
            List of normalized preprint records
        
        Performance: p95 <3s
        """
        # medRxiv API uses date-range detail endpoint
        # Format: /details/medrxiv/{start_date}/{end_date}/{cursor}/{page_size}
        url = f"{MEDRXIV_API}/details/medrxiv/{start_date}/{end_date}/0/{min(limit * 2, 100)}"
        
        body, meta = await self._cached_get(url, extra_key=query)
        
        if body is None:
            log.warning(
                "medrxiv_search_failed",
                query=query,
                meta=meta
            )
            return []
        
        if "collection" not in body:
            log.warning(
                "medrxiv_unexpected_response",
                query=query,
                body_keys=list(body.keys()) if isinstance(body, dict) else None
            )
            return []
        
        results = []
        query_lower = query.lower()
        
        for item in body.get("collection", []):
            # Filter by query in title or abstract
            title = item.get("title", "").lower()
            abstract = item.get("abstract", "").lower()
            
            if query_lower in title or query_lower in abstract:
                normalized = self.normalize(item)
                # Add provenance
                normalized["provenance"] = self._prov(
                    url=url,
                    phash=meta.get("payload_hash", ""),
                    confidence=0.95,
                    reasoning="Retrieved from medRxiv API",
                    ext_id=item.get("doi", "")
                ).dict()
                results.append(normalized)
            
            if len(results) >= limit:
                break
        
        log.info(
            "medrxiv_search_complete",
            query=query,
            results_count=len(results),
            cache_hit=meta.get("cache_hit", False)
        )
        
        return results[:limit]

    async def fetch_by_id(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific medRxiv preprint by DOI.
        
        Args:
            doi: Digital Object Identifier (e.g., "10.1101/2021.01.01.12345678")
        
        Returns:
            Normalized preprint record or None if not found
        
        Performance: p95 <3s
        """
        # Clean DOI (remove prefix if present)
        clean_doi = doi.replace("https://doi.org/", "").replace("doi:", "")
        
        url = f"{MEDRXIV_API}/details/medrxiv/{clean_doi}"
        
        body, meta = await self._cached_get(url)
        
        if body is None or "collection" not in body:
            log.warning(
                "medrxiv_fetch_failed",
                doi=clean_doi,
                meta=meta
            )
            return None
        
        items = body.get("collection", [])
        if not items:
            log.warning(
                "medrxiv_not_found",
                doi=clean_doi
            )
            return None
        
        normalized = self.normalize(items[0])
        # Add provenance
        normalized["provenance"] = self._prov(
            url=url,
            phash=meta.get("payload_hash", ""),
            confidence=1.0,
            reasoning="Retrieved by DOI from medRxiv API",
            ext_id=clean_doi
        ).dict()
        
        log.info(
            "medrxiv_fetch_complete",
            doi=clean_doi,
            cache_hit=meta.get("cache_hit", False)
        )
        
        return normalized

    async def count(self, query: str) -> Optional[int]:
        """
        Get total count of preprints matching query.
        
        Args:
            query: Search query string
        
        Returns:
            Total count or None if unavailable
        """
        # medRxiv API doesn't provide a count endpoint
        # We'd need to fetch all results to count
        # Return None to indicate count is not available
        return None

    async def extract_evidence(self, doi: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records from a medRxiv preprint.
        
        Args:
            doi: Digital Object Identifier
        
        Returns:
            List of evidence records (abstract, findings, etc.)
        """
        preprint = await self.fetch_by_id(doi)
        if not preprint:
            return []
        
        evidence = []
        
        # Abstract as evidence
        if preprint.get("abstract"):
            evidence.append({
                "type": "abstract",
                "content": preprint["abstract"],
                "source": "medrxiv",
                "doi": doi,
                "confidence": 0.9
            })
        
        # Title as evidence
        if preprint.get("title"):
            evidence.append({
                "type": "title",
                "content": preprint["title"],
                "source": "medrxiv",
                "doi": doi,
                "confidence": 0.95
            })
        
        return evidence

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize medRxiv API response to standard format.
        
        Args:
            raw_data: Raw API response item
        
        Returns:
            Normalized preprint record
        """
        # Clean HTML tags from text fields
        title = strip_html(raw_data.get("title", ""))
        abstract = strip_html(raw_data.get("abstract", ""))
        
        return {
            "id": raw_data.get("doi", ""),
            "doi": raw_data.get("doi", ""),
            "title": title,
            "abstract": abstract,
            "authors": raw_data.get("authors", ""),
            "author_corresponding": raw_data.get("author_corresponding", ""),
            "author_corresponding_institution": raw_data.get("author_corresponding_institution", ""),
            "date": raw_data.get("date", ""),
            "version": raw_data.get("version", ""),
            "type": raw_data.get("type", ""),
            "license": raw_data.get("license", ""),
            "category": raw_data.get("category", ""),
            "jatsxml": raw_data.get("jatsxml", ""),
            "published": raw_data.get("published", ""),
            "server": "medrxiv",
            "source": "medrxiv",
            "resource_type": "preprint",
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Check medRxiv API health and availability.
        
        Returns:
            Health status with response time and availability
        """
        import time
        
        start_time = time.time()
        
        try:
            # Try to fetch a known preprint
            url = f"{MEDRXIV_API}/details/medrxiv/2020-01-01/2020-01-02/0/1"
            body, meta = await self._cached_get(url)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if body is not None and "collection" in body:
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
                "medrxiv_health_check_failed",
                error=str(e),
                response_time_ms=response_time_ms
            )
            return {
                "status": "unhealthy",
                "response_time_ms": response_time_ms,
                "available": False,
                "error": str(e)
            }
