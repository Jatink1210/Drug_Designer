"""Enhanced async HTTP client with retries, backoff, circuit breaker, and rate limiting."""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any, Dict, Optional, Tuple, List
from collections import defaultdict

import httpx
import structlog

log = structlog.get_logger()

DEFAULT_TIMEOUT = 15.0
MAX_RETRIES = 3
BACKOFF_BASE = 1.0
BACKOFF_MAX = 10.0

# Connection pooling configuration
MAX_CONNECTIONS = 100
MAX_KEEPALIVE_CONNECTIONS = 20
KEEPALIVE_EXPIRY = 30.0  # seconds

# §64 Per-operation tiered timeouts (seconds)
TIERED_TIMEOUTS = {
    "health": 2.0,
    "graph": 5.0,
    "evidence": 10.0,
    "search": 10.0,
    "targets": 15.0,
    "structure": 30.0,
    "design": 60.0,
    "disease": 120.0,
    "dossier": 300.0,
    "retrosynthesis": 120.0,
    "default": 15.0,
}


def get_tiered_timeout(operation: str = "default") -> float:
    """Return the spec-mandated timeout for an operation category (§64)."""
    return TIERED_TIMEOUTS.get(operation, TIERED_TIMEOUTS["default"])


class CircuitBreaker:
    """Per-host circuit breaker: open after N consecutive failures, half-open after cooldown."""

    def __init__(self, failure_threshold: int = 5, cooldown_sec: float = 60.0):
        self._threshold = failure_threshold
        self._cooldown = cooldown_sec
        self._failures: Dict[str, int] = {}
        self._opened_at: Dict[str, float] = {}

    def is_open(self, host: str) -> bool:
        if host not in self._opened_at:
            return False
        if time.monotonic() - self._opened_at[host] > self._cooldown:
            del self._opened_at[host]
            self._failures[host] = 0
            return False
        return True

    def record_failure(self, host: str) -> None:
        self._failures[host] = self._failures.get(host, 0) + 1
        if self._failures[host] >= self._threshold:
            self._opened_at[host] = time.monotonic()
            log.warning("circuit_opened", host=host, failures=self._failures[host])

    def record_success(self, host: str) -> None:
        self._failures[host] = 0
        self._opened_at.pop(host, None)


class RateLimiter:
    """Per-host token-bucket rate limiter."""

    def __init__(self, default_rps: float = 5.0):
        self._default_rps = default_rps
        self._limits: Dict[str, float] = {}
        self._tokens: Dict[str, float] = {}
        self._last_refill: Dict[str, float] = {}

    def set_limit(self, host: str, rps: float) -> None:
        self._limits[host] = rps

    async def acquire(self, host: str) -> None:
        rps = self._limits.get(host, self._default_rps)
        now = time.monotonic()
        if host not in self._tokens:
            self._tokens[host] = rps
            self._last_refill[host] = now

        elapsed = now - self._last_refill[host]
        self._tokens[host] = min(rps, self._tokens[host] + elapsed * rps)
        self._last_refill[host] = now

        if self._tokens[host] < 1.0:
            wait = (1.0 - self._tokens[host]) / rps
            await asyncio.sleep(wait)
            self._tokens[host] = 0.0
        else:
            self._tokens[host] -= 1.0


# Global singletons
_circuit_breaker = CircuitBreaker()
_rate_limiter = RateLimiter()

# Performance metrics tracking
_performance_metrics: Dict[str, List[float]] = defaultdict(list)
_request_counts: Dict[str, int] = defaultdict(int)
_error_counts: Dict[str, int] = defaultdict(int)


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter


