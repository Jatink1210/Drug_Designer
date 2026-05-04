"""
Pytest configuration and fixtures for connector tests

Provides shared fixtures and utilities for all connector tests.
"""

import pytest
from unittest.mock import Mock, MagicMock
import sys
import os

# Add apps/api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../apps/api'))


@pytest.fixture
def mock_response():
    """Create a mock HTTP response"""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"data": "test"}
    response.text = "test response"
    response.headers = {"Content-Type": "application/json"}
    return response


@pytest.fixture
def mock_error_response():
    """Create a mock error HTTP response"""
    response = Mock()
    response.status_code = 500
    response.json.side_effect = ValueError("No JSON")
    response.text = "Internal Server Error"
    response.headers = {"Content-Type": "text/html"}
    return response


@pytest.fixture
def mock_rate_limit_response():
    """Create a mock rate limit response"""
    response = Mock()
    response.status_code = 429
    response.json.return_value = {"error": "Rate limit exceeded"}
    response.text = "Too Many Requests"
    response.headers = {
        "Content-Type": "application/json",
        "Retry-After": "60"
    }
    return response


@pytest.fixture
def sample_article_data():
    """Sample article data for testing"""
    return {
        "pmid": "12345678",
        "title": "Sample Article Title",
        "authors": [
            {"name": "Smith J", "affiliation": "University A"},
            {"name": "Doe J", "affiliation": "University B"}
        ],
        "abstract": "This is a sample abstract for testing purposes.",
        "pubdate": "2024-01-15",
        "journal": "Nature",
        "volume": "123",
        "issue": "4",
        "pages": "567-578",
        "doi": "10.1038/nature12345",
        "mesh_terms": ["Neoplasms", "Drug Therapy", "Clinical Trials"]
    }


@pytest.fixture
def sample_protein_data():
    """Sample protein data for testing"""
    return {
        "uniprot_id": "P12345",
        "name": "Sample Protein",
        "gene_name": "GENE1",
        "organism": "Homo sapiens",
        "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL",
        "function": "Sample protein function description",
        "subcellular_location": ["Cytoplasm", "Nucleus"],
        "domains": [
            {"name": "Domain1", "start": 10, "end": 100},
            {"name": "Domain2", "start": 150, "end": 250}
        ]
    }


@pytest.fixture
def sample_compound_data():
    """Sample compound data for testing"""
    return {
        "chembl_id": "CHEMBL123",
        "name": "Sample Compound",
        "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
        "inchi": "InChI=1S/C13H18O2/c1-9(2)7-11-4-5-12(6-8-11)10(3)13(14)15/h4-6,8-10H,7H2,1-3H3,(H,14,15)",
        "molecular_weight": 206.28,
        "logp": 3.5,
        "hbd": 1,
        "hba": 2,
        "rotatable_bonds": 4,
        "psa": 37.3,
        "targets": ["P12345", "P67890"]
    }


@pytest.fixture
def sample_clinical_trial_data():
    """Sample clinical trial data for testing"""
    return {
        "nct_id": "NCT12345678",
        "title": "Sample Clinical Trial",
        "status": "Recruiting",
        "phase": "Phase 2",
        "conditions": ["Cancer", "Solid Tumor"],
        "interventions": [
            {"type": "Drug", "name": "Sample Drug A"},
            {"type": "Drug", "name": "Sample Drug B"}
        ],
        "sponsor": "Sample Pharma Inc",
        "start_date": "2024-01-01",
        "completion_date": "2026-12-31",
        "enrollment": 100,
        "locations": [
            {"facility": "Hospital A", "city": "Boston", "country": "USA"},
            {"facility": "Hospital B", "city": "London", "country": "UK"}
        ]
    }


@pytest.fixture
def sample_variant_data():
    """Sample genetic variant data for testing"""
    return {
        "rsid": "rs12345",
        "chromosome": "17",
        "position": 43044295,
        "ref_allele": "G",
        "alt_allele": "A",
        "gene": "BRCA1",
        "consequence": "missense_variant",
        "clinical_significance": "Pathogenic",
        "allele_frequency": 0.001,
        "populations": {
            "EUR": 0.0015,
            "AFR": 0.0008,
            "ASN": 0.0012
        }
    }


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "connector: marks tests for connectors"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    for item in items:
        # Add connector marker to all tests in connectors directory
        if "connectors" in str(item.fspath):
            item.add_marker(pytest.mark.connector)
        
        # Add unit marker to all tests in unit directory
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
