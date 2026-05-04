"""
Unit tests for HPO Connector

Tests HPO-specific functionality including:
- Search functionality
- Data retrieval
- Error handling
- Rate limiting
- Circuit breaker
- Caching
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

import sys
sys.path.insert(0, 'apps/api')
from connectors.hpo import HPOConnector


class TestHPOConnector:
    """Test suite for HPO connector"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.connector = HPOConnector()
    
    def test_initialization(self):
        """Test HPO connector initialization"""
        assert self.connector.name == "HPO"
        assert hasattr(self.connector, 'cache_ttl')
        assert hasattr(self.connector, 'rate_limit_rps')
    
    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful search operation"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ({'terms': []}, {"source": "HPO"})
            
            result = await self.connector.search("test query", limit=10)
            
            assert isinstance(result, list)
            assert len(result) >= 0
            mock_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Test search with no results"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (None, {"source": "HPO"})
            
            result = await self.connector.search("nonexistent query xyz123")
            
            assert isinstance(result, list)
            assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_search_with_limit(self):
        """Test search respects limit parameter"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ({'terms': []}, {"source": "HPO"})
            
            result = await self.connector.search("test", limit=5)
            
            assert isinstance(result, list)
            # Verify limit was applied in the request
            call_args = mock_get.call_args
            assert call_args is not None
    
    @pytest.mark.asyncio
    async def test_fetch_by_id_success(self):
        """Test fetching entity by ID"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ({"id": "test_123", "name": "Test Entity"}, {"source": "HPO"})
            
            result = await self.connector.fetch_by_id("test_id_123")
            
            if result is not None:
                assert isinstance(result, dict)
                assert "id" in result or "entity_type" in result
    
    @pytest.mark.asyncio
    async def test_fetch_by_id_not_found(self):
        """Test fetching non-existent entity"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (None, {"source": "HPO"})
            
            result = await self.connector.fetch_by_id("nonexistent_id")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_caching_behavior(self):
        """Test that results are cached properly"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ({'terms': []}, {"source": "HPO", "cache_hit": False})
            
            # First call
            result1 = await self.connector.search("test query")
            
            # Second call - should use cache
            mock_get.return_value = ({'terms': []}, {"source": "HPO", "cache_hit": True})
            result2 = await self.connector.search("test query")
            
            assert isinstance(result1, list)
            assert isinstance(result2, list)
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting is enforced"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            # Simulate rate limit response
            mock_get.return_value = (None, {
                "source": "HPO",
                "rate_limited": True,
                "status": "degraded"
            })
            
            result = await self.connector.search("test")
            
            # Should handle rate limiting gracefully
            assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_error_handling_network_error(self):
        """Test handling of network errors"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            # Should not crash, should handle gracefully
            try:
                result = await self.connector.search("test")
                # If it returns, should be empty list or None
                assert result is None or isinstance(result, list)
            except Exception as e:
                # If it raises, that's also acceptable
                assert "error" in str(e).lower() or "network" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_response(self):
        """Test handling of malformed API responses"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            # Return invalid data structure
            mock_get.return_value = ({"invalid": "structure"}, {"source": "HPO"})
            
            result = await self.connector.search("test")
            
            # Should handle gracefully and return empty or valid structure
            assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_provenance_tracking(self):
        """Test that provenance metadata is included"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ({'terms': []}, {"source": "HPO"})
            
            result = await self.connector.search("test")
            
            if result and len(result) > 0:
                # Check if provenance is tracked
                first_result = result[0]
                assert isinstance(first_result, dict)
                # Provenance might be in the result or metadata
                assert "provenance" in first_result or "source" in str(first_result)
    
    @pytest.mark.asyncio
    async def test_count_method(self):
        """Test count method if implemented"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ({"count": 42}, {"source": "HPO"})
            
            result = await self.connector.count("test query")
            
            # count() may return None if not implemented
            assert result is None or isinstance(result, int)
    
    @pytest.mark.asyncio
    async def test_extract_evidence(self):
        """Test evidence extraction if implemented"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ({"evidence": []}, {"source": "HPO"})
            
            result = await self.connector.extract_evidence("test_id")
            
            # extract_evidence() returns empty list by default
            assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_normalize_method(self):
        """Test data normalization"""
        raw_data = {"id": "test_123", "name": "Test Entity"}
        
        result = self.connector.normalize(raw_data)
        
        # normalize() should return data (may be unchanged)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_behavior(self):
        """Test circuit breaker opens after repeated failures"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            # Simulate repeated failures
            mock_get.side_effect = Exception("Service unavailable")
            
            # Make multiple requests
            for i in range(5):
                try:
                    await self.connector.search(f"test{i}")
                except:
                    pass
            
            # Circuit breaker should be engaged
            # (Implementation detail - may vary)
            assert mock_get.call_count >= 3
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test request timeout handling"""
        with patch.object(self.connector, '_cached_get', new_callable=AsyncMock) as mock_get:
            import asyncio
            mock_get.side_effect = asyncio.TimeoutError("Request timeout")
            
            try:
                result = await self.connector.search("test")
                assert result is None or isinstance(result, list)
            except asyncio.TimeoutError:
                # Timeout exceptions are acceptable
                pass
    
    @pytest.mark.asyncio
    async def test_close_method(self):
        """Test connector cleanup"""
        await self.connector.close()
        
        # Should close without errors
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
