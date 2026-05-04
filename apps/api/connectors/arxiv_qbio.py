"""
arXiv q-bio Connector - Literature Family

Implements FR-CONN-001: Connector Portfolio
Task 8.1.2: Implement arXiv q-bio connector

arXiv is a preprint repository for scientific papers.
q-bio category covers quantitative biology papers.

API Documentation: https://arxiv.org/help/api/
Rate Limits: 3 requests/second (per arXiv guidelines)
Authentication: None required (public API)
Performance Target: p95 <3s
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET
import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger()

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}


class ArXivQBioConnector(BaseConnector):
    """
    Search arXiv q-bio (quantitative biology) preprints.
    
    Features:
    - Circuit breaker pattern (via ResilientClient)
    - Rate limiting (3 RPS per arXiv guidelines)
    - Provenance tracking
    - Two-tier caching (Redis + in-memory)
    - Performance: p95 <3s
    """

    name = "arxiv_qbio"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 3.0  # arXiv recommends 3 seconds between requests
    rate_limit_burst = 5
    http_timeout = 15.0
    max_retries = 3
    degradation_mode = "degrade"

    async def search(
        self, 
        query: str, 
        limit: int = 20,
        category: str = "q-bio",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search arXiv q-bio preprints.
        
        Args:
            query: Search query string
            limit: Maximum number of results (default: 20)
            category: arXiv category (default: "q-bio" for quantitative biology)
        
        Returns:
            List of normalized preprint records
        
        Performance: p95 <3s
        """
        # Build arXiv API query
        # Format: cat:q-bio* AND all:query
        search_query = f"cat:{category}* AND all:{query}"
        
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        
        body, meta = await self._cached_get(ARXIV_API, params=params, extra_key=query)
        
        if body is None:
            log.warning(
                "arxiv_search_failed",
                query=query,
                meta=meta
            )
            return []
        
        # Parse XML response
        try:
            results = self._parse_arxiv_xml(body, meta)
            
            log.info(
                "arxiv_search_complete",
                query=query,
                results_count=len(results),
                cache_hit=meta.get("cache_hit", False)
            )
            
            return results[:limit]
        
        except Exception as e:
            log.error(
                "arxiv_parse_error",
                query=query,
                error=str(e)
            )
            return []

    async def fetch_by_id(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific arXiv preprint by ID.
        
        Args:
            arxiv_id: arXiv identifier (e.g., "2101.12345" or "q-bio/0601001")
        
        Returns:
            Normalized preprint record or None if not found
        
        Performance: p95 <3s
        """
        # Clean arXiv ID (remove prefix if present)
        clean_id = arxiv_id.replace("arXiv:", "").replace("http://arxiv.org/abs/", "")
        
        params = {
            "id_list": clean_id,
            "max_results": 1
        }
        
        body, meta = await self._cached_get(ARXIV_API, params=params)
        
        if body is None:
            log.warning(
                "arxiv_fetch_failed",
                arxiv_id=clean_id,
                meta=meta
            )
            return None
        
        # Parse XML response
        try:
            results = self._parse_arxiv_xml(body, meta)
            
            if not results:
                log.warning(
                    "arxiv_not_found",
                    arxiv_id=clean_id
                )
                return None
            
            log.info(
                "arxiv_fetch_complete",
                arxiv_id=clean_id,
                cache_hit=meta.get("cache_hit", False)
            )
            
            return results[0]
        
        except Exception as e:
            log.error(
                "arxiv_parse_error",
                arxiv_id=clean_id,
                error=str(e)
            )
            return None

    async def count(self, query: str) -> Optional[int]:
        """
        Get total count of preprints matching query.
        
        Args:
            query: Search query string
        
        Returns:
            Total count from arXiv API
        """
        search_query = f"cat:q-bio* AND all:{query}"
        
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": 1  # We only need the total count
        }
        
        body, meta = await self._cached_get(ARXIV_API, params=params, extra_key=f"count_{query}")
        
        if body is None:
            return None
        
        try:
            root = ET.fromstring(body) if isinstance(body, str) else ET.fromstring(str(body))
            total_results = root.find(".//atom:totalResults", ARXIV_NAMESPACE)
            
            if total_results is not None and total_results.text:
                return int(total_results.text)
        
        except Exception as e:
            log.error(
                "arxiv_count_error",
                query=query,
                error=str(e)
            )
        
        return None

    async def extract_evidence(self, arxiv_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records from an arXiv preprint.
        
        Args:
            arxiv_id: arXiv identifier
        
        Returns:
            List of evidence records (abstract, title, etc.)
        """
        preprint = await self.fetch_by_id(arxiv_id)
        if not preprint:
            return []
        
        evidence = []
        
        # Abstract as evidence
        if preprint.get("abstract"):
            evidence.append({
                "type": "abstract",
                "content": preprint["abstract"],
                "source": "arxiv_qbio",
                "arxiv_id": arxiv_id,
                "confidence": 0.9
            })
        
        # Title as evidence
        if preprint.get("title"):
            evidence.append({
                "type": "title",
                "content": preprint["title"],
                "source": "arxiv_qbio",
                "arxiv_id": arxiv_id,
                "confidence": 0.95
            })
        
        return evidence

    def _parse_arxiv_xml(self, xml_data: str, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse arXiv API XML response.
        
        Args:
            xml_data: XML response from arXiv API
            meta: Metadata from HTTP request
        
        Returns:
            List of normalized preprint records
        """
        root = ET.fromstring(xml_data) if isinstance(xml_data, str) else ET.fromstring(str(xml_data))
        
        results = []
        
        for entry in root.findall(".//atom:entry", ARXIV_NAMESPACE):
            # Extract fields
            arxiv_id = self._get_text(entry, ".//atom:id", ARXIV_NAMESPACE)
            if arxiv_id:
                arxiv_id = arxiv_id.replace("http://arxiv.org/abs/", "")
            
            title = self._get_text(entry, ".//atom:title", ARXIV_NAMESPACE)
            abstract = self._get_text(entry, ".//atom:summary", ARXIV_NAMESPACE)
            published = self._get_text(entry, ".//atom:published", ARXIV_NAMESPACE)
            updated = self._get_text(entry, ".//atom:updated", ARXIV_NAMESPACE)
            
            # Extract authors
            authors = []
            for author in entry.findall(".//atom:author", ARXIV_NAMESPACE):
                name = self._get_text(author, ".//atom:name", ARXIV_NAMESPACE)
                if name:
                    authors.append(name)
            
            # Extract categories
            categories = []
            for category in entry.findall(".//atom:category", ARXIV_NAMESPACE):
                term = category.get("term")
                if term:
                    categories.append(term)
            
            # Extract PDF link
            pdf_link = None
            for link in entry.findall(".//atom:link", ARXIV_NAMESPACE):
                if link.get("title") == "pdf":
                    pdf_link = link.get("href")
                    break
            
            normalized = {
                "id": arxiv_id,
                "arxiv_id": arxiv_id,
                "title": strip_html(title) if title else "",
                "abstract": strip_html(abstract) if abstract else "",
                "authors": authors,
                "authors_string": ", ".join(authors),
                "published": published,
                "updated": updated,
                "categories": categories,
                "primary_category": categories[0] if categories else "",
                "pdf_url": pdf_link,
                "abs_url": f"http://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
                "server": "arxiv",
                "source": "arxiv_qbio",
                "resource_type": "preprint",
            }
            
            # Add provenance
            normalized["provenance"] = self._prov(
                url=ARXIV_API,
                phash=meta.get("payload_hash", ""),
                confidence=0.95,
                reasoning="Retrieved from arXiv API",
                ext_id=arxiv_id or ""
            ).dict()
            
            results.append(normalized)
        
        return results

    def _get_text(self, element: ET.Element, path: str, namespace: Dict[str, str]) -> Optional[str]:
        """Helper to safely extract text from XML element."""
        found = element.find(path, namespace)
        return found.text.strip() if found is not None and found.text else None

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize arXiv data (already normalized in _parse_arxiv_xml).
        
        Args:
            raw_data: Already normalized data
        
        Returns:
            Normalized preprint record
        """
        return raw_data

    async def health_check(self) -> Dict[str, Any]:
        """
        Check arXiv API health and availability.
        
        Returns:
            Health status with response time and availability
        """
        import time
        
        start_time = time.time()
        
        try:
            # Try a simple search
            params = {
                "search_query": "cat:q-bio*",
                "start": 0,
                "max_results": 1
            }
            
            body, meta = await self._cached_get(ARXIV_API, params=params)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if body is not None:
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
                    "error": "No response from arXiv API",
                    "cache_hit": meta.get("cache_hit", False)
                }
        
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            log.error(
                "arxiv_health_check_failed",
                error=str(e),
                response_time_ms=response_time_ms
            )
            return {
                "status": "unhealthy",
                "response_time_ms": response_time_ms,
                "available": False,
                "error": str(e)
            }
