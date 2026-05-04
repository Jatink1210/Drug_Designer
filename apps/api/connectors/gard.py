"""
GARD Connector - Disease & Ontology Family

Implements FR-CONN-001: Connector Portfolio
Task 8.2.5: Implement GARD connector

GARD (Genetic and Rare Diseases Information Center) provides information
about rare and genetic diseases.

API Documentation: https://rarediseases.info.nih.gov/api (unofficial)
Rate Limits: 5 requests/second
Authentication: None required (public access)
Performance Target: p95 <3s
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger()

GARD_API = "https://rarediseases.info.nih.gov/api"


class GARDConnector(BaseConnector):
    """
    Search GARD for rare disease information.
    
    Features:
    - Circuit breaker pattern (via ResilientClient)
    - Rate limiting (5 RPS)
    - Provenance tracking
    - Two-tier caching (Redis + in-memory)
    - Performance: p95 <3s
    """

    name = "gard"
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
        Search GARD for rare diseases.
        
        Args:
            query: Search query string (disease name)
            limit: Maximum number of results (default: 20)
        
        Returns:
            List of normalized disease records
        
        Performance: p95 <3s
        """
        params = {
            "query": query,
            "limit": limit
        }
        
        url = f"{GARD_API}/diseases"
        body, meta = await self._cached_get(url, params=params, extra_key=query)
        
        if body is None:
            log.warning(
                "gard_search_failed",
                query=query,
                meta=meta
            )
            return []
        
        # Parse response
        results = []
        diseases = body if isinstance(body, list) else body.get("diseases", [])
        
        for disease in diseases[:limit]:
            normalized = self.normalize(disease)
            
            # Add provenance
            normalized["provenance"] = self._prov(
                url=url,
                phash=meta.get("payload_hash", ""),
                confidence=0.95,
                reasoning="Retrieved from GARD API",
                ext_id=disease.get("gard_id", "")
            ).dict()
            
            results.append(normalized)
        
        log.info(
            "gard_search_complete",
            query=query,
            results_count=len(results),
            cache_hit=meta.get("cache_hit", False)
        )
        
        return results

    async def fetch_by_id(self, gard_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific GARD disease by ID.
        
        Args:
            gard_id: GARD disease ID (e.g., "GARD:0001234")
        
        Returns:
            Normalized disease record or None if not found
        
        Performance: p95 <3s
        """
        # Clean GARD ID
        clean_id = gard_id.replace("GARD:", "").replace("gard:", "")
        
        url = f"{GARD_API}/diseases/{clean_id}"
        body, meta = await self._cached_get(url)
        
        if body is None:
            log.warning(
                "gard_fetch_failed",
                gard_id=clean_id,
                meta=meta
            )
            return None
        
        normalized = self.normalize(body)
        
        # Add provenance
        normalized["provenance"] = self._prov(
            url=url,
            phash=meta.get("payload_hash", ""),
            confidence=1.0,
            reasoning="Retrieved by ID from GARD API",
            ext_id=clean_id
        ).dict()
        
        log.info(
            "gard_fetch_complete",
            gard_id=clean_id,
            cache_hit=meta.get("cache_hit", False)
        )
        
        return normalized

    async def extract_evidence(self, gard_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records from a GARD disease.
        
        Args:
            gard_id: GARD disease ID
        
        Returns:
            List of evidence records
        """
        disease = await self.fetch_by_id(gard_id)
        if not disease:
            return []
        
        evidence = []
        
        if disease.get("description"):
            evidence.append({
                "type": "description",
                "content": disease["description"],
                "source": "gard",
                "gard_id": gard_id,
                "confidence": 0.95
            })
        
        if disease.get("name"):
            evidence.append({
                "type": "name",
                "content": disease["name"],
                "source": "gard",
                "gard_id": gard_id,
                "confidence": 0.95
            })
        
        if disease.get("synonyms"):
            evidence.append({
                "type": "synonyms",
                "content": ", ".join(disease["synonyms"]),
                "source": "gard",
                "gard_id": gard_id,
                "confidence": 0.9
            })
        
        return evidence

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize GARD API response to standard format.
        
        Args:
            raw_data: Raw API response item
        
        Returns:
            Normalized disease record
        """
        gard_id = raw_data.get("gard_id", "")
        name = strip_html(raw_data.get("name", ""))
        description = strip_html(raw_data.get("description", ""))
        
        # Extract synonyms
        synonyms = raw_data.get("synonyms", [])
        if isinstance(synonyms, str):
            synonyms = [s.strip() for s in synonyms.split(";")]
        
        return {
            "id": gard_id,
            "gard_id": gard_id,
            "name": name,
            "description": description,
            "synonyms": synonyms,
            "orpha_number": raw_data.get("orpha_number", ""),
            "umls_cui": raw_data.get("umls_cui", ""),
            "icd10": raw_data.get("icd10", []),
            "source": "gard",
            "resource_type": "rare_disease",
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Check GARD API health and availability.
        
        Returns:
            Health status with response time and availability
        """
        import time
        
        start_time = time.time()
        
        try:
            params = {"query": "diabetes", "limit": 1}
            url = f"{GARD_API}/diseases"
            body, meta = await self._cached_get(url, params=params)
            
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
                    "error": "No response from GARD API",
                    "cache_hit": meta.get("cache_hit", False)
                }
        
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            log.error(
                "gard_health_check_failed",
                error=str(e),
                response_time_ms=response_time_ms
            )
            return {
                "status": "unhealthy",
                "response_time_ms": response_time_ms,
                "available": False,
                "error": str(e)
            }
