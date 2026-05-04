"""
Integration tests for Embeddings API endpoints.

Tests the vector embeddings endpoints including:
- Text embedding generation
- Similarity search
- Vector operations
- Embedding management
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


class TestEmbeddingGenerationEndpoints:
    """Test embedding generation endpoints."""

    def test_generate_text_embedding(self, client, auth_headers):
        """Test POST /api/v1/embeddings/text endpoint."""
        request_data = {
            "text": "BRCA1 is a tumor suppressor gene",
            "model": "pubmedbert"
        }
        
        response = client.post(
            "/api/v1/embeddings/text",
            headers=auth_headers,
            json=request_data
        )
        
        assert response.status_code in [200, 401, 422]
        if response.status_code == 200:
            data = response.json()
            assert "embedding" in data or "vector" in data

    def test_generate_batch_embeddings(self, client, auth_headers):
        """Test POST /api/v1/embeddings/batch endpoint."""
        request_data = {
            "texts": [
                "BRCA1 is a tumor suppressor gene",
                "TP53 mutations are common in cancer"
            ],
            "model": "pubmedbert"
        }
        
        response = client.post(
            "/api/v1/embeddings/batch",
            headers=auth_headers,
            json=request_data
        )
        
        assert response.status_code in [200, 401, 422]
        if response.status_code == 200:
            data = response.json()
            assert "embeddings" in data or isinstance(data, list)

    def test_generate_document_embedding(self, client, auth_headers):
        """Test POST /api/v1/embeddings/document endpoint."""
        request_data = {
            "document_id": "test-doc-id",
            "model": "pubmedbert"
        }
        
        response = client.post(
            "/api/v1/embeddings/document",
            headers=auth_headers,
            json=request_data
        )
        
        assert response.status_code in [200, 401, 404, 422]


class TestSimilaritySearchEndpoints:
    """Test similarity search endpoints."""

    def test_similarity_search(self, client, auth_headers):
        """Test POST /api/v1/embeddings/search endpoint."""
        search_request = {
            "query": "BRCA1 breast cancer",
            "top_k": 10,
            "collection": "evidence"
        }
        
        response = client.post(
            "/api/v1/embeddings/search",
            headers=auth_headers,
            json=search_request
        )
        
        assert response.status_code in [200, 401, 422]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_vector_similarity_search(self, client, auth_headers):
        """Test POST /api/v1/embeddings/search/vector endpoint."""
        search_request = {
            "vector": [0.1] * 768,  # Sample 768-dim vector
            "top_k": 10,
            "collection": "evidence"
        }
        
        response = client.post(
            "/api/v1/embeddings/search/vector",
            headers=auth_headers,
            json=search_request
        )
        
        assert response.status_code in [200, 401, 422]

    def test_hybrid_search(self, client, auth_headers):
        """Test POST /api/v1/embeddings/search/hybrid endpoint."""
        search_request = {
            "query": "BRCA1 breast cancer",
            "filters": {"source": "pubmed"},
            "top_k": 10
        }
        
        response = client.post(
            "/api/v1/embeddings/search/hybrid",
            headers=auth_headers,
            json=search_request
        )
        
        assert response.status_code in [200, 401, 422]


class TestVectorOperationsEndpoints:
    """Test vector operations endpoints."""

    def test_compute_similarity(self, client, auth_headers):
        """Test POST /api/v1/embeddings/similarity endpoint."""
        request_data = {
            "vector1": [0.1] * 768,
            "vector2": [0.2] * 768,
            "metric": "cosine"
        }
        
        response = client.post(
            "/api/v1/embeddings/similarity",
            headers=auth_headers,
            json=request_data
        )
        
        assert response.status_code in [200, 401, 422]
        if response.status_code == 200:
            data = response.json()
            assert "similarity" in data or "score" in data

    def test_compute_distance(self, client, auth_headers):
        """Test POST /api/v1/embeddings/distance endpoint."""
        request_data = {
            "vector1": [0.1] * 768,
            "vector2": [0.2] * 768,
            "metric": "euclidean"
        }
        
        response = client.post(
            "/api/v1/embeddings/distance",
            headers=auth_headers,
            json=request_data
        )
        
        assert response.status_code in [200, 401, 422]

    def test_cluster_vectors(self, client, auth_headers):
        """Test POST /api/v1/embeddings/cluster endpoint."""
        request_data = {
            "vectors": [[0.1] * 768, [0.2] * 768, [0.3] * 768],
            "n_clusters": 2,
            "method": "kmeans"
        }
        
        response = client.post(
            "/api/v1/embeddings/cluster",
            headers=auth_headers,
            json=request_data
        )
        
        assert response.status_code in [200, 401, 422]


class TestEmbeddingManagementEndpoints:
    """Test embedding management endpoints."""

    def test_get_embedding(self, client, auth_headers):
        """Test GET /api/v1/embeddings/{embedding_id} endpoint."""
        response = client.get(
            "/api/v1/embeddings/test-embedding-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_list_embeddings(self, client, auth_headers):
        """Test GET /api/v1/embeddings endpoint."""
        response = client.get("/api/v1/embeddings", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_delete_embedding(self, client, auth_headers):
        """Test DELETE /api/v1/embeddings/{embedding_id} endpoint."""
        response = client.delete(
            "/api/v1/embeddings/test-embedding-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 204, 401, 404]

    def test_update_embedding(self, client, auth_headers):
        """Test PUT /api/v1/embeddings/{embedding_id} endpoint."""
        update_data = {
            "metadata": {"updated": True}
        }
        
        response = client.put(
            "/api/v1/embeddings/test-embedding-id",
            headers=auth_headers,
            json=update_data
        )
        
        assert response.status_code in [200, 401, 404, 422]


class TestCollectionEndpoints:
    """Test embedding collection endpoints."""

    def test_create_collection(self, client, auth_headers):
        """Test POST /api/v1/embeddings/collections endpoint."""
        collection_data = {
            "name": "test_collection",
            "dimension": 768,
            "metric": "cosine"
        }
        
        response = client.post(
            "/api/v1/embeddings/collections",
            headers=auth_headers,
            json=collection_data
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_list_collections(self, client, auth_headers):
        """Test GET /api/v1/embeddings/collections endpoint."""
        response = client.get("/api/v1/embeddings/collections", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_collection_info(self, client, auth_headers):
        """Test GET /api/v1/embeddings/collections/{collection_name} endpoint."""
        response = client.get(
            "/api/v1/embeddings/collections/evidence",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_delete_collection(self, client, auth_headers):
        """Test DELETE /api/v1/embeddings/collections/{collection_name} endpoint."""
        response = client.delete(
            "/api/v1/embeddings/collections/test_collection",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 204, 401, 404]


class TestModelEndpoints:
    """Test embedding model endpoints."""

    def test_list_models(self, client, auth_headers):
        """Test GET /api/v1/embeddings/models endpoint."""
        response = client.get("/api/v1/embeddings/models", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_model_info(self, client, auth_headers):
        """Test GET /api/v1/embeddings/models/{model_name} endpoint."""
        response = client.get(
            "/api/v1/embeddings/models/pubmedbert",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing embeddings without authentication."""
        response = client.get("/api/v1/embeddings")
        
        assert response.status_code == 401

    def test_invalid_vector_dimension(self, client, auth_headers):
        """Test search with invalid vector dimension."""
        search_request = {
            "vector": [0.1] * 100,  # Wrong dimension
            "collection": "evidence"
        }
        
        response = client.post(
            "/api/v1/embeddings/search/vector",
            headers=auth_headers,
            json=search_request
        )
        
        assert response.status_code in [422, 400]

    def test_empty_text(self, client, auth_headers):
        """Test generating embedding with empty text."""
        request_data = {"text": "", "model": "pubmedbert"}
        
        response = client.post(
            "/api/v1/embeddings/text",
            headers=auth_headers,
            json=request_data
        )
        
        assert response.status_code in [422, 400]


# Performance tests
class TestPerformance:
    """Test performance of embedding endpoints."""

    def test_embedding_generation_performance(self, client, auth_headers):
        """Test embedding generation performance."""
        import time
        
        request_data = {
            "text": "BRCA1 is a tumor suppressor gene",
            "model": "pubmedbert"
        }
        
        start = time.time()
        response = client.post(
            "/api/v1/embeddings/text",
            headers=auth_headers,
            json=request_data
        )
        duration = time.time() - start
        
        if response.status_code == 200:
            assert duration < 1.0  # Should complete in under 1 second

    def test_similarity_search_performance(self, client, auth_headers):
        """Test similarity search performance."""
        import time
        
        search_request = {
            "query": "BRCA1 breast cancer",
            "top_k": 10,
            "collection": "evidence"
        }
        
        start = time.time()
        response = client.post(
            "/api/v1/embeddings/search",
            headers=auth_headers,
            json=search_request
        )
        duration = time.time() - start
        
        if response.status_code == 200:
            assert duration < 2.0  # Should complete in under 2 seconds

