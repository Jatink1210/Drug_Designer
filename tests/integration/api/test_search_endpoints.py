"""
Integration tests for Search API endpoints.

Tests the search functionality including:
- Full-text search
- Faceted search
- Advanced search with filters
- Search suggestions and autocomplete
- Search history
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime

from apps.api.main import app
from apps.api.models.db_tables import User


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Mock authentication headers."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return User(
        id="user-123",
        email="test@example.com",
        full_name="Test User",
        role="researcher"
    )


class TestFullTextSearchEndpoints:
    """Test full-text search endpoints."""

    def test_global_search(self, client, auth_headers):
        """Test POST /api/v1/search endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search",
                headers=auth_headers,
                json={
                    "query": "Alzheimer's disease",
                    "limit": 50
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert "total" in data
            assert isinstance(data["results"], list)

    def test_search_with_pagination(self, client, auth_headers):
        """Test search with pagination parameters."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search",
                headers=auth_headers,
                json={
                    "query": "cancer",
                    "limit": 20,
                    "offset": 40
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) <= 20

    def test_search_empty_query(self, client, auth_headers):
        """Test search with empty query."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search",
                headers=auth_headers,
                json={"query": ""}
            )
            
            assert response.status_code in [200, 400]


class TestEntitySearchEndpoints:
    """Test entity-specific search endpoints."""

    def test_search_diseases(self, client, auth_headers):
        """Test POST /api/v1/search/diseases endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search/diseases",
                headers=auth_headers,
                json={
                    "query": "diabetes",
                    "filters": {
                        "category": ["metabolic", "endocrine"]
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "diseases" in data

    def test_search_targets(self, client, auth_headers):
        """Test POST /api/v1/search/targets endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search/targets",
                headers=auth_headers,
                json={
                    "query": "kinase",
                    "filters": {
                        "target_type": ["protein"]
                    }
                }
            )
            
            assert response.status_code == 200

    def test_search_molecules(self, client, auth_headers):
        """Test POST /api/v1/search/molecules endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search/molecules",
                headers=auth_headers,
                json={
                    "query": "aspirin",
                    "filters": {
                        "molecular_weight": {"min": 100, "max": 500}
                    }
                }
            )
            
            assert response.status_code == 200

    def test_search_evidence(self, client, auth_headers):
        """Test POST /api/v1/search/evidence endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search/evidence",
                headers=auth_headers,
                json={
                    "query": "clinical trial",
                    "filters": {
                        "evidence_type": ["clinical"],
                        "confidence_score": {"min": 0.7}
                    }
                }
            )
            
            assert response.status_code == 200


class TestFacetedSearchEndpoints:
    """Test faceted search endpoints."""

    def test_search_with_facets(self, client, auth_headers):
        """Test POST /api/v1/search/faceted endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search/faceted",
                headers=auth_headers,
                json={
                    "query": "cancer drug",
                    "facets": [
                        "entity_type",
                        "source",
                        "publication_year",
                        "confidence_level"
                    ]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert "facets" in data
            assert isinstance(data["facets"], dict)

    def test_get_available_facets(self, client, auth_headers):
        """Test GET /api/v1/search/facets endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/search/facets",
                headers=auth_headers,
                params={"entity_type": "disease"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "facets" in data


class TestAdvancedSearchEndpoints:
    """Test advanced search with complex filters."""

    def test_advanced_search(self, client, auth_headers):
        """Test POST /api/v1/search/advanced endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search/advanced",
                headers=auth_headers,
                json={
                    "query": "Alzheimer's",
                    "filters": {
                        "entity_types": ["disease", "target", "evidence"],
                        "date_range": {
                            "start": "2020-01-01",
                            "end": "2026-04-23"
                        },
                        "confidence_score": {"min": 0.8},
                        "sources": ["pubmed", "clinicaltrials", "opentargets"]
                    },
                    "sort_by": "relevance",
                    "sort_order": "desc"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "results" in data

    def test_boolean_search(self, client, auth_headers):
        """Test POST /api/v1/search/boolean endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search/boolean",
                headers=auth_headers,
                json={
                    "query": "(Alzheimer OR dementia) AND (drug OR therapy) NOT placebo"
                }
            )
            
            assert response.status_code == 200


