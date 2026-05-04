"""
GTR Connector - Disease & Ontology Family

Implements FR-CONN-001: Connector Portfolio
Task 8.2.4: Implement GTR connector

GTR (Genetic Testing Registry) provides information about genetic tests.
Maintained by NCBI.

API Documentation: https://www.ncbi.nlm.nih.gov/gtr/ (uses E-utilities)
Rate Limits: 3 requests/second (10 with API key)
Authentication: Optional API key for higher rate limits
Performance Target: p95 <3s
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger()

GTR_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class GTRConnector(BaseConnector):
    """
    Search GTR for genetic testing information.
    
    Features:
    - Circuit breaker pattern (via ResilientClient)
    - Rate limiting (3 RPS, 10 RPS with API key)
    - Provenance tracking
    - Two-tier caching (Redis + in-memory)
    - Performance: p95 <3s
    """

    name = "gtr"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 3.0  # 10.0 with API key
    rate_limit_burst = 10
    http_timeout = 15.0
    max_retries = 3
    degradation_mode = "degrade"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key
        if api_key:
            self.rate_limit_rps = 10.0

    async def search(
        self, 
        query: str, 
        limit: int = 20,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search GTR for genetic tests.
        
        Args:
            query: Search query string (gene, disease, or test name)
            limit: Maximum number of results (default: 20)
        
        Returns:
            List of normalized test records
        
        Performance: p95 <3s
        """
        # Step 1: Search for IDs using esearch
        search_params = {
            "db": "gtr",
            "term": query,
            "retmax": limit,
            "retmode": "json"
        }
        
        if self.api_key:
            search_params["api_key"] = self.api_key
        
        search_url = f"{GTR_API}/esearch.fcgi"
        search_body, search_meta = await self._cached_get(
            search_url, 
            params=search_params,
            extra_key=query
        )
        
        if search_body is None or "esearchresult" not in search_body:
            log.warning(
                "gtr_search_failed",
                query=query,
                meta=search_meta
            )
            return []
        
        # Extract IDs
        id_list = search_body.get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            log.info(
                "gtr_no_results",
                query=query
            )
            return []
        
        # Step 2: Fetch details using esummary
        summary_params = {
            "db": "gtr",
            "id": ",".join(id_list),
            "retmode": "json"
        }
        
        if self.api_key:
            summary_params["api_key"] = self.api_key
        
        summary_url = f"{GTR_API}/esummary.fcgi"
        summary_body, summary_meta = await self._cached_get(
            summary_url,
            params=summary_params,
            extra_key=query
        )
        
        if summary_body is None or "result" not in summary_body:
            log.warning(
                "gtr_summary_failed",
                query=query,
                ids=id_list,
                meta=summary_meta
            )
            return []
        
        # Parse results
        results = []
        result_data = summary_body.get("result", {})
        
        for gtr_id in id_list:
            if gtr_id in result_data:
                test = result_data[gtr_id]
                normalized = self.normalize(test)
                
                # Add provenance
                normalized["provenance"] = self._prov(
                    url=summary_url,
                    phash=summary_meta.get("payload_hash", ""),
                    confidence=0.95,
                    reasoning="Retrieved from GTR via NCBI E-utilities",
                    ext_id=gtr_id
                ).dict()
                
                results.append(normalized)
        
        log.info(
            "gtr_search_complete",
            query=query,
            results_count=len(results),
            cache_hit=search_meta.get("cache_hit", False)
        )
        
        return results[:limit]

    async def fetch_by_id(self, gtr_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific GTR test by ID.
        
        Args:
            gtr_id: GTR test ID
        
        Returns:
            Normalized test record or None if not found
        
        Performance: p95 <3s
        """
        params = {
            "db": "gtr",
            "id": gtr_id,
            "retmode": "json"
        }
        
        if self.api_key:
            params["api_key"] = self.api_key
        
        url = f"{GTR_API}/esummary.fcgi"
        body, meta = await self._cached_get(url, params=params)
        
        if body is None or "result" not in body:
            log.warning(
                "gtr_fetch_failed",
                gtr_id=gtr_id,
                meta=meta
            )
            return None
        
        result_data = body.get("result", {})
        
        if gtr_id not in result_data:
            log.warning(
                "gtr_not_found",
                gtr_id=gtr_id
            )
            return None
        
        test = result_data[gtr_id]
        normalized = self.normalize(test)
        
        # Add provenance
        normalized["provenance"] = self._prov(
            url=url,
            phash=meta.get("payload_hash", ""),
            confidence=1.0,
            reasoning="Retrieved by ID from GTR via NCBI E-utilities",
            ext_id=gtr_id
        ).dict()
        
        log.info(
            "gtr_fetch_complete",
            gtr_id=gtr_id,
            cache_hit=meta.get("cache_hit", False)
        )
        
        return normalized

    async def extract_evidence(self, gtr_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records from a GTR test.
        
        Args:
            gtr_id: GTR test ID
        
        Returns:
            List of evidence records
        """
        test = await self.fetch_by_id(gtr_id)
        if not test:
            return []
        
        evidence = []
        
        if test.get("test_name"):
            evidence.append({
                "type": "test_name",
                "content": test["test_name"],
                "source": "gtr",
                "gtr_id": gtr_id,
                "confidence": 0.95
            })
        
        if test.get("purpose"):
            evidence.append({
                "type": "purpose",
                "content": test["purpose"],
                "source": "gtr",
                "gtr_id": gtr_id,
                "confidence": 0.9
            })
        
        return evidence

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize GTR API response to standard format.
        
        Args:
            raw_data: Raw API response item
        
        Returns:
            Normalized test record
        """
        gtr_id = raw_data.get("uid", "")
        test_name = strip_html(raw_data.get("test_name", ""))
        
        return {
            "id": gtr_id,
            "gtr_id": gtr_id,
            "test_name": test_name,
            "purpose": raw_data.get("purpose", ""),
            "methodology": raw_data.get("methodology", ""),
            "genes": raw_data.get("genes", []),
            "conditions": raw_data.get("conditions", []),
            "laboratory": raw_data.get("laboratory", ""),
            "source": "gtr",
            "resource_type": "genetic_test",
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Check GTR API health and availability.
        
        Returns:
            Health status with response time and availability
        """
        import time
        
        start_time = time.time()
        
        try:
            params = {
                "db": "gtr",
                "term": "BRCA1",
                "retmax": 1,
                "retmode": "json"
            }
            
            if self.api_key:
                params["api_key"] = self.api_key
            
            url = f"{GTR_API}/esearch.fcgi"
            body, meta = await self._cached_get(url, params=params)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if body is not None and "esearchresult" in body:
                return {
                    "status": "healthy",
                    "response_time_ms": response_time_ms,
                    "available": True,
                    "error": None,
                    "cache_hit": meta.get("cache_hit", False),
                    "api_key_configured": self.api_key is not None
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
                "gtr_health_check_failed",
                error=str(e),
                response_time_ms=response_time_ms
            )
            return {
                "status": "unhealthy",
                "response_time_ms": response_time_ms,
                "available": False,
                "error": str(e)
            }
