"""
Integration tests for ML Models API endpoints.

Tests the ML model management endpoints including:
- Model listing and retrieval
- Model inference
- Model training and fine-tuning
- Model versioning
- Model performance metrics
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


class TestModelListingEndpoints:
    """Test model listing and retrieval endpoints."""

    def test_list_models(self, client, auth_headers):
        """Test GET /api/v1/models endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/models",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "models" in data
            assert isinstance(data["models"], list)

    def test_get_model_details(self, client, auth_headers):
        """Test GET /api/v1/models/{model_id} endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/models/esm2",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "model_id" in data
                assert "name" in data
                assert "type" in data

    def test_get_model_catalog(self, client, auth_headers):
        """Test GET /api/v1/models/catalog endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/models/catalog",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "models" in data

    def test_filter_models_by_type(self, client, auth_headers):
        """Test GET /api/v1/models with type filter."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/models",
                headers=auth_headers,
                params={"type": "protein_language_model"}
            )
            
            assert response.status_code == 200


class TestModelInferenceEndpoints:
    """Test model inference endpoints."""

    def test_run_inference(self, client, auth_headers):
        """Test POST /api/v1/models/{model_id}/inference endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/esm2/inference",
                headers=auth_headers,
                json={
                    "input": {
                        "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL"
                    }
                }
            )
            
            assert response.status_code in [200, 202]
            data = response.json()
            assert "result" in data or "task_id" in data

    def test_batch_inference(self, client, auth_headers):
        """Test POST /api/v1/models/{model_id}/batch-inference endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/molformer/batch-inference",
                headers=auth_headers,
                json={
                    "inputs": [
                        {"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"},
                        {"smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O"}
                    ]
                }
            )
            
            assert response.status_code in [200, 202]

    def test_inference_with_explainability(self, client, auth_headers):
        """Test POST /api/v1/models/{model_id}/inference with explainability."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/pathogenicity/inference",
                headers=auth_headers,
                json={
                    "input": {
                        "variant": "chr1:12345:A>G"
                    },
                    "explain": True,
                    "explainer": "shap"
                }
            )
            
            assert response.status_code in [200, 202]


class TestModelTrainingEndpoints:
    """Test model training and fine-tuning endpoints."""

    def test_start_training(self, client, auth_headers):
        """Test POST /api/v1/models/{model_id}/train endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/custom-model/train",
                headers=auth_headers,
                json={
                    "training_data": "dataset-123",
                    "hyperparameters": {
                        "learning_rate": 0.001,
                        "batch_size": 32,
                        "epochs": 10
                    }
                }
            )
            
            assert response.status_code in [200, 202]
            data = response.json()
            assert "training_id" in data or "task_id" in data

    def test_fine_tune_model(self, client, auth_headers):
        """Test POST /api/v1/models/{model_id}/fine-tune endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/esm2/fine-tune",
                headers=auth_headers,
                json={
                    "dataset_id": "dataset-456",
                    "task": "protein_function_prediction",
                    "epochs": 5
                }
            )
            
            assert response.status_code in [200, 202]

    def test_get_training_status(self, client, auth_headers):
        """Test GET /api/v1/models/training/{training_id}/status endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/models/training/train-123/status",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_stop_training(self, client, auth_headers):
        """Test POST /api/v1/models/training/{training_id}/stop endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/training/train-123/stop",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestModelVersioningEndpoints:
    """Test model versioning endpoints."""

    def test_list_model_versions(self, client, auth_headers):
        """Test GET /api/v1/models/{model_id}/versions endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/models/esm2/versions",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "versions" in data

    def test_get_model_version(self, client, auth_headers):
        """Test GET /api/v1/models/{model_id}/versions/{version} endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/models/esm2/versions/v1.0",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_create_model_version(self, client, auth_headers):
        """Test POST /api/v1/models/{model_id}/versions endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/custom-model/versions",
                headers=auth_headers,
                json={
                    "version": "v2.0",
                    "description": "Improved accuracy",
                    "checkpoint_path": "/models/custom-model-v2.0.pt"
                }
            )
            
            assert response.status_code in [200, 201, 404]


class TestModelPerformanceEndpoints:
    """Test model performance metrics endpoints."""

    def test_get_model_metrics(self, client, auth_headers):
        """Test GET /api/v1/models/{model_id}/metrics endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/models/esm2/metrics",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "metrics" in data

    def test_benchmark_model(self, client, auth_headers):
        """Test POST /api/v1/models/{model_id}/benchmark endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/esm2/benchmark",
                headers=auth_headers,
                json={
                    "dataset": "benchmark-dataset-123",
                    "metrics": ["accuracy", "f1_score", "auc"]
                }
            )
            
            assert response.status_code in [200, 202]

    def test_compare_models(self, client, auth_headers):
        """Test POST /api/v1/models/compare endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/compare",
                headers=auth_headers,
                json={
                    "model_ids": ["esm2", "molformer", "alphafold"],
                    "metrics": ["accuracy", "inference_time", "memory_usage"]
                }
            )
            
            assert response.status_code == 200


class TestModelConfigurationEndpoints:
    """Test model configuration endpoints."""

    def test_get_model_config(self, client, auth_headers):
        """Test GET /api/v1/models/{model_id}/config endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/models/esm2/config",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_update_model_config(self, client, auth_headers):
        """Test PATCH /api/v1/models/{model_id}/config endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.patch(
                "/api/v1/models/custom-model/config",
                headers=auth_headers,
                json={
                    "batch_size": 64,
                    "use_gpu": True,
                    "precision": "fp16"
                }
            )
            
            assert response.status_code in [200, 404]


class TestModelDeploymentEndpoints:
    """Test model deployment endpoints."""

    def test_deploy_model(self, client, auth_headers):
        """Test POST /api/v1/models/{model_id}/deploy endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/custom-model/deploy",
                headers=auth_headers,
                json={
                    "environment": "production",
                    "replicas": 3,
                    "resources": {
                        "cpu": "2",
                        "memory": "8Gi",
                        "gpu": "1"
                    }
                }
            )
            
            assert response.status_code in [200, 202]

    def test_undeploy_model(self, client, auth_headers):
        """Test POST /api/v1/models/{model_id}/undeploy endpoint."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/custom-model/undeploy",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.get("/api/v1/models")
        assert response.status_code == 401

    def test_invalid_model_id(self, client, auth_headers):
        """Test accessing non-existent model."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/models/nonexistent-model",
                headers=auth_headers
            )
            
            assert response.status_code == 404

    def test_invalid_inference_input(self, client, auth_headers):
        """Test inference with invalid input."""
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/models/esm2/inference",
                headers=auth_headers,
                json={"input": {}}
            )
            
            assert response.status_code in [400, 422]


# Performance tests
class TestPerformance:
    """Test performance of model endpoints."""

    def test_inference_performance(self, client, auth_headers):
        """Test model inference performance."""
        import time
        
        with patch("apps.api.routers.models.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.post(
                "/api/v1/models/esm2/inference",
                headers=auth_headers,
                json={
                    "input": {"sequence": "MKTAYIAKQRQISFVK"}
                }
            )
            duration = time.time() - start
            
            assert response.status_code in [200, 202]
            # Async inference should return quickly
            if response.status_code == 202:
                assert duration < 2.0
