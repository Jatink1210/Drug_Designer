"""
Unit tests for ICTRP (International Clinical Trials Registry Platform) connector
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from apps.api.connectors.ictrp import ICTRPConnector


@pytest.fixture
def ictrp_connector():
    """Fixture for ICTRP connector instance"""
    return ICTRPConnector()


@pytest.mark.asyncio
async def test_search_trials(ictrp_connector):
    """Test clinical trial search"""
    mock_response = {
        "trials": [
            {
                "trial_id": "EUCTR2023-001234-56",
                "title": "Phase II Study of FOXP3 Modulator",
                "condition": "IPEX syndrome",
                "status": "Recruiting",
                "sponsor": "Test Pharma"
            }
        ]
    }
    
    with patch.object(ictrp_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        results = await ictrp_connector.search("IPEX syndrome", limit=10)
        
        assert len(results) == 1
        assert results[0]["trial_id"] == "EUCTR2023-001234-56"
        assert "IPEX" in results[0]["condition"]
        assert results[0]["provenance"]["source"] == "ictrp"


@pytest.mark.asyncio
async def test_get_trial_by_id(ictrp_connector):
    """Test fetching trial by ID"""
    mock_response = {
        "trial_id": "EUCTR2023-001234-56",
        "title": "Specific Trial",
        "condition": "IPEX syndrome",
        "phase": "Phase II"
    }
    
    with patch.object(ictrp_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        trial = await ictrp_connector.get_by_id("EUCTR2023-001234-56")
        
        assert trial["trial_id"] == "EUCTR2023-001234-56"


def test_connector_initialization(ictrp_connector):
    """Test connector initialization"""
    assert ictrp_connector.name == "ictrp"
    assert ictrp_connector.base_url is not None
