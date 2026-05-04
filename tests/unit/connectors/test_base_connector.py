"""
Unit tests for BaseConnector

Tests the base connector functionality including:
- Caching mechanisms
- Rate limiting
- Circuit breaker
- Error handling
- Retry logic
- Provenance tracking
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Import the base connector (adjust path as needed)
import sys
sys.path.insert(0, 'apps/api')
from connectors.base import BaseConnector


class TestConnector(BaseConnector):
    """Test implementation of BaseConnector"""
    
    def __init__(self):
        super().__init__(
            name="test_connector",
            base_url="https://api.test.com",
            rate_limit=10,
            cache_ttl=300
        )
    
    def search(self, query: str, **kwargs):
        """Test search implementation"""
        return self._make_request("GET", f"/search?q={query}")


class TestBaseConnector:
    """Test suite for BaseConnector"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.connector = TestConnector()
    
    def test_initialization(self):
        """Test connector initialization"""
        assert self.connector.name == "test_connector"
        assert self.connector.base_url == "https://api.test.com"
        assert self.connector.rate_limit == 10
        assert self.connector.cache_ttl == 300
    
    @patch('requests.get')
    def test_make_request_success(self, mock_get):
        """Test successful API request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_get.return_value = mock_response
        
        result = self.connector._make_request("GET", "/test")
        
        assert result == {"data": "test"}
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_make_request_with_cache(self, mock_get):
        """Test request caching"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_get.return_value = mock_response
        
        # First request - should hit API
        result1 = self.connector._make_request("GET", "/test")
        assert result1 == {"data": "test"}
        assert mock_get.call_count == 1
        
        # Second request - should use cache
        result2 = self.connector._make_request("GET", "/test")
        assert result2 == {"data": "test"}
        assert mock_get.call_count == 1  # Still 1, not 2
    
    @patch('requests.get')
    def test_rate_limiting(self, mock_get):
        """Test rate limiting functionality"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_get.return_value = mock_response
        
        # Make requests up to rate limit
        start_time = time.time()
        for i in range(self.connector.rate_limit + 5):
            self.connector._make_request("GET", f"/test{i}")
        end_time = time.time()
        
        # Should take at least 1 second due to rate limiting
        assert end_time - start_time >= 0.5
    
    @patch('requests.get')
    def test_circuit_breaker_opens(self, mock_get):
        """Test circuit breaker opens after failures"""
        mock_get.side_effect = Exception("API Error")
        
        # Make requests until circuit breaker opens
        for i in range(6):  # Threshold is typically 5
            try:
                self.connector._make_request("GET", "/test")
            except:
                pass
        
        # Circuit should be open now
        assert self.connector._circuit_breaker_open == True
    
    @patch('requests.get')
    def test_circuit_breaker_half_open(self, mock_get):
        """Test circuit breaker half-open state"""
        # Open the circuit
        mock_get.side_effect = Exception("API Error")
        for i in range(6):
            try:
                self.connector._make_request("GET", "/test")
            except:
                pass
        
        # Wait for timeout
        time.sleep(self.connector._circuit_breaker_timeout + 0.1)
        
        # Next request should be in half-open state
        mock_get.side_effect = None
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_get.return_value = mock_response
        
        result = self.connector._make_request("GET", "/test")
        assert result == {"data": "test"}
        assert self.connector._circuit_breaker_open == False
    
    @patch('requests.get')
    def test_retry_logic(self, mock_get):
        """Test retry logic on transient failures"""
        # First two calls fail, third succeeds
        mock_get.side_effect = [
            Exception("Timeout"),
            Exception("Timeout"),
            Mock(status_code=200, json=lambda: {"data": "test"})
        ]
        
        result = self.connector._make_request("GET", "/test")
        assert result == {"data": "test"}
        assert mock_get.call_count == 3
    
    @patch('requests.get')
    def test_error_handling_404(self, mock_get):
        """Test handling of 404 errors"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception) as exc_info:
            self.connector._make_request("GET", "/test")
        
        assert "404" in str(exc_info.value)
    
    @patch('requests.get')
    def test_error_handling_500(self, mock_get):
        """Test handling of 500 errors"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception) as exc_info:
            self.connector._make_request("GET", "/test")
        
        assert "500" in str(exc_info.value)
    
    @patch('requests.get')
    def test_provenance_tracking(self, mock_get):
        """Test provenance metadata tracking"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_get.return_value = mock_response
        
        result = self.connector._make_request("GET", "/test")
        
        # Check provenance metadata
        assert hasattr(self.connector, '_last_request_time')
        assert hasattr(self.connector, '_request_count')
    
    def test_cache_expiration(self):
        """Test cache expiration after TTL"""
        # Set a short TTL
        self.connector.cache_ttl = 1
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_get.return_value = mock_response
            
            # First request
            result1 = self.connector._make_request("GET", "/test")
            assert mock_get.call_count == 1
            
            # Wait for cache to expire
            time.sleep(1.1)
            
            # Second request - should hit API again
            result2 = self.connector._make_request("GET", "/test")
            assert mock_get.call_count == 2
    
    def test_search_method(self):
        """Test search method implementation"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": ["item1", "item2"]}
            mock_get.return_value = mock_response
            
            result = self.connector.search("test query")
            assert result == {"results": ["item1", "item2"]}
    
    @patch('requests.get')
    def test_timeout_handling(self, mock_get):
        """Test request timeout handling"""
        mock_get.side_effect = TimeoutError("Request timeout")
        
        with pytest.raises(Exception) as exc_info:
            self.connector._make_request("GET", "/test")
        
        assert "timeout" in str(exc_info.value).lower()
    
    @patch('requests.get')
    def test_connection_error_handling(self, mock_get):
        """Test connection error handling"""
        mock_get.side_effect = ConnectionError("Connection failed")
        
        with pytest.raises(Exception) as exc_info:
            self.connector._make_request("GET", "/test")
        
        assert "connection" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
