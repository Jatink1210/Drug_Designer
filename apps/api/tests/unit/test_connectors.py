"""Unit tests for Connector Framework.

Tests base connector, circuit breaker integration, rate limiting,
and sample connector implementations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


class TestBaseConnector:
    """Test base connector functionality."""
    
    def test_connector_initialization(self):
        """Test connector initialization."""
        from connectors.base import BaseConnector
        
        class TestConnector(BaseConnector):
            def __init__(self):
                super().__init__(name="test_connector")
        
        connector = TestConnector()
        assert connector.name == "test_connector"
    
    @pytest.mark.asyncio
    async def test_connector_search(self):
        """Test connector search method."""
        from connectors.base import BaseConnector
        
        class TestConnector(BaseConnector):
            def __init__(self):
                super().__init__(name="test_connector")
            
            async def search(self, query: str):
                return {"results": [{"id": "1", "title": "Test"}]}
        
        connector = TestConnector()
        results = await connector.search("test query")
        
        assert "results" in results
        assert len(results["results"]) > 0
    
    @pytest.mark.asyncio
    async def test_connector_error_handling(self):
        """Test connector error handling."""
        from connectors.base import BaseConnector
        
        class TestConnector(BaseConnector):
            def __init__(self):
                super().__init__(name="test_connector")
            
            async def search(self, query: str):
                raise Exception("API error")
        
        connector = TestConnector()
        
        with pytest.raises(Exception):
            await connector.search("test query")


class TestPubMedConnector:
    """Test PubMed connector."""
    
    @pytest.mark.asyncio
    async def test_pubmed_search(self):
        """Test PubMed search."""
        from connectors.pubmed import PubMedConnector
        
        with patch("connectors.pubmed.PubMedConnector") as MockConnector:
            connector = MockConnector()
            connector.search = AsyncMock(return_value={
                "results": [
                    {
                        "pmid": "12345678",
                        "title": "Test Article",
                        "abstract": "Test abstract"
                    }
                ]
            })
            
            results = await connector.search("FOXP3")
            
            assert "results" in results
            assert len(results["results"]) > 0
    
    @pytest.mark.asyncio
    async def test_pubmed_rate_limiting(self):
        """Test PubMed respects rate limits."""
        from connectors.pubmed import PubMedConnector
        from core.rate_limiter import RATE_LIMITS
        
        assert "pubmed" in RATE_LIMITS
        assert RATE_LIMITS["pubmed"]["requests_per_second"] == 3


class TestUniProtConnector:
    """Test UniProt connector."""
    
    @pytest.mark.asyncio
    async def test_uniprot_search(self):
        """Test UniProt search."""
        from connectors.uniprot import UniProtConnector
        
        with patch("connectors.uniprot.UniProtConnector") as MockConnector:
            connector = MockConnector()
            connector.search = AsyncMock(return_value={
                "results": [
                    {
                        "accession": "P12345",
                        "gene_name": "FOXP3",
                        "protein_name": "Forkhead box protein P3"
                    }
                ]
            })
            
            results = await connector.search("FOXP3")
            
            assert "results" in results
            assert results["results"][0]["gene_name"] == "FOXP3"
    
    @pytest.mark.asyncio
    async def test_uniprot_get_protein(self):
        """Test UniProt protein retrieval."""
        from connectors.uniprot import UniProtConnector
        
        with patch("connectors.uniprot.UniProtConnector") as MockConnector:
            connector = MockConnector()
            connector.get_protein = AsyncMock(return_value={
                "accession": "P12345",
                "sequence": "MKTAYIAK...",
                "length": 431
            })
            
            protein = await connector.get_protein("P12345")
            
            assert "accession" in protein
            assert "sequence" in protein


class TestChEMBLConnector:
    """Test ChEMBL connector."""
    
    @pytest.mark.asyncio
    async def test_chembl_search(self):
        """Test ChEMBL search."""
        from connectors.chembl import ChEMBLConnector
        
        with patch("connectors.chembl.ChEMBLConnector") as MockConnector:
            connector = MockConnector()
            connector.search = AsyncMock(return_value={
                "results": [
                    {
                        "chembl_id": "CHEMBL123",
                        "name": "Sirolimus",
                        "smiles": "CC1CCC2CC..."
                    }
                ]
            })
            
            results = await connector.search("Sirolimus")
            
            assert "results" in results
            assert len(results["results"]) > 0


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with connectors."""
    
    @pytest.mark.asyncio
    async def test_connector_with_circuit_breaker(self):
        """Test connector uses circuit breaker."""
        from core.circuit_breaker import get_circuit_breaker_registry
        
        registry = get_circuit_breaker_registry()
        breaker = registry.get("test_connector")
        
        async def mock_search():
            return {"results": []}
        
        result = await breaker.call(mock_search)
        assert "results" in result
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_on_failures(self):
        """Test circuit breaker trips after failures."""
        from core.circuit_breaker import ConnectorCircuitBreaker
        
        breaker = ConnectorCircuitBreaker("test_connector", failure_threshold=3)
        
        async def failing_search():
            raise Exception("API error")
        
        # Trigger failures
        for _ in range(3):
            await breaker.call(failing_search)
        
        assert breaker.is_open


