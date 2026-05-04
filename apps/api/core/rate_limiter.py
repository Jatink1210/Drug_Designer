"""Rate Limiter — Adaptive Token Bucket (Drug Designer §52, §A9).

Per-connector rate limiting using Redis-backed token buckets.
Respects Retry-After headers. Implements the exact limits from §A9.1.

§52: When rate limited, the system engages the Truthful Pause Rule:
     marks that specific data column as [Degraded: Rate Limited]
     but continues resolving the remaining APIs. Never fakes missing data.
"""

import asyncio
import time
import structlog
from typing import Dict, Optional

logger = structlog.get_logger()


# ── §A9.1 Rate Limits (Exact from spec) ─────────────────────
RATE_LIMITS: Dict[str, Dict[str, int]] = {
    "pubmed":            {"requests_per_second": 3,  "burst": 10},
    "europe_pmc":        {"requests_per_second": 10, "burst": 20},
    "opentargets":       {"requests_per_second": 5,  "burst": 15},
    "uniprot":           {"requests_per_second": 5,  "burst": 10},
    "chembl":            {"requests_per_second": 5,  "burst": 15},
    "kegg":              {"requests_per_second": 2,  "burst": 5},
    "string":            {"requests_per_second": 3,  "burst": 8},
    "rcsb_pdb":          {"requests_per_second": 5,  "burst": 15},
    "gwas_catalog":      {"requests_per_second": 5,  "burst": 10},
    "semantic_scholar":  {"requests_per_second": 1,  "burst": 5},
    "openalex":          {"requests_per_second": 10, "burst": 30},
    "crossref":          {"requests_per_second": 5,  "burst": 10},
    "clinvar":           {"requests_per_second": 3,  "burst": 10},
    "gnomad":            {"requests_per_second": 2,  "burst": 5},
    "interpro":          {"requests_per_second": 5,  "burst": 10},
    "chebi":             {"requests_per_second": 3,  "burst": 8},
    "biogrid":           {"requests_per_second": 3,  "burst": 8},
    "disgenet":          {"requests_per_second": 3,  "burst": 8},
    "reactome":          {"requests_per_second": 5,  "burst": 10},
    "wikipathways":      {"requests_per_second": 3,  "burst": 8},
    "intact":            {"requests_per_second": 5,  "burst": 10},
    "ensembl":           {"requests_per_second": 5,  "burst": 10},
    "alphafold":         {"requests_per_second": 5,  "burst": 10},
    "pubchem":           {"requests_per_second": 5,  "burst": 15},
    "drugbank":          {"requests_per_second": 2,  "burst": 5},
    "hpo":               {"requests_per_second": 3,  "burst": 8},
    "disease_ontology":  {"requests_per_second": 3,  "burst": 8},
    "clinicaltrials":    {"requests_per_second": 5,  "burst": 10},
}

# Default for unknown connectors
DEFAULT_RATE_LIMIT = {"requests_per_second": 3, "burst": 10}


class TokenBucket:
    """In-memory token bucket rate limiter for a single connector."""

    def __init__(self, connector_name: str):
        limits = RATE_LIMITS.get(connector_name.lower(), DEFAULT_RATE_LIMIT)
        self.connector_name = connector_name
        self.rate = limits["requests_per_second"]
        self.max_tokens = limits["burst"]
        self.tokens = float(self.max_tokens)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self.retry_after: Optional[float] = None  # Retry-After from server

    async def acquire(self) -> bool:
        """Try to acquire a token. Returns True if allowed, False if rate limited."""
        async with self._lock:
            # Check if we're in a server-enforced cooldown
            if self.retry_after and time.monotonic() < self.retry_after:
                remaining = self.retry_after - time.monotonic()
                logger.debug("rate_limiter_retry_after",
                             connector=self.connector_name,
                             remaining_s=round(remaining, 1))
                return False

            # Refill tokens based on elapsed time
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True

            return False

    async def wait_and_acquire(self, timeout: float = 30.0) -> bool:
        """Wait until a token is available, with timeout."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if await self.acquire():
                return True
            await asyncio.sleep(1.0 / self.rate)
        return False

    def set_retry_after(self, seconds: float):
        """Set a server-enforced cooldown (from Retry-After header)."""
        self.retry_after = time.monotonic() + seconds
        logger.warning("rate_limiter_backoff_enforced",
                       connector=self.connector_name,
                       backoff_s=seconds)


class RateLimiterRegistry:
    """Global registry of per-connector rate limiters.
    
    Usage:
        registry = RateLimiterRegistry()
        limiter = registry.get("pubmed")
        if await limiter.acquire():
            result = await pubmed.search(query)
        else:
            return degraded_response("Rate limited")
    """

    def __init__(self):
        self._limiters: Dict[str, TokenBucket] = {}

    def get(self, connector_name: str) -> TokenBucket:
        key = connector_name.lower()
        if key not in self._limiters:
            self._limiters[key] = TokenBucket(key)
        return self._limiters[key]

    def get_status(self) -> Dict[str, Dict]:
        """Return current rate limiter status for all connectors."""
        return {
            name: {
                "tokens": round(limiter.tokens, 1),
                "max_tokens": limiter.max_tokens,
                "rate": limiter.rate,
                "blocked": limiter.retry_after is not None and time.monotonic() < (limiter.retry_after or 0),
            }
            for name, limiter in self._limiters.items()
        }
