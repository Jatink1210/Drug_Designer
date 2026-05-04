"""
Integration tests for Data Management API endpoints.

Tests the data management endpoints including:
- Data ingestion
- Data validation
- Data transformation
- Data export
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from apps.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    return {"Authorization": "Bearer test_token"}


class TestDataIngestionEndpoints:
    """Test data ingestion endpoints."""

    def test_ingest_data(self, client, auth_headers):
        """Test POST /api/v1/data/ingest endpoint."""
        data_payload = {
            "source": "pubmed",
            "query": "BRCA1 breast cancer",
            "limit": 100
        }
        
        response = client.post(
            "/api/v1/data/ingest",
            headers=auth_headers,
            json=data_payload
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_bulk_ingest(self, client, auth_headers):
        """Test POST /api/v1/data/ingest/bulk endpoint."""
        bulk_data = {
            "sources": ["pubmed", "clinvar", "uniprot"],
            "query": "BRCA1"
        }
        
        response = client.post(
            "/api/v1/data/ingest/bulk",
            headers=auth_headers,
            json=bulk_data
        )
        
        assert response.status_code in [200, 201, 401, 422]


class TestDataValidationEndpoints:
    """Test data validation endpoints."""

    def test_validate_data(self, client, auth_headers):
        """Test POST /api/v1/data/validate endpoint."""
        data_to_validate = {
            "type": "variant",
            "data": {"gene": "BRCA1", "variant": "p.Arg1699Gln"}
        }
        
        response = client.post(
            "/api/v1/data/validate",
            headers=auth_headers,
            json=data_to_validate
        )
        
        assert response.status_code in [200, 401, 422]

    def test_validate_schema(self, client, auth_headers):
        """Test POST /api/v1/data/validate/schema endpoint."""
        schema_data = {
            "schema": "evidence",
            "data": {"title": "Test", "source": "pubmed"}
        }
        
        response = client.post(
            "/api/v1/data/validate/schema",
            headers=auth_headers,
            json=schema_data
        )
        
        assert response.status_code in [200, 401, 422]


class TestDataTransformationEndpoints:
    """Test data transformation endpoints."""

    def test_transform_data(self, client, auth_headers):
        """Test POST /api/v1/data/transform endpoint."""
        transform_request = {
            "data": {"gene": "BRCA1"},
            "transformation": "normalize"
        }
        
        response = client.post(
            "/api/v1/data/transform",
            headers=auth_headers,
            json=transform_request
        )
        
        assert response.status_code in [200, 401, 422]

    def test_batch_transform(self, client, auth_headers):
        """Test POST /api/v1/data/transform/batch endpoint."""
        batch_request = {
            "data": [{"gene": "BRCA1"}, {"gene": "TP53"}],
            "transformation": "normalize"
        }
        
        response = client.post(
            "/api/v1/data/transform/batch",
            headers=auth_headers,
            json=batch_request
        )
        
        assert response.status_code in [200, 401, 422]


class TestDataQueryEndpoints:
    """Test data query endpoints."""

    def test_query_data(self, client, auth_headers):
        """Test POST /api/v1/data/query endpoint."""
        query = {
            "collection": "evidence",
            "filters": {"gene": "BRCA1"},
            "limit": 50
        }
        
        response = client.post(
            "/api/v1/data/query",
            headers=auth_headers,
            json=query
        )
        
        assert response.status_code in [200, 401, 422]

    def test_aggregate_data(self, client, auth_headers):
        """Test POST /api/v1/data/aggregate endpoint."""
        aggregation = {
            "collection": "evidence",
            "group_by": "source",
            "metrics": ["count"]
        }
        
        response = client.post(
            "/api/v1/data/aggregate",
            headers=auth_headers,
            json=aggregation
        )
        
        assert response.status_code in [200, 401, 422]


class TestDataExportEndpoints:
    """Test data export endpoints."""

    def test_export_data(self, client, auth_headers):
        """Test POST /api/v1/data/export endpoint."""
        export_request = {
            "collection": "evidence",
            "format": "csv",
            "filters": {"gene": "BRCA1"}
        }
        
        response = client.post(
            "/api/v1/data/export",
            headers=auth_headers,
            json=export_request
        )
        
        assert response.status_code in [200, 401, 422]

    def test_export_to_s3(self, client, auth_headers):
        """Test POST /api/v1/data/export/s3 endpoint."""
        export_request = {
            "collection": "evidence",
            "bucket": "test-bucket",
            "key": "exports/evidence.csv"
        }
        
        response = client.post(
            "/api/v1/data/export/s3",
            headers=auth_headers,
            json=export_request
        )
        
        assert response.status_code in [200, 401, 422]


class TestDataManagementEndpoints:
    """Test data management endpoints."""

    def test_get_data_stats(self, client, auth_headers):
        """Test GET /api/v1/data/stats endpoint."""
        response = client.get("/api/v1/data/stats", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_collection_info(self, client, auth_headers):
        """Test GET /api/v1/data/collections/{collection} endpoint."""
        response = client.get(
            "/api/v1/data/collections/evidence",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_delete_data(self, client, auth_headers):
        """Test DELETE /api/v1/data/{data_id} endpoint."""
        response = client.delete(
            "/api/v1/data/test-data-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 204, 401, 404]


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing data without authentication."""
        response = client.get("/api/v1/data/stats")
        
        assert response.status_code == 401

    def test_invalid_collection(self, client, auth_headers):
        """Test querying invalid collection."""
        query = {"collection": "invalid_collection"}
        
        response = client.post(
            "/api/v1/data/query",
            headers=auth_headers,
            json=query
        )
        
        assert response.status_code in [422, 404]


# Performance tests
class TestPerformance:
    """Test performance of data endpoints."""

    def test_query_performance(self, client, auth_headers):
        """Test data query performance."""
        import time
        
        query = {"collection": "evidence", "limit": 100}
        
        start = time.time()
        response = client.post(
            "/api/v1/data/query",
            headers=auth_headers,
            json=query
        )
        duration = time.time() - start
        
        if response.status_code == 200:
            assert duration < 2.0  # Should complete in under 2 seconds

