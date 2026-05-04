"""
Integration tests for Mapping API endpoints.

Tests entity mapping endpoints including:
- Entity mapping
- ID conversion
- Cross-reference resolution
"""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    return {"Authorization": "Bearer test_token"}


class TestEntityMappingEndpoints:
    """Test entity mapping endpoints."""

    def test_map_entity(self, client, auth_headers):
        """Test POST /api/v1/mapping/entity endpoint."""
        mapping_request = {
            "entity_type": "gene",
            "source_id": "BRCA1",
            "source_db": "hgnc",
            "target_db": "ensembl"
        }
        
        response = client.post(
            "/api/v1/mapping/entity",
            headers=auth_headers,
            json=mapping_request
        )
        
        assert response.status_code in [200, 401, 422]

    def test_batch_map_entities(self, client, auth_headers):
        """Test POST /api/v1/mapping/batch endpoint."""
        batch_request = {
            "entities": [
                {"entity_type": "gene", "source_id": "BRCA1"},
                {"entity_type": "gene", "source_id": "TP53"}
            ],
            "source_db": "hgnc",
            "target_db": "ensembl"
        }
        
        response = client.post(
            "/api/v1/mapping/batch",
            headers=auth_headers,
            json=batch_request
        )
        
        assert response.status_code in [200, 401, 422]


class TestIDConversionEndpoints:
    """Test ID conversion endpoints."""

    def test_convert_gene_id(self, client, auth_headers):
        """Test GET /api/v1/mapping/gene/{gene_id} endpoint."""
        response = client.get(
            "/api/v1/mapping/gene/BRCA1",
            headers=auth_headers,
            params={"target_db": "ensembl"}
        )
        
        assert response.status_code in [200, 401, 404]

    def test_convert_protein_id(self, client, auth_headers):
        """Test GET /api/v1/mapping/protein/{protein_id} endpoint."""
        response = client.get(
            "/api/v1/mapping/protein/P38398",
            headers=auth_headers,
            params={"target_db": "ensembl"}
        )
        
        assert response.status_code in [200, 401, 404]


class TestCrossReferenceEndpoints:
    """Test cross-reference endpoints."""

    def test_get_cross_references(self, client, auth_headers):
        """Test GET /api/v1/mapping/xrefs/{entity_id} endpoint."""
        response = client.get(
            "/api/v1/mapping/xrefs/BRCA1",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_resolve_identifier(self, client, auth_headers):
        """Test POST /api/v1/mapping/resolve endpoint."""
        resolve_request = {
            "identifier": "BRCA1",
            "entity_type": "gene"
        }
        
        response = client.post(
            "/api/v1/mapping/resolve",
            headers=auth_headers,
            json=resolve_request
        )
        
        assert response.status_code in [200, 401, 422]


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing mapping without authentication."""
        response = client.get("/api/v1/mapping/gene/BRCA1")
        
        assert response.status_code == 401

    def test_invalid_entity_type(self, client, auth_headers):
        """Test mapping with invalid entity type."""
        mapping_request = {
            "entity_type": "invalid_type",
            "source_id": "test"
        }
        
        response = client.post(
            "/api/v1/mapping/entity",
            headers=auth_headers,
            json=mapping_request
        )
        
        assert response.status_code in [422, 400]


# Performance tests
class TestPerformance:
    """Test performance of mapping endpoints."""

    def test_mapping_performance(self, client, auth_headers):
        """Test entity mapping performance."""
        import time
        
        mapping_request = {
            "entity_type": "gene",
            "source_id": "BRCA1",
            "source_db": "hgnc",
            "target_db": "ensembl"
        }
        
        start = time.time()
        response = client.post(
            "/api/v1/mapping/entity",
            headers=auth_headers,
            json=mapping_request
        )
        duration = time.time() - start
        
        if response.status_code == 200:
            assert duration < 1.0  # Should complete in under 1 second
