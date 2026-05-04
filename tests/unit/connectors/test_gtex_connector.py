"""
Unit tests for GTEx (Genotype-Tissue Expression) connector
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from apps.api.connectors.gtex import GTExConnector


@pytest.fixture
def gtex_connector():
    """Fixture for GTEx connector instance"""
    return GTExConnector()


@pytest.mark.asyncio
async def test_get_gene_expression(gtex_connector):
    """Test fetching gene expression data"""
    mock_response = {
        "geneExpression": [
            {
                "gencodeId": "ENSG00000000003.15",
                "geneSymbol": "TSPAN6",
                "tissueSiteDetailId": "Brain_Cortex",
                "median": 12.5,
                "unit": "TPM"
            },
            {
                "gencodeId": "ENSG00000000003.15",
                "geneSymbol": "TSPAN6",
                "tissueSiteDetailId": "Heart_Left_Ventricle",
                "median": 8.3,
                "unit": "TPM"
            }
        ]
    }
    
    with patch.object(gtex_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        results = await gtex_connector.get_gene_expression("TSPAN6")
        
        assert len(results) == 2
        assert results[0]["gene_symbol"] == "TSPAN6"
        assert results[0]["tissue"] == "Brain_Cortex"
        assert results[0]["expression_median"] == 12.5
        
        # Verify provenance
        assert results[0]["provenance"]["source"] == "gtex"


@pytest.mark.asyncio
async def test_get_eqtl_data(gtex_connector):
    """Test fetching eQTL data"""
    mock_response = {
        "singleTissueEqtl": [
            {
                "geneSymbol": "FOXP3",
                "variantId": "rs123456",
                "tissueSiteDetailId": "Whole_Blood",
                "pValue": 1.2e-8,
                "nes": 0.45
            }
        ]
    }
    
    with patch.object(gtex_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        results = await gtex_connector.get_eqtl("FOXP3", "Whole_Blood")
        
        assert len(results) == 1
        assert results[0]["gene_symbol"] == "FOXP3"
        assert results[0]["variant_id"] == "rs123456"
        assert results[0]["p_value"] < 1e-5


@pytest.mark.asyncio
async def test_empty_results(gtex_connector):
    """Test handling of empty results"""
    mock_response = {"geneExpression": []}
    
    with patch.object(gtex_connector, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        results = await gtex_connector.get_gene_expression("NONEXISTENT")
        
        assert len(results) == 0


def test_connector_initialization(gtex_connector):
    """Test connector initialization"""
    assert gtex_connector.name == "gtex"
    assert gtex_connector.base_url is not None
