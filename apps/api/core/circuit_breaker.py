"""Circuit Breaker — Per-Connector Fault Isolation (Drug Designer §62.1).

Implements the exact pattern from the spec:
  CLOSED → OPEN → HALF_OPEN → CLOSED

When a connector fails N times within a window, the breaker trips open
and all subsequent calls return {status: degraded, reason: circuit_open}
until the recovery_timeout elapses. Then a single test request is allowed
(HALF_OPEN). If it succeeds, the breaker closes. If it fails, it opens again.
"""

import time
import asyncio
import structlog
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field

logger = structlog.get_logger()


@dataclass
class CircuitState:
    state: str = "closed"        # closed | open | half_open
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    total_requests: int = 0
    total_failures: int = 0


class ConnectorCircuitBreaker:
    """Per-connector circuit breaker with configurable thresholds.
    
    Args:
        connector_name: Name of the connector (for logging/metrics)
        failure_threshold: Number of consecutive failures to trip the breaker
        recovery_timeout: Seconds to wait before testing recovery (HALF_OPEN)
        success_threshold: Number of consecutive successes in HALF_OPEN to close
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        connector_name: str,
        failure_threshold: int = 3,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
    ):
        self.connector_name = connector_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self._state = CircuitState()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state.state

    @property
    def is_open(self) -> bool:
        return self._state.state == self.OPEN

    def get_health(self) -> Dict[str, Any]:
        """Return health diagnostics for the HealthStrip."""
        return {
            "connector": self.connector_name,
            "state": self._state.state,
            "failure_count": self._state.failure_count,
            "total_requests": self._state.total_requests,
            "total_failures": self._state.total_failures,
            "last_failure": self._state.last_failure_time,
            "last_success": self._state.last_success_time,
        }

    async def call(self, fn: Callable, *args, **kwargs) -> Any:
        """Execute a connector call through the circuit breaker.
        
        Returns the connector result on success, or a degraded dict on failure/open.
        """
        async with self._lock:
            self._state.total_requests += 1

            # ── Check if breaker is OPEN ──
            if self._state.state == self.OPEN:
                elapsed = time.time() - self._state.last_failure_time
                if elapsed > self.recovery_timeout:
                    # Move to HALF_OPEN — allow one test request
                    self._state.state = self.HALF_OPEN
                    self._state.success_count = 0
                    logger.info("circuit_breaker_half_open",
                                connector=self.connector_name,
                                elapsed_s=int(elapsed))
                else:
                    logger.debug("circuit_breaker_rejected",
                                 connector=self.connector_name,
                                 retry_in_s=int(self.recovery_timeout - elapsed))
                    return {
                        "status": "degraded",
                        "reason": "circuit_open",
                        "connector": self.connector_name,
                        "retry_in_seconds": int(self.recovery_timeout - elapsed),
                    }

        # ── Execute the actual call (outside the lock) ──
        try:
            if asyncio.iscoroutinefunction(fn):
                result = await fn(*args, **kwargs)
            else:
                result = fn(*args, **kwargs)

            # ── Success ──
            async with self._lock:
                self._state.last_success_time = time.time()
                self._state.failure_count = 0

                if self._state.state == self.HALF_OPEN:
                    self._state.success_count += 1
                    if self._state.success_count >= self.success_threshold:
                        self._state.state = self.CLOSED
                        logger.info("circuit_breaker_closed",
                                    connector=self.connector_name)
                elif self._state.state != self.CLOSED:
                    self._state.state = self.CLOSED

            return result

        except Exception as exc:
            # ── Failure ──
            async with self._lock:
                self._state.failure_count += 1
                self._state.total_failures += 1
                self._state.last_failure_time = time.time()

                if self._state.failure_count >= self.failure_threshold:
                    self._state.state = self.OPEN
                    logger.warning("circuit_breaker_tripped",
                                   connector=self.connector_name,
                                   failures=self._state.failure_count,
                                   threshold=self.failure_threshold)

            return {
                "status": "degraded",
                "reason": "connector_error",
                "connector": self.connector_name,
                "error": str(exc),
            }


class CircuitBreakerRegistry:
    """Global registry of per-connector circuit breakers.
    
    Usage:
        registry = CircuitBreakerRegistry()
        breaker = registry.get("pubmed")
        result = await breaker.call(pubmed_connector.search, query="BRCA1")
    """

    def __init__(self, default_failure_threshold: int = 3, default_recovery_timeout: int = 60):
        self._breakers: Dict[str, ConnectorCircuitBreaker] = {}
        self._default_failure_threshold = default_failure_threshold
        self._default_recovery_timeout = default_recovery_timeout

    def get(self, connector_name: str) -> ConnectorCircuitBreaker:
        if connector_name not in self._breakers:
            self._breakers[connector_name] = ConnectorCircuitBreaker(
                connector_name=connector_name,
                failure_threshold=self._default_failure_threshold,
                recovery_timeout=self._default_recovery_timeout,
            )
        return self._breakers[connector_name]

    def get_all_health(self) -> list:
        """Return health diagnostics for all registered breakers."""
        return [b.get_health() for b in self._breakers.values()]

    def get_summary(self) -> Dict[str, int]:
        """Return counts: how many closed, open, half_open."""
        summary = {"closed": 0, "open": 0, "half_open": 0}
        for b in self._breakers.values():
            summary[b.state] = summary.get(b.state, 0) + 1
        return summary


# Global singleton registry
_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get singleton circuit breaker registry."""
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry()
    return _registry

