"""Enhanced base connector using ResilientClient + two-tier cache + provenance."""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, List, Optional, Tuple

import structlog

from core.http_client import ResilientClient, payload_hash
from core.cache import cache_key, async_two_tier_get, async_two_tier_put
from core.provenance import ProvenanceRecord
from core.rate_limiter import RateLimiterRegistry

log = structlog.get_logger()

DEFAULT_CACHE_TTL = 86400  # 24h

# Shared HTML tag stripper for cleaning API responses
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Remove HTML/XML tags from text (e.g. <i>, <b>, <sub>, <sup>, <span>)."""
    return _HTML_TAG_RE.sub("", text) if text else text

# Singleton rate limiter registry shared by all connectors (§A9.1)
_rl_registry = RateLimiterRegistry()


class BaseConnector(ABC):
    """All connectors: cached search + fetch_by_id + normalize + evidence extraction."""

    name: str = "base"
    cache_ttl: float = DEFAULT_CACHE_TTL

    # Per-connector rate limiting and degradation policy (§A9, §32)
    rate_limit_rps: float = 5.0          # Max requests per second
    rate_limit_burst: int = 10           # Burst allowance
    max_retries: int = 3                 # Max retry attempts before marking degraded
    degradation_mode: str = "degrade"    # "degrade" = mark partial, "abort" = stop pipeline
    http_timeout: float = 8.0            # Per-request HTTP timeout (§16.3: 8s max)

    def __init__(self) -> None:
        self._client = ResilientClient(timeout=self.http_timeout)

    async def close(self) -> None:
        await self._client.close()

    # ── HTTP helpers (cached + rate-limited §A9.1) ────────
    async def _cached_get(
        self, url: str, params: Optional[Dict[str, Any]] = None, extra_key: str = ""
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        key = cache_key(self.name, url, str(params) + extra_key)
        cached = await async_two_tier_get(key)
        if cached is not None:
            return cached, {"cache_hit": True, "source": self.name}
        # §A9.1: Enforce per-connector rate limit before HTTP call
        limiter = _rl_registry.get(self.name)
        if not await limiter.wait_and_acquire(timeout=15.0):
            log.warning("rate_limited", connector=self.name, url=url)
            await self._track_health_stats(response_time_ms=0, is_error=False, is_rate_limited=True)
            return None, {"source": self.name, "rate_limited": True, "status": "degraded"}
        _t_start = time.time()
        body, meta = await self._client.get(url, params=params)
        t_elapsed_ms = round((time.time() - _t_start) * 1000, 1)
        await self._track_health_stats(
            response_time_ms=t_elapsed_ms,
            is_error=(body is None),
            is_rate_limited=False,
        )
        if body is not None:
            phash = payload_hash(body)
            await async_two_tier_put(key, self.name, url, body, ttl=self.cache_ttl, payload_hash=phash)
            meta["payload_hash"] = phash
        meta["source"] = self.name
        return body, meta

    async def _cached_post(
        self, url: str, json_body: Optional[Dict[str, Any]] = None, extra_key: str = ""
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        key = cache_key(self.name, url, str(json_body) + extra_key)
        cached = await async_two_tier_get(key)
        if cached is not None:
            return cached, {"cache_hit": True, "source": self.name}
        # §A9.1: Enforce per-connector rate limit before HTTP call
        limiter = _rl_registry.get(self.name)
        if not await limiter.wait_and_acquire(timeout=15.0):
            log.warning("rate_limited", connector=self.name, url=url)
            await self._track_health_stats(response_time_ms=0, is_error=False, is_rate_limited=True)
            return None, {"source": self.name, "rate_limited": True, "status": "degraded"}
        _t_start_post = time.time()
        body, meta = await self._client.post(url, json_body=json_body)
        t_elapsed_post_ms = round((time.time() - _t_start_post) * 1000, 1)
        await self._track_health_stats(
            response_time_ms=t_elapsed_post_ms,
            is_error=(body is None),
            is_rate_limited=False,
        )
        if body is not None:
            phash = payload_hash(body)
            await async_two_tier_put(key, self.name, url, body, ttl=self.cache_ttl, payload_hash=phash)
            meta["payload_hash"] = phash
        meta["source"] = self.name
        return body, meta

    async def _track_health_stats(
        self,
        response_time_ms: float,
        is_error: bool,
        is_rate_limited: bool,
    ) -> None:
        """Push rolling health stats to Redis for cockpit source-health (§D7).

        Keys (TTL 2h unless noted):
          source_health:{name}:latency        — list of last 100 response times (ms)
          source_health:{name}:errors         — error count (TTL 1h)
          source_health:{name}:ratelimit_hits — rate-limit hit count (TTL 1h)
        """
        try:
            from core.redis_client import get_redis_client
            redis = await get_redis_client()
            name = self.name
            # Rolling latency list (last 100 samples, TTL 2h)
            latency_key = f"source_health:{name}:latency"
            await redis.rpush(latency_key, str(response_time_ms))
            await redis.ltrim(latency_key, -100, -1)  # keep last 100
            await redis.expire(latency_key, 7200)  # 2h
            # Error counter (1h sliding window)
            if is_error:
                err_key = f"source_health:{name}:errors"
                await redis.incr(err_key)
                await redis.expire(err_key, 3600)
            # Rate-limit counter (1h sliding window)
            if is_rate_limited:
                rl_key = f"source_health:{name}:ratelimit_hits"
                await redis.incr(rl_key)
                await redis.expire(rl_key, 3600)
        except Exception:
            pass  # Redis unavailable — health tracking is non-blocking

    @classmethod
    async def get_health_stats(cls, connector_name: str) -> Dict[str, Any]:
        """Read rolling health stats for a connector from Redis (§D7)."""
        try:
            from core.redis_client import get_redis_client
            redis = await get_redis_client()
            latency_raw = await redis.lrange(f"source_health:{connector_name}:latency", 0, -1)
            lats = [float(x) for x in latency_raw] if latency_raw else []
            avg_ms = round(sum(lats) / len(lats), 1) if lats else None
            p95_ms = round(sorted(lats)[int(len(lats) * 0.95)], 1) if len(lats) >= 20 else None
            err_raw = await redis.get(f"source_health:{connector_name}:errors")
            rl_raw = await redis.get(f"source_health:{connector_name}:ratelimit_hits")
            return {
                "connector": connector_name,
                "avg_response_ms": avg_ms,
                "p95_response_ms": p95_ms,
                "samples": len(lats),
                "errors_1h": int(err_raw) if err_raw else 0,
                "ratelimit_hits_1h": int(rl_raw) if rl_raw else 0,
            }
        except Exception:
            return {"connector": connector_name, "error": "stats_unavailable"}

    def _prov(
        self, url: str = "", phash: str = "",
        confidence: float = 1.0, reasoning: str = "", ext_id: str = "",
    ) -> ProvenanceRecord:
        return ProvenanceRecord.from_connector(
            source=self.name, url=url, payload_hash=phash,
            confidence=confidence, reasoning=reasoning, external_id=ext_id,
        )

    # ── Abstract interface ────────────────────────────────
    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search and return dicts (legacy) or normalized entities."""
        ...

    def normalize(self, raw_data: Dict[str, Any]) -> Any:
        """Normalize raw API data into canonical EntityBase schemas. Override in subclasses."""
        return raw_data

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single entity by canonical ID."""
        return None

    async def count(self, query: str) -> Optional[int]:
        """Return total hit count for a query."""
        return None

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """Extract evidence records linked to an entity."""
        return []