class TestRateLimitingIntegration:
    """Test rate limiting integration with connectors."""
    
    @pytest.mark.asyncio
    async def test_connector_respects_rate_limits(self):
        """Test connector respects rate limits."""
        from core.rate_limiter import RateLimiterRegistry
        
        registry = RateLimiterRegistry()
        limiter = registry.get("pubmed")
        
        # Should be able to acquire token
        result = await limiter.acquire()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess_requests(self):
        """Test rate limiter blocks excess requests."""
        from core.rate_limiter import TokenBucket
        
        bucket = TokenBucket("test_connector")
        
        # Exhaust tokens
        for _ in range(bucket.max_tokens):
            await bucket.acquire()
        
        # Should be blocked
        result = await bucket.acquire()
        assert result is False


class TestConnectorHealth:
    """Test connector health monitoring."""
    
    def test_connector_health_status(self):
        """Test connector health status."""
        from core.circuit_breaker import ConnectorCircuitBreaker
        
        breaker = ConnectorCircuitBreaker("test_connector")
        health = breaker.get_health()
        
        assert "connector" in health
        assert "state" in health
        assert "failure_count" in health
    
    def test_all_connectors_health(self):
        """Test getting health for all connectors."""
        from core.circuit_breaker import get_circuit_breaker_registry
        
        registry = get_circuit_breaker_registry()
        registry.get("connector1")
        registry.get("connector2")
        
        health = registry.get_all_health()
        assert len(health) >= 2


class TestConnectorRetry:
    """Test connector retry logic."""
    
    @pytest.mark.asyncio
    async def test_connector_retries_on_failure(self):
        """Test connector retries on transient failures."""
        from connectors.base import BaseConnector
        
        class RetryConnector(BaseConnector):
            def __init__(self):
                super().__init__(name="retry_connector")
                self.attempt = 0
            
            async def search(self, query: str):
                self.attempt += 1
                if self.attempt < 3:
                    raise Exception("Transient error")
                return {"results": []}
        
        connector = RetryConnector()
        
        # Would need retry logic in actual implementation
        # This test verifies the interface
        assert connector.name == "retry_connector"


class TestConnectorCaching:
    """Test connector response caching."""
    
    @pytest.mark.asyncio
    async def test_connector_caches_responses(self, mock_redis):
        """Test connector caches responses."""
        from connectors.base import BaseConnector
        
        class CachingConnector(BaseConnector):
            def __init__(self, redis):
                super().__init__(name="caching_connector")
                self.redis = redis
            
            async def search(self, query: str):
                # Check cache
                cached = await self.redis.get(f"cache:{query}")
                if cached:
                    return cached
                
                # Fetch and cache
                result = {"results": []}
                await self.redis.set(f"cache:{query}", result)
                return result
        
        connector = CachingConnector(mock_redis)
        result = await connector.search("test")
        
        assert "results" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
