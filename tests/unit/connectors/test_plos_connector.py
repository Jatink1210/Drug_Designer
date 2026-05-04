"""
Unit tests for PLoS (Public Library of Science) connector
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from apps.api.connectors.plos import PLoSConnector


@pytest.fixture
def plos_connector():
    """Fixture for PLoS connector instance"""
    return PLoSConnector()


@pytest.mark.asyncio
async def test_search_success(plos_connector):
    """Test successful article search"""
    mock_response = {
        "response": {
            "numFound": 2,
            "docs": [
                {
                    "id": "10.1371/journal.pone.0123456",
                    "title_display": "Test Article 1",
                    "author_display": ["Author A", "Author B"],
                    "abstract": ["Test abstract 1"],
                    "publication_date": "2024-01-15T00:00:00Z"
                },
                {
                    "id": "10.1371/journal.pbio.0234567",
                    "title_display": "Test Article 2",
                    "author_display": ["Author C"],
                    "abstract": ["Test abstract 2"],
                    "publication_date": "2024-02-20T00:00:00Z"
                }
            ]
        }
    }
    
    with patch.object(plos_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        results = await plos_connector.search("FOXP3 mutations", limit=10)
        
        assert len(results) == 2
        assert results[0]["id"] == "10.1371/journal.pone.0123456"
        assert results[0]["title"] == "Test Article 1"
        assert "Author A" in results[0]["authors"]
        assert results[0]["abstract"] == "Test abstract 1"
        
        # Verify provenance tracking
        assert results[0]["provenance"]["source"] == "plos"
        assert "timestamp" in results[0]["provenance"]


@pytest.mark.asyncio
async def test_search_empty_results(plos_connector):
    """Test search with no results"""
    mock_response = {
        "response": {
            "numFound": 0,
            "docs": []
        }
    }
    
    with patch.object(plos_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        results = await plos_connector.search("nonexistent query", limit=10)
        
        assert len(results) == 0


@pytest.mark.asyncio
async def test_search_rate_limiting(plos_connector):
    """Test rate limiting behavior"""
    with patch.object(plos_connector, '_check_rate_limit') as mock_rate_limit:
        mock_rate_limit.return_value = False  # Rate limit exceeded
        
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await plos_connector.search("test query")


@pytest.mark.asyncio
async def test_search_error_handling(plos_connector):
    """Test error handling for failed requests"""
    with patch.object(plos_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = Exception("API error")
        
        with pytest.raises(Exception, match="API error"):
            await plos_connector.search("test query")


@pytest.mark.asyncio
async def test_get_article_by_doi(plos_connector):
    """Test fetching article by DOI"""
    mock_response = {
        "response": {
            "numFound": 1,
            "docs": [{
                "id": "10.1371/journal.pone.0123456",
                "title_display": "Specific Article",
                "author_display": ["Author A"],
                "abstract": ["Specific abstract"],
                "publication_date": "2024-01-15T00:00:00Z"
            }]
        }
    }
    
    with patch.object(plos_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        article = await plos_connector.get_by_id("10.1371/journal.pone.0123456")
        
        assert article["id"] == "10.1371/journal.pone.0123456"
        assert article["title"] == "Specific Article"


@pytest.mark.asyncio
async def test_caching(plos_connector):
    """Test caching mechanism"""
    mock_response = {
        "response": {
            "numFound": 1,
            "docs": [{
                "id": "10.1371/journal.pone.0123456",
                "title_display": "Cached Article"
            }]
        }
    }
    
    with patch.object(plos_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        # First call - should hit API
        results1 = await plos_connector.search("test query", limit=10)
        
        # Second call with same query - should use cache
        results2 = await plos_connector.search("test query", limit=10)
        
        # API should only be called once due to caching
        assert mock_request.call_count == 1
        assert results1 == results2


def test_connector_initialization(plos_connector):
    """Test connector initialization"""
    assert plos_connector.name == "plos"
    assert plos_connector.base_url is not None
    assert hasattr(plos_connector, 'rate_limiter')
    assert hasattr(plos_connector, 'cache')