def get_performance_metrics() -> Dict[str, Any]:
    """Get performance metrics for all hosts."""
    metrics = {}
    
    for host, latencies in _performance_metrics.items():
        if not latencies:
            continue
        
        metrics[host] = {
            "total_requests": _request_counts[host],
            "total_errors": _error_counts[host],
            "error_rate": round(_error_counts[host] / max(_request_counts[host], 1) * 100, 2),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            "p50_latency_ms": round(sorted(latencies)[len(latencies) // 2], 2),
            "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 2),
            "p99_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.99)], 2),
        }
    
    return metrics


def reset_performance_metrics():
    """Reset performance metrics."""
    _performance_metrics.clear()
    _request_counts.clear()
    _error_counts.clear()
    log.info("performance_metrics_reset")


class ResilientClient:
    """Async HTTP client with retries, exponential backoff, circuit breaker, and rate limiting."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, max_retries: int = MAX_RETRIES):
        # Connection pooling configuration
        limits = httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
            keepalive_expiry=KEEPALIVE_EXPIRY,
        )
        
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            limits=limits,
        )
        self._max_retries = max_retries
        
        log.info("resilient_client_initialized",
                max_connections=MAX_CONNECTIONS,
                max_keepalive=MAX_KEEPALIVE_CONNECTIONS)

    async def close(self) -> None:
        await self._client.aclose()

    def _host(self, url: str) -> str:
        return httpx.URL(url).host or "unknown"

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        """GET with retries. Returns (json_body, metadata)."""
        return await self._request("GET", url, params=params, headers=headers)

    async def post(
        self,
        url: str,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        """POST with retries. Returns (json_body, metadata)."""
        return await self._request("POST", url, json_body=json_body, headers=headers)

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        host = self._host(url)
        meta: Dict[str, Any] = {
            "url": url,
            "method": method,
            "attempts": 0,
            "status": None,
            "elapsed_ms": 0,
            "etag": None,
            "cache_hit": False,
            "provenance": {
                "source": host,
                "timestamp": time.time(),
                "payload_hash": payload_hash(json_body) if json_body else None,
                "request_id": payload_hash({"url": url, "time": time.time()})
            }
        }

        if _circuit_breaker.is_open(host):
            log.warning("circuit_open_skip", host=host, url=url)
            meta["error"] = "circuit_open"
            return None, meta

        last_error = None
        for attempt in range(self._max_retries):
            meta["attempts"] = attempt + 1
            await _rate_limiter.acquire(host)

            try:
                t0 = time.monotonic()
                if method == "GET":
                    resp = await self._client.get(url, params=params, headers=headers)
                else:
                    resp = await self._client.post(url, json=json_body, headers=headers)

                meta["elapsed_ms"] = round((time.monotonic() - t0) * 1000)
                meta["status"] = resp.status_code
                meta["etag"] = resp.headers.get("etag")

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("retry-after", BACKOFF_BASE * (2 ** attempt)))
                    log.info("rate_limited", host=host, retry_after=retry_after)
                    await asyncio.sleep(min(retry_after, BACKOFF_MAX))
                    continue

                if resp.status_code >= 500:
                    _circuit_breaker.record_failure(host)
                    await asyncio.sleep(min(BACKOFF_BASE * (2 ** attempt), BACKOFF_MAX))
                    continue

                resp.raise_for_status()
                _circuit_breaker.record_success(host)
                
                # Track performance metrics
                _request_counts[host] += 1
                _performance_metrics[host].append(meta["elapsed_ms"])
                
                # Keep only last 1000 measurements per host
                if len(_performance_metrics[host]) > 1000:
                    _performance_metrics[host] = _performance_metrics[host][-1000:]

                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                return body, meta

            except httpx.TimeoutException:
                last_error = "timeout"
                _circuit_breaker.record_failure(host)
                _error_counts[host] += 1
                await asyncio.sleep(min(BACKOFF_BASE * (2 ** attempt), BACKOFF_MAX))
            except Exception as exc:
                last_error = str(exc)
                _error_counts[host] += 1
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(min(BACKOFF_BASE * (2 ** attempt), BACKOFF_MAX))
                else:
                    _circuit_breaker.record_failure(host)

        meta["error"] = last_error
        log.warning("request_exhausted", url=url, attempts=self._max_retries, error=last_error)
        return None, meta


def payload_hash(data: Any) -> str:
    """SHA-256 hash of JSON-serialized payload for provenance tracking."""
    import json
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
