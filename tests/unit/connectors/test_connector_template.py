"""
Template for connector unit tests
This template can be used to quickly create tests for new connectors
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock


# TEMPLATE: Replace ConnectorName with actual connector class name
# from apps.api.connectors.connector_name import ConnectorNameConnector


def create_connector_test_suite(connector_class, connector_name, sample_data):
    """
    Factory function to create a complete test suite for a connector
    
    Args:
        connector_class: The connector class to test
        connector_name: Name of the connector (e.g., "pubmed")
        sample_data: Dictionary with sample response data
    
    Returns:
        Dictionary of test functions
    """
    
    @pytest.fixture
    def connector():
        """Fixture for connector instance"""
        return connector_class()
    
    def test_initialization(connector):
        """Test connector initialization"""
        assert connector.name == connector_name
        assert connector.base_url is not None
        assert hasattr(connector, 'rate_limiter')
        assert hasattr(connector, 'cache')
    
    @pytest.mark.asyncio
    async def test_search_success(connector):
        """Test successful search"""
        with patch.object(connector, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_data['search_response']
            
            results = await connector.search("test query", limit=10)
            
            assert len(results) > 0
            assert all('id' in r for r in results)
            assert all('provenance' in r for r in results)
            assert all(r['provenance']['source'] == connector_name for r in results)
    
    @pytest.mark.asyncio
    async def test_search_empty_results(connector):
        """Test search with no results"""
        with patch.object(connector, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_data['empty_response']
            
            results = await connector.search("nonexistent query", limit=10)
            
            assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_get_by_id(connector):
        """Test fetching by ID"""
        with patch.object(connector, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_data['get_by_id_response']
            
            result = await connector.get_by_id("test_id_001")
            
            assert result['id'] == "test_id_001"
            assert 'provenance' in result
    
    @pytest.mark.asyncio
    async def test_rate_limiting(connector):
        """Test rate limiting behavior"""
        with patch.object(connector, '_check_rate_limit') as mock_rate_limit:
            mock_rate_limit.return_value = False  # Rate limit exceeded
            
            with pytest.raises(Exception, match="Rate limit exceeded"):
                await connector.search("test query")
    
    @pytest.mark.asyncio
    async def test_error_handling(connector):
        """Test error handling for failed requests"""
        with patch.object(connector, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("API error")
            
            with pytest.raises(Exception, match="API error"):
                await connector.search("test query")
    
    @pytest.mark.asyncio
    async def test_caching(connector):
        """Test caching mechanism"""
        with patch.object(connector, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_data['search_response']
            
            # First call - should hit API
            results1 = await connector.search("test query", limit=10)
            
            # Second call with same query - should use cache
            results2 = await connector.search("test query", limit=10)
            
            # API should only be called once due to caching
            assert mock_request.call_count == 1
            assert results1 == results2
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(connector):
        """Test circuit breaker functionality"""
        with patch.object(connector, '_make_request', new_callable=AsyncMock) as mock_request:
            # Simulate multiple failures
            mock_request.side_effect = Exception("Service unavailable")
            
            # After multiple failures, circuit breaker should open
            for _ in range(5):
                try:
                    await connector.search("test query")
                except Exception:
                    pass
            
            # Circuit should be open
            assert connector.circuit_breaker.is_open()
    
    @pytest.mark.asyncio
    async def test_retry_logic(connector):
        """Test retry logic for transient failures"""
        with patch.object(connector, '_make_request', new_callable=AsyncMock) as mock_request:
            # First call fails, second succeeds
            mock_request.side_effect = [
                Exception("Temporary error"),
                sample_data['search_response']
            ]
            
            results = await connector.search("test query", limit=10)
            
            # Should have retried and succeeded
            assert len(results) > 0
            assert mock_request.call_count == 2
    
    @pytest.mark.asyncio
    async def test_provenance_tracking(connector):
        """Test provenance tracking"""
        with patch.object(connector, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_data['search_response']
            
            results = await connector.search("test query", limit=10)
            
            for result in results:
                assert 'provenance' in result
                assert result['provenance']['source'] == connector_name
                assert 'timestamp' in result['provenance']
                assert 'retrieval_method' in result['provenance']
    
    return {
        'test_initialization': test_initialization,
        'test_search_success': test_search_success,
        'test_search_empty_results': test_search_empty_results,
        'test_get_by_id': test_get_by_id,
        'test_rate_limiting': test_rate_limiting,
        'test_error_handling': test_error_handling,
        'test_caching': test_caching,
        'test_circuit_breaker': test_circuit_breaker,
        'test_retry_logic': test_retry_logic,
        'test_provenance_tracking': test_provenance_tracking
    }


# Example usage:
# from apps.api.connectors.example import ExampleConnector
# 
# sample_data = {
#     'search_response': {'results': [{'id': '1', 'title': 'Test'}]},
#     'empty_response': {'results': []},
#     'get_by_id_response': {'id': 'test_id_001', 'title': 'Test Item'}
# }
# 
# test_suite = create_connector_test_suite(ExampleConnector, "example", sample_data)
# 
# # Then use the test functions:
# test_initialization = test_suite['test_initialization']
# test_search_success = test_suite['test_search_success']
# etc.
