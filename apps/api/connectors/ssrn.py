"""
SSRN Connector - Literature Family

Implements FR-CONN-001: Connector Portfolio
Task 8.1.3: Implement SSRN connector

SSRN (Social Science Research Network) is a repository for scholarly research.
Includes health economics, health policy, and medical research papers.

API Documentation: https://www.ssrn.com/ (web scraping approach)
Rate Limits: 5 requests/second (conservative)
Authentication: None required (public access)
Performance Target: p95 <3s

Note: SSRN doesn't have a public API, so this connector uses web scraping
with proper rate limiting and caching.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import re
import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger()

SSRN_BASE = "https://www.ssrn.com"
SSRN_SEARCH = f"{SSRN_BASE}/index.cfm/en/janda/search"


class SSRNConnector(BaseConnector):
    """
    Search SSRN papers via web scraping.
    
    Features:
    - Circuit breaker pattern (via ResilientClient)
    - Rate limiting (5 RPS)
    - Provenance tracking
    - Two-tier caching (Redis + in-memory)
    - Performance: p95 <3s
    
    Note: SSRN doesn't provide a public API, so this connector
    uses web scraping with proper rate limiting and caching.
    """

    name = "ssrn"
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
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search SSRN papers.
        
        Args:
            query: Search query string
            limit: Maximum number of results (default: 20)
        
        Returns:
            List of normalized paper records
        
        Performance: p95 <3s
        
        Note: This is a simplified implementation. In production,
        consider using SSRN's RSS feeds or partnering for API access.
        """
        # SSRN search parameters
        params = {
            "q": query,
            "sortBy": "relevance"
        }
        
        body, meta = await self._cached_get(SSRN_SEARCH, params=params, extra_key=query)
        
        if body is None:
            log.warning(
                "ssrn_search_failed",
                query=query,
                meta=meta
            )
            return []
        
        # Parse HTML response (simplified - in production use proper HTML parser)
        try:
            results = self._parse_ssrn_html(body, meta, limit)
            
            log.info(
                "ssrn_search_complete",
                query=query,
                results_count=len(results),
                cache_hit=meta.get("cache_hit", False)
            )
            
            return results[:limit]
        
        except Exception as e:
            log.error(
                "ssrn_parse_error",
                query=query,
                error=str(e)
            )
            return []

    async def fetch_by_id(self, ssrn_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific SSRN paper by ID.
        
        Args:
            ssrn_id: SSRN paper ID (e.g., "3456789")
        
        Returns:
            Normalized paper record or None if not found
        
        Performance: p95 <3s
        """
        # Clean SSRN ID
        clean_id = ssrn_id.replace("ssrn-", "").replace("SSRN-", "")
        
        url = f"{SSRN_BASE}/abstract={clean_id}"
        
        body, meta = await self._cached_get(url)
        
        if body is None:
            log.warning(
                "ssrn_fetch_failed",
                ssrn_id=clean_id,
                meta=meta
            )
            return None
        
        # Parse HTML response
        try:
            paper = self._parse_ssrn_paper(body, clean_id, meta)
            
            if not paper:
                log.warning(
                    "ssrn_not_found",
                    ssrn_id=clean_id
                )
                return None
            
            log.info(
                "ssrn_fetch_complete",
                ssrn_id=clean_id,
                cache_hit=meta.get("cache_hit", False)
            )
            
            return paper
        
        except Exception as e:
            log.error(
                "ssrn_parse_error",
                ssrn_id=clean_id,
                error=str(e)
            )
            return None

    async def count(self, query: str) -> Optional[int]:
        """
        Get total count of papers matching query.
        
        Args:
            query: Search query string
        
        Returns:
            Total count or None if unavailable
        """
        # SSRN doesn't provide easy count access via web scraping
        return None

    async def extract_evidence(self, ssrn_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records from an SSRN paper.
        
        Args:
            ssrn_id: SSRN paper ID
        
        Returns:
            List of evidence records (abstract, title, etc.)
        """
        paper = await self.fetch_by_id(ssrn_id)
        if not paper:
            return []
        
        evidence = []
        
        # Abstract as evidence
        if paper.get("abstract"):
            evidence.append({
                "type": "abstract",
                "content": paper["abstract"],
                "source": "ssrn",
                "ssrn_id": ssrn_id,
                "confidence": 0.9
            })
        
        # Title as evidence
        if paper.get("title"):
            evidence.append({
                "type": "title",
                "content": paper["title"],
                "source": "ssrn",
                "ssrn_id": ssrn_id,
                "confidence": 0.95
            })
        
        return evidence

    def _parse_ssrn_html(self, html: str, meta: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """
        Parse SSRN search results HTML.
        
        Args:
            html: HTML response from SSRN
            meta: Metadata from HTTP request
            limit: Maximum number of results
        
        Returns:
            List of normalized paper records
        
        Note: This is a simplified implementation. In production,
        use a proper HTML parser like BeautifulSoup or lxml.
        """
        results = []
        
        # Simplified parsing - extract paper IDs from links
        # Pattern: /abstract=1234567
        id_pattern = r'/abstract=(\d+)'
        matches = re.findall(id_pattern, html)
        
        # Get unique IDs
        unique_ids = list(dict.fromkeys(matches))[:limit]
        
        for ssrn_id in unique_ids:
            # Create basic record (full details would require fetching each paper)
            normalized = {
                "id": ssrn_id,
                "ssrn_id": ssrn_id,
                "title": f"SSRN Paper {ssrn_id}",  # Placeholder
                "abstract": "",  # Would need to fetch full paper
                "authors": [],
                "date": "",
                "url": f"{SSRN_BASE}/abstract={ssrn_id}",
                "server": "ssrn",
                "source": "ssrn",
                "resource_type": "paper",
            }
            
            # Add provenance
            normalized["provenance"] = self._prov(
                url=SSRN_SEARCH,
                phash=meta.get("payload_hash", ""),
                confidence=0.85,
                reasoning="Retrieved from SSRN search (web scraping)",
                ext_id=ssrn_id
            ).dict()
            
            results.append(normalized)
        
        return results

    def _parse_ssrn_paper(self, html: str, ssrn_id: str, meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse SSRN paper page HTML.
        
        Args:
            html: HTML response from SSRN paper page
            ssrn_id: SSRN paper ID
            meta: Metadata from HTTP request
        
        Returns:
            Normalized paper record or None
        
        Note: This is a simplified implementation. In production,
        use a proper HTML parser like BeautifulSoup or lxml.
        """
        # Simplified parsing - extract title and abstract
        title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1) if title_match else f"SSRN Paper {ssrn_id}"
        
        # Clean title
        title = strip_html(title).replace(" :: SSRN", "").strip()
        
        # Try to extract abstract (simplified)
        abstract_match = re.search(
            r'<div[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</div>',
            html,
            re.IGNORECASE | re.DOTALL
        )
        abstract = ""
        if abstract_match:
            abstract = strip_html(abstract_match.group(1)).strip()
        
        normalized = {
            "id": ssrn_id,
            "ssrn_id": ssrn_id,
            "title": title,
            "abstract": abstract,
            "authors": [],  # Would need more sophisticated parsing
            "date": "",  # Would need more sophisticated parsing
            "url": f"{SSRN_BASE}/abstract={ssrn_id}",
            "server": "ssrn",
            "source": "ssrn",
            "resource_type": "paper",
        }
        
        # Add provenance
        normalized["provenance"] = self._prov(
            url=f"{SSRN_BASE}/abstract={ssrn_id}",
            phash=meta.get("payload_hash", ""),
            confidence=0.9,
            reasoning="Retrieved from SSRN paper page (web scraping)",
            ext_id=ssrn_id
        ).dict()
        
        return normalized

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize SSRN data (already normalized in parsing methods).
        
        Args:
            raw_data: Already normalized data
        
        Returns:
            Normalized paper record
        """
        return raw_data

    async def health_check(self) -> Dict[str, Any]:
        """
        Check SSRN availability.
        
        Returns:
            Health status with response time and availability
        """
        import time
        
        start_time = time.time()
        
        try:
            # Try to access SSRN homepage
            body, meta = await self._cached_get(SSRN_BASE)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if body is not None:
                return {
                    "status": "healthy",
                    "response_time_ms": response_time_ms,
                    "available": True,
                    "error": None,
                    "cache_hit": meta.get("cache_hit", False),
                    "note": "SSRN uses web scraping - consider API partnership for production"
                }
            else:
                return {
                    "status": "degraded",
                    "response_time_ms": response_time_ms,
                    "available": True,
                    "error": "No response from SSRN",
                    "cache_hit": meta.get("cache_hit", False)
                }
        
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            log.error(
                "ssrn_health_check_failed",
                error=str(e),
                response_time_ms=response_time_ms
            )
            return {
                "status": "unhealthy",
                "response_time_ms": response_time_ms,
                "available": False,
                "error": str(e)
            }
