"""
Unit tests for JSTOR connector
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from apps.api.connectors.jstor import JSTORConnector


@pytest.fixture
def jstor_connector():
    """Fixture for JSTOR connector instance"""
    return JSTORConnector()


@pytest.mark.asyncio
async def test_search_articles(jstor_connector):
    """Test article search"""
    mock_response = {
        "response": {
            "docs": [
                {
                    "id": "10.2307/12345678",
                    "title": ["Test Article on FOXP3"],
                    "author": ["Smith, J.", "Doe, A."],
                    "abstract": ["Study of FOXP3 mutations"],
                    "publicationYear": 2023
                }
            ]
        }
    }
    
    with patch.object(jstor_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        results = await jstor_connector.search("FOXP3 mutations", limit=10)
        
        assert len(results) == 1
        assert results[0]["id"] == "10.2307/12345678"
        assert "FOXP3" in results[0]["title"]
        assert results[0]["provenance"]["source"] == "jstor"


@pytest.mark.asyncio
async def test_get_article_by_doi(jstor_connector):
    """Test fetching article by DOI"""
    mock_response = {
        "id": "10.2307/12345678",
        "title": ["Specific Article"],
        "author": ["Author A"],
        "abstract": ["Specific abstract"]
    }
    
    with patch.object(jstor_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        article = await jstor_connector.get_by_id("10.2307/12345678")
        
        assert article["id"] == "10.2307/12345678"


def test_connector_initialization(jstor_connector):
    """Test connector initialization"""
    assert jstor_connector.name == "jstor"
    assert jstor_connector.base_url is not None
