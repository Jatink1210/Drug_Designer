"""Unit tests for Circuit Breaker module.

Tests circuit breaker state transitions, failure detection, and recovery.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from core.circuit_breaker import (
    ConnectorCircuitBreaker,
    CircuitBreakerRegistry,
    get_circuit_breaker_registry
)


class TestConnectorCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_initialization(self):
        """Test circuit breaker initialization."""
        breaker = ConnectorCircuitBreaker(
            connector_name="test_connector",
            failure_threshold=5,
            recovery_timeout=300
        )
        assert breaker.connector_name == "test_connector"
        assert breaker.state == "closed"
        assert breaker.is_open is False
    
    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Test successful call through circuit breaker."""
        breaker = ConnectorCircuitBreaker("test_connector")
        
        async def success_fn():
            return {"status": "success", "data": "test"}
        
        result = await breaker.call(success_fn)
        assert result["status"] == "success"
        assert breaker.state == "closed"
    
    @pytest.mark.asyncio
    async def test_failed_call(self):
        """Test failed call through circuit breaker."""
        breaker = ConnectorCircuitBreaker("test_connector", failure_threshold=3)
        
        async def fail_fn():
            raise Exception("Test error")
        
        result = await breaker.call(fail_fn)
        assert result["status"] == "degraded"
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        breaker = ConnectorCircuitBreaker("test_connector", failure_threshold=3)
        
        async def fail_fn():
            raise Exception("Test error")
        
        # Trigger failures
        for _ in range(3):
            await breaker.call(fail_fn)
        
        assert breaker.state == "open"
        assert breaker.is_open is True
    
    @pytest.mark.asyncio
    async def test_circuit_rejects_when_open(self):
        """Test circuit rejects calls when open."""
        breaker = ConnectorCircuitBreaker("test_connector", failure_threshold=2)
        
        async def fail_fn():
            raise Exception("Test error")
        
        # Trip the breaker
        await breaker.call(fail_fn)
        await breaker.call(fail_fn)
        
        assert breaker.state == "open"
        
        # Next call should be rejected
        result = await breaker.call(fail_fn)
        assert result["status"] == "degraded"
        assert result["reason"] == "circuit_open"
    
    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        """Test circuit moves to half-open after recovery timeout."""
        breaker = ConnectorCircuitBreaker(
            "test_connector",
            failure_threshold=2,
            recovery_timeout=1  # 1 second for testing
        )
        
        async def fail_fn():
            raise Exception("Test error")
        
        # Trip the breaker
        await breaker.call(fail_fn)
        await breaker.call(fail_fn)
        assert breaker.state == "open"
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        
        # Next call should move to half-open
        async def success_fn():
            return {"status": "success"}
        
        result = await breaker.call(success_fn)
        assert breaker.state == "half_open" or breaker.state == "closed"
    
    @pytest.mark.asyncio
    async def test_circuit_closes_after_success_in_half_open(self):
        """Test circuit closes after successful calls in half-open state."""
        breaker = ConnectorCircuitBreaker(
            "test_connector",
            failure_threshold=2,
            recovery_timeout=1,
            success_threshold=2
        )
        
        async def fail_fn():
            raise Exception("Test error")
        
        async def success_fn():
            return {"status": "success"}
        
        # Trip the breaker
        await breaker.call(fail_fn)
        await breaker.call(fail_fn)
        
        # Wait for recovery
        await asyncio.sleep(1.1)
        
        # Successful calls should close the circuit
        await breaker.call(success_fn)
        await breaker.call(success_fn)
        
        assert breaker.state == "closed"
    
    @pytest.mark.asyncio
    async def test_sync_function_call(self):
        """Test circuit breaker with synchronous function."""
        breaker = ConnectorCircuitBreaker("test_connector")
        
        def sync_fn():
            return {"status": "success"}
        
        result = await breaker.call(sync_fn)
        assert result["status"] == "success"
    
    def test_get_health(self):
        """Test health diagnostics."""
        breaker = ConnectorCircuitBreaker("test_connector")
        health = breaker.get_health()
        
        assert "connector" in health
        assert "state" in health
        assert "failure_count" in health
        assert "total_requests" in health
        assert health["connector"] == "test_connector"


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""
    
    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = CircuitBreakerRegistry()
        assert registry is not None
    
    def test_get_breaker(self):
        """Test getting breaker from registry."""
        registry = CircuitBreakerRegistry()
        breaker = registry.get("test_connector")
        
        assert breaker is not None
        assert breaker.connector_name == "test_connector"
    
    def test_get_same_breaker_twice(self):
        """Test getting same breaker returns same instance."""
        registry = CircuitBreakerRegistry()
        breaker1 = registry.get("test_connector")
        breaker2 = registry.get("test_connector")
        
        assert breaker1 is breaker2
    
    def test_get_all_health(self):
        """Test getting health for all breakers."""
        registry = CircuitBreakerRegistry()
        registry.get("connector1")
        registry.get("connector2")
        
        health = registry.get_all_health()
        assert len(health) == 2
    
    def test_get_summary(self):
        """Test getting summary of breaker states."""
        registry = CircuitBreakerRegistry()
        registry.get("connector1")
        registry.get("connector2")
        
        summary = registry.get_summary()
        assert "closed" in summary
        assert "open" in summary
        assert "half_open" in summary
        assert summary["closed"] == 2


class TestGlobalRegistry:
    """Test global registry singleton."""
    
    def test_get_global_registry(self):
        """Test getting global registry."""
        registry = get_circuit_breaker_registry()
        assert registry is not None
    
    def test_global_registry_singleton(self):
        """Test global registry is singleton."""
        registry1 = get_circuit_breaker_registry()
        registry2 = get_circuit_breaker_registry()
        assert registry1 is registry2


class TestPerformance:
    """Test performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_call_latency(self):
        """Test circuit breaker adds minimal latency."""
        breaker = ConnectorCircuitBreaker("test_connector")
        
        async def fast_fn():
            return {"status": "success"}
        
        start = time.time()
        await breaker.call(fast_fn)
        latency = time.time() - start
        
        # Should be very fast (<10ms)
        assert latency < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
