"""Unit tests for Rate Limiter module.

Tests token bucket rate limiting, retry-after handling, and connector limits.
"""

import pytest
import asyncio
import time
from core.rate_limiter import (
    TokenBucket,
    RateLimiterRegistry,
    RATE_LIMITS,
    DEFAULT_RATE_LIMIT
)


class TestTokenBucket:
    """Test token bucket rate limiter."""
    
    def test_initialization(self):
        """Test token bucket initialization."""
        bucket = TokenBucket("pubmed")
        assert bucket.connector_name == "pubmed"
        assert bucket.rate == RATE_LIMITS["pubmed"]["requests_per_second"]
        assert bucket.max_tokens == RATE_LIMITS["pubmed"]["burst"]
    
    def test_initialization_unknown_connector(self):
        """Test initialization with unknown connector uses defaults."""
        bucket = TokenBucket("unknown_connector")
        assert bucket.rate == DEFAULT_RATE_LIMIT["requests_per_second"]
        assert bucket.max_tokens == DEFAULT_RATE_LIMIT["burst"]
    
    @pytest.mark.asyncio
    async def test_acquire_success(self):
        """Test successful token acquisition."""
        bucket = TokenBucket("pubmed")
        result = await bucket.acquire()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_acquire_exhaustion(self):
        """Test token exhaustion."""
        bucket = TokenBucket("pubmed")
        
        # Exhaust all tokens
        for _ in range(bucket.max_tokens):
            await bucket.acquire()
        
        # Next acquisition should fail
        result = await bucket.acquire()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_token_refill(self):
        """Test tokens refill over time."""
        bucket = TokenBucket("pubmed")
        
        # Exhaust tokens
        for _ in range(bucket.max_tokens):
            await bucket.acquire()
        
        # Wait for refill
        await asyncio.sleep(1.0 / bucket.rate + 0.1)
        
        # Should be able to acquire again
        result = await bucket.acquire()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_wait_and_acquire(self):
        """Test waiting for token availability."""
        bucket = TokenBucket("pubmed")
        
        # Exhaust tokens
        for _ in range(bucket.max_tokens):
            await bucket.acquire()
        
        # Wait and acquire should succeed
        result = await bucket.wait_and_acquire(timeout=2.0)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_wait_and_acquire_timeout(self):
        """Test wait and acquire with timeout."""
        bucket = TokenBucket("pubmed")
        bucket.tokens = 0
        bucket.rate = 0.1  # Very slow refill
        
        # Should timeout
        result = await bucket.wait_and_acquire(timeout=0.1)
        assert result is False
    
    def test_set_retry_after(self):
        """Test setting retry-after cooldown."""
        bucket = TokenBucket("pubmed")
        bucket.set_retry_after(10.0)
        
        assert bucket.retry_after is not None
        assert bucket.retry_after > time.monotonic()
    
    @pytest.mark.asyncio
    async def test_retry_after_blocks_acquisition(self):
        """Test retry-after blocks token acquisition."""
        bucket = TokenBucket("pubmed")
        bucket.set_retry_after(1.0)
        
        # Should be blocked
        result = await bucket.acquire()
        assert result is False
        
        # Wait for cooldown
        await asyncio.sleep(1.1)
        
        # Should work now
        result = await bucket.acquire()
        assert result is True


class TestRateLimiterRegistry:
    """Test rate limiter registry."""
    
    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = RateLimiterRegistry()
        assert registry is not None
    
    def test_get_limiter(self):
        """Test getting limiter from registry."""
        registry = RateLimiterRegistry()
        limiter = registry.get("pubmed")
        
        assert limiter is not None
        assert limiter.connector_name == "pubmed"
    
    def test_get_same_limiter_twice(self):
        """Test getting same limiter returns same instance."""
        registry = RateLimiterRegistry()
        limiter1 = registry.get("pubmed")
        limiter2 = registry.get("pubmed")
        
        assert limiter1 is limiter2
    
    def test_get_status(self):
        """Test getting status for all limiters."""
        registry = RateLimiterRegistry()
        registry.get("pubmed")
        registry.get("chembl")
        
        status = registry.get_status()
        assert "pubmed" in status
        assert "chembl" in status
        assert "tokens" in status["pubmed"]
        assert "rate" in status["pubmed"]


class TestRateLimits:
    """Test rate limit configurations."""
    
    def test_pubmed_limits(self):
        """Test PubMed rate limits."""
        assert "pubmed" in RATE_LIMITS
        assert RATE_LIMITS["pubmed"]["requests_per_second"] == 3
        assert RATE_LIMITS["pubmed"]["burst"] == 10
    
    def test_chembl_limits(self):
        """Test ChEMBL rate limits."""
        assert "chembl" in RATE_LIMITS
        assert RATE_LIMITS["chembl"]["requests_per_second"] == 5
        assert RATE_LIMITS["chembl"]["burst"] == 15
    
    def test_all_connectors_have_limits(self):
        """Test all major connectors have defined limits."""
        expected_connectors = [
            "pubmed", "europe_pmc", "opentargets", "uniprot",
            "chembl", "kegg", "string", "rcsb_pdb"
        ]
        for connector in expected_connectors:
            assert connector in RATE_LIMITS


class TestPerformance:
    """Test performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_acquire_latency(self):
        """Test token acquisition is fast."""
        bucket = TokenBucket("pubmed")
        
        start = time.time()
        await bucket.acquire()
        latency = time.time() - start
        
        # Should be very fast (<1ms)
        assert latency < 0.001
    
    @pytest.mark.asyncio
    async def test_burst_handling(self):
        """Test burst requests are handled correctly."""
        bucket = TokenBucket("pubmed")
        burst_size = bucket.max_tokens
        
        # Should handle burst
        results = []
        for _ in range(burst_size):
            result = await bucket.acquire()
            results.append(result)
        
        # All burst requests should succeed
        assert all(results)
        
        # Next request should fail
        result = await bucket.acquire()
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