class TestAutocompleteEndpoints:
    """Test autocomplete and suggestion endpoints."""

    def test_autocomplete(self, client, auth_headers):
        """Test GET /api/v1/search/autocomplete endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/search/autocomplete",
                headers=auth_headers,
                params={"query": "alzh", "limit": 10}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "suggestions" in data
            assert isinstance(data["suggestions"], list)

    def test_search_suggestions(self, client, auth_headers):
        """Test GET /api/v1/search/suggestions endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/search/suggestions",
                headers=auth_headers,
                params={"query": "cancer"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "suggestions" in data

    def test_did_you_mean(self, client, auth_headers):
        """Test GET /api/v1/search/did-you-mean endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/search/did-you-mean",
                headers=auth_headers,
                params={"query": "alzhimers"}  # Misspelled
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "suggestion" in data or "suggestions" in data


class TestSearchHistoryEndpoints:
    """Test search history endpoints."""

    def test_get_search_history(self, client, auth_headers):
        """Test GET /api/v1/search/history endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/search/history",
                headers=auth_headers,
                params={"limit": 20}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "history" in data
            assert isinstance(data["history"], list)

    def test_clear_search_history(self, client, auth_headers):
        """Test DELETE /api/v1/search/history endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/search/history",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204]

    def test_delete_search_history_item(self, client, auth_headers):
        """Test DELETE /api/v1/search/history/{item_id} endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/search/history/item-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]


class TestSavedSearchesEndpoints:
    """Test saved searches endpoints."""

    def test_save_search(self, client, auth_headers):
        """Test POST /api/v1/search/saved endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search/saved",
                headers=auth_headers,
                json={
                    "name": "My Cancer Research",
                    "query": "cancer drug therapy",
                    "filters": {
                        "entity_types": ["disease", "target"]
                    }
                }
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "search_id" in data

    def test_get_saved_searches(self, client, auth_headers):
        """Test GET /api/v1/search/saved endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/search/saved",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "searches" in data

    def test_execute_saved_search(self, client, auth_headers):
        """Test POST /api/v1/search/saved/{search_id}/execute endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search/saved/search-123/execute",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_delete_saved_search(self, client, auth_headers):
        """Test DELETE /api/v1/search/saved/{search_id} endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/search/saved/search-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]


class TestSearchFiltersEndpoints:
    """Test search filter endpoints."""

    def test_get_available_filters(self, client, auth_headers):
        """Test GET /api/v1/search/filters endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/search/filters",
                headers=auth_headers,
                params={"entity_type": "disease"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "filters" in data

    def test_validate_filters(self, client, auth_headers):
        """Test POST /api/v1/search/filters/validate endpoint."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search/filters/validate",
                headers=auth_headers,
                json={
                    "filters": {
                        "molecular_weight": {"min": 100, "max": 500},
                        "confidence_score": {"min": 0.7}
                    }
                }
            )
            
            assert response.status_code == 200


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.post(
            "/api/v1/search",
            json={"query": "test"}
        )
        assert response.status_code == 401

    def test_invalid_search_query(self, client, auth_headers):
        """Test search with invalid query."""
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/search",
                headers=auth_headers,
                json={"query": "a" * 1000}  # Too long
            )
            
            assert response.status_code in [400, 422]


# Performance tests
class TestPerformance:
    """Test performance of search endpoints."""

    def test_search_performance(self, client, auth_headers):
        """Test search endpoint performance."""
        import time
        
        with patch("apps.api.routers.search.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.post(
                "/api/v1/search",
                headers=auth_headers,
                json={"query": "cancer", "limit": 100}
            )
            duration = time.time() - start
            
            assert response.status_code == 200
            assert duration < 3.0  # Should complete in under 3 seconds
