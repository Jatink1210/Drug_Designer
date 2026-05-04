"""
Unit tests for EFO (Experimental Factor Ontology) connector
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from apps.api.connectors.efo import EFOConnector


@pytest.fixture
def efo_connector():
    """Fixture for EFO connector instance"""
    return EFOConnector()


@pytest.mark.asyncio
async def test_search_disease_success(efo_connector):
    """Test successful disease term search"""
    mock_response = {
        "response": {
            "docs": [
                {
                    "iri": "http://www.ebi.ac.uk/efo/EFO_0000001",
                    "label": "experimental factor",
                    "description": ["A variable under study"],
                    "synonyms": ["factor"]
                },
                {
                    "iri": "http://www.ebi.ac.uk/efo/EFO_0000408",
                    "label": "disease",
                    "description": ["A disease is a disposition"],
                    "synonyms": ["disorder", "illness"]
                }
            ]
        }
    }
    
    with patch.object(efo_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        results = await efo_connector.search("disease", limit=10)
        
        assert len(results) == 2
        assert results[0]["id"] == "EFO_0000001"
        assert results[0]["label"] == "experimental factor"
        assert "factor" in results[0]["synonyms"]
        
        # Verify provenance
        assert results[0]["provenance"]["source"] == "efo"


@pytest.mark.asyncio
async def test_get_term_by_id(efo_connector):
    """Test fetching specific EFO term by ID"""
    mock_response = {
        "iri": "http://www.ebi.ac.uk/efo/EFO_0000408",
        "label": "disease",
        "description": ["A disease is a disposition"],
        "synonyms": ["disorder", "illness"],
        "parents": ["EFO_0000001"]
    }
    
    with patch.object(efo_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        term = await efo_connector.get_by_id("EFO_0000408")
        
        assert term["id"] == "EFO_0000408"
        assert term["label"] == "disease"
        assert "disorder" in term["synonyms"]
        assert "EFO_0000001" in term["parents"]


@pytest.mark.asyncio
async def test_search_empty_results(efo_connector):
    """Test search with no results"""
    mock_response = {"response": {"docs": []}}
    
    with patch.object(efo_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        results = await efo_connector.search("nonexistent term", limit=10)
        
        assert len(results) == 0


@pytest.mark.asyncio
async def test_rate_limiting(efo_connector):
    """Test rate limiting behavior"""
    with patch.object(efo_connector, '_check_rate_limit') as mock_rate_limit:
        mock_rate_limit.return_value = False
        
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await efo_connector.search("test query")


def test_connector_initialization(efo_connector):
    """Test connector initialization"""
    assert efo_connector.name == "efo"
    assert efo_connector.base_url is not None
    assert hasattr(efo_connector, 'rate_limiter')
