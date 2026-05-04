"""
MedGen Connector - Disease & Ontology Family

Implements FR-CONN-001: Connector Portfolio
Task 8.2.1: Implement MedGen connector

MedGen is NCBI's portal for medical genetics information.
Organizes information related to human medical genetics.

API Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25501/ (E-utilities)
Rate Limits: 3 requests/second (10 with API key)
Authentication: Optional API key for higher rate limits
Performance Target: p95 <3s
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger()

MEDGEN_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class MedGenConnector(BaseConnector):
    """
    Search MedGen for medical genetics information.
    
    Features:
    - Circuit breaker pattern (via ResilientClient)
    - Rate limiting (3 RPS, 10 RPS with API key)
    - Provenance tracking
    - Two-tier caching (Redis + in-memory)
    - Performance: p95 <3s
    """

    name = "medgen"
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
            self.rate_limit_rps = 10.0  # Higher rate limit with API key

    async def search(
        self, 
        query: str, 
        limit: int = 20,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search MedGen for medical genetics concepts.
        
        Args:
            query: Search query string
            limit: Maximum number of results (default: 20)
        
        Returns:
            List of normalized concept records
        
        Performance: p95 <3s
        """
        # Step 1: Search for IDs using esearch
        search_params = {
            "db": "medgen",
            "term": query,
            "retmax": limit,
            "retmode": "json"
        }
        
        if self.api_key:
            search_params["api_key"] = self.api_key
        
        search_url = f"{MEDGEN_API}/esearch.fcgi"
        search_body, search_meta = await self._cached_get(
            search_url, 
            params=search_params,
            extra_key=query
        )
        
        if search_body is None or "esearchresult" not in search_body:
            log.warning(
                "medgen_search_failed",
                query=query,
                meta=search_meta
            )
            return []
        
        # Extract IDs
        id_list = search_body.get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            log.info(
                "medgen_no_results",
                query=query
            )
            return []
        
        # Step 2: Fetch details using esummary
        summary_params = {
            "db": "medgen",
            "id": ",".join(id_list),
            "retmode": "json"
        }
        
        if self.api_key:
            summary_params["api_key"] = self.api_key
        
        summary_url = f"{MEDGEN_API}/esummary.fcgi"
        summary_body, summary_meta = await self._cached_get(
            summary_url,
            params=summary_params,
            extra_key=query
        )
        
        if summary_body is None or "result" not in summary_body:
            log.warning(
                "medgen_summary_failed",
                query=query,
                ids=id_list,
                meta=summary_meta
            )
            return []
        
        # Parse results
        results = []
        result_data = summary_body.get("result", {})
        
        for medgen_id in id_list:
            if medgen_id in result_data:
                concept = result_data[medgen_id]
                normalized = self.normalize(concept)
                
                # Add provenance
                normalized["provenance"] = self._prov(
                    url=summary_url,
                    phash=summary_meta.get("payload_hash", ""),
                    confidence=0.95,
                    reasoning="Retrieved from MedGen via NCBI E-utilities",
                    ext_id=medgen_id
                ).dict()
                
                results.append(normalized)
        
        log.info(
            "medgen_search_complete",
            query=query,
            results_count=len(results),
            cache_hit=search_meta.get("cache_hit", False)
        )
        
        return results[:limit]

    async def fetch_by_id(self, medgen_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific MedGen concept by ID.
        
        Args:
            medgen_id: MedGen concept ID (CUI)
        
        Returns:
            Normalized concept record or None if not found
        
        Performance: p95 <3s
        """
        params = {
            "db": "medgen",
            "id": medgen_id,
            "retmode": "json"
        }
        
        if self.api_key:
            params["api_key"] = self.api_key
        
        url = f"{MEDGEN_API}/esummary.fcgi"
        body, meta = await self._cached_get(url, params=params)
        
        if body is None or "result" not in body:
            log.warning(
                "medgen_fetch_failed",
                medgen_id=medgen_id,
                meta=meta
            )
            return None
        
        result_data = body.get("result", {})
        
        if medgen_id not in result_data:
            log.warning(
                "medgen_not_found",
                medgen_id=medgen_id
            )
            return None
        
        concept = result_data[medgen_id]
        normalized = self.normalize(concept)
        
        # Add provenance
        normalized["provenance"] = self._prov(
            url=url,
            phash=meta.get("payload_hash", ""),
            confidence=1.0,
            reasoning="Retrieved by ID from MedGen via NCBI E-utilities",
            ext_id=medgen_id
        ).dict()
        
        log.info(
            "medgen_fetch_complete",
            medgen_id=medgen_id,
            cache_hit=meta.get("cache_hit", False)
        )
        
        return normalized

    async def count(self, query: str) -> Optional[int]:
        """
        Get total count of concepts matching query.
        
        Args:
            query: Search query string
        
        Returns:
            Total count from MedGen
        """
        params = {
            "db": "medgen",
            "term": query,
            "rettype": "count",
            "retmode": "json"
        }
        
        if self.api_key:
            params["api_key"] = self.api_key
        
        url = f"{MEDGEN_API}/esearch.fcgi"
        body, meta = await self._cached_get(url, params=params, extra_key=f"count_{query}")
        
        if body is None or "esearchresult" not in body:
            return None
        
        count = body.get("esearchresult", {}).get("count")
        return int(count) if count else None

    async def extract_evidence(self, medgen_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records from a MedGen concept.
        
        Args:
            medgen_id: MedGen concept ID
        
        Returns:
            List of evidence records (definition, synonyms, etc.)
        """
        concept = await self.fetch_by_id(medgen_id)
        if not concept:
            return []
        
        evidence = []
        
        # Definition as evidence
        if concept.get("definition"):
            evidence.append({
                "type": "definition",
                "content": concept["definition"],
                "source": "medgen",
                "medgen_id": medgen_id,
                "confidence": 0.95
            })
        
        # Title as evidence
        if concept.get("title"):
            evidence.append({
                "type": "title",
                "content": concept["title"],
                "source": "medgen",
                "medgen_id": medgen_id,
                "confidence": 0.95
            })
        
        # Synonyms as evidence
        if concept.get("synonyms"):
            evidence.append({
                "type": "synonyms",
                "content": ", ".join(concept["synonyms"]),
                "source": "medgen",
                "medgen_id": medgen_id,
                "confidence": 0.9
            })
        
        return evidence

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize MedGen API response to standard format.
        
        Args:
            raw_data: Raw API response item
        
        Returns:
            Normalized concept record
        """
        # Extract fields
        medgen_id = raw_data.get("uid", "")
        title = strip_html(raw_data.get("title", ""))
        definition = strip_html(raw_data.get("definition", ""))
        
        # Extract concept ID (CUI)
        concept_id = raw_data.get("conceptid", "")
        
        # Extract semantic types
        semantic_types = raw_data.get("semantictype", [])
        if isinstance(semantic_types, str):
            semantic_types = [semantic_types]
        
        # Extract synonyms
        synonyms_str = raw_data.get("synonyms_cased", "")
        synonyms = [s.strip() for s in synonyms_str.split("|")] if synonyms_str else []
        
        return {
            "id": medgen_id,
            "medgen_id": medgen_id,
            "concept_id": concept_id,
            "cui": concept_id,  # UMLS Concept Unique Identifier
            "title": title,
            "definition": definition,
            "semantic_types": semantic_types,
            "synonyms": synonyms,
            "source": "medgen",
            "resource_type": "medical_concept",
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Check MedGen API health and availability.
        
        Returns:
            Health status with response time and availability
        """
        import time
        
        start_time = time.time()
        
        try:
            # Try a simple search
            params = {
                "db": "medgen",
                "term": "diabetes",
                "retmax": 1,
                "retmode": "json"
            }
            
            if self.api_key:
                params["api_key"] = self.api_key
            
            url = f"{MEDGEN_API}/esearch.fcgi"
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
                "medgen_health_check_failed",
                error=str(e),
                response_time_ms=response_time_ms
            )
            return {
                "status": "unhealthy",
                "response_time_ms": response_time_ms,
                "available": False,
                "error": str(e)
            }
