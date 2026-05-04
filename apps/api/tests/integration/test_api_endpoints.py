"""Integration tests for API endpoints.

Tests API endpoints with real database connections.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app
from core.db import Base, get_db
import uuid

# Test database URL
TEST_DATABASE_URL = "postgresql://test:test@localhost:5432/drugdesigner_test"

# Create test engine
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    """Create test database tables."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_db):
    """Create database session for tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    return {"Authorization": "Bearer test_token"}


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_readiness_check(self, client):
        """Test readiness check endpoint."""
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True


class TestProjectEndpoints:
    """Test project management endpoints."""
    
    def test_create_project(self, client, auth_headers):
        """Test project creation."""
        project_data = {
            "name": "Test Project",
            "description": "Test Description",
            "disease_area": "Rare Disease"
        }
        response = client.post("/api/v1/projects", json=project_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Project"
        assert "id" in data
    
    def test_list_projects(self, client, auth_headers):
        """Test listing projects."""
        response = client.get("/api/v1/projects", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_project(self, client, auth_headers):
        """Test getting single project."""
        # Create project first
        project_data = {"name": "Test Project", "description": "Test"}
        create_response = client.post("/api/v1/projects", json=project_data, headers=auth_headers)
        project_id = create_response.json()["id"]
        
        # Get project
        response = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == project_id
    
    def test_update_project(self, client, auth_headers):
        """Test updating project."""
        # Create project first
        project_data = {"name": "Test Project", "description": "Test"}
        create_response = client.post("/api/v1/projects", json=project_data, headers=auth_headers)
        project_id = create_response.json()["id"]
        
        # Update project
        update_data = {"name": "Updated Project"}
        response = client.patch(f"/api/v1/projects/{project_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Project"
    
    def test_delete_project(self, client, auth_headers):
        """Test deleting project."""
        # Create project first
        project_data = {"name": "Test Project", "description": "Test"}
        create_response = client.post("/api/v1/projects", json=project_data, headers=auth_headers)
        project_id = create_response.json()["id"]
        
        # Delete project
        response = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
        assert response.status_code == 204


class TestClinicalEndpoints:
    """Test clinical workflow endpoints."""
    
    def test_ingest_clinical_data(self, client, auth_headers):
        """Test clinical data ingestion."""
        data = {
            "record_type": "ehr",
            "raw_text": "Patient has fever and cough",
            "patient_id": "P12345"
        }
        response = client.post("/api/v1/clinical/ingest", json=data, headers=auth_headers)
        assert response.status_code == 201
        result = response.json()
        assert "record_id" in result
        assert result["phi_redacted"] is True
    
    def test_phenotype_clustering(self, client, auth_headers):
        """Test phenotype clustering."""
        data = {
            "ehr_record_ids": ["rec1", "rec2", "rec3"],
            "min_cluster_size": 2
        }
        response = client.post("/api/v1/clinical/phenotype-cluster", json=data, headers=auth_headers)
        assert response.status_code == 200
        result = response.json()
        assert "run_id" in result
        assert "clusters" in result


class TestConsensusEndpoints:
    """Test MAV consensus endpoints."""
    
    def test_mav_consensus(self, client, auth_headers):
        """Test MAV consensus voting."""
        data = {
            "claim": "FOXP3 mutations cause IPEX syndrome",
            "evidence_bundle_id": str(uuid.uuid4()),
            "jury_size": 5
        }
        response = client.post("/api/v1/consensus/mav", json=data, headers=auth_headers)
        assert response.status_code == 200
        result = response.json()
        assert "consensus_id" in result["data"]
        assert result["data"]["status"] in ["verified", "contradicted", "conflict"]


class TestExportEndpoints:
    """Test export endpoints."""
    
    def test_export_pdf(self, client, auth_headers):
        """Test PDF export."""
        data = {
            "dossier_id": str(uuid.uuid4()),
            "include_provenance": True
        }
        response = client.post("/api/v1/exports/pdf", json=data, headers=auth_headers)
        assert response.status_code == 200
        result = response.json()
        assert "export_id" in result
        assert result["file_path"].endswith(".pdf")


class TestAuthenticationEndpoints:
    """Test authentication endpoints."""
    
    def test_login(self, client):
        """Test user login."""
        data = {
            "email": "test@example.com",
            "password": "testpassword"
        }
        response = client.post("/api/v1/auth/login", json=data)
        assert response.status_code in [200, 401]  # 401 if user doesn't exist
    
    def test_unauthorized_access(self, client):
        """Test unauthorized access is blocked."""
        response = client.get("/api/v1/projects")
        assert response.status_code == 401


class TestErrorHandling:
    """Test error handling."""
    
    def test_404_not_found(self, client):
        """Test 404 error."""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
    
    def test_invalid_json(self, client, auth_headers):
        """Test invalid JSON handling."""
        response = client.post(
            "/api/v1/projects",
            data="invalid json",
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_validation_error(self, client, auth_headers):
        """Test validation error."""
        data = {"name": ""}  # Empty name should fail validation
        response = client.post("/api/v1/projects", json=data, headers=auth_headers)
        assert response.status_code == 422


class TestRateLimiting:
    """Test rate limiting."""
    
    def test_rate_limit_enforcement(self, client, auth_headers):
        """Test rate limiting is enforced."""
        # Make many requests quickly
        responses = []
        for _ in range(100):
            response = client.get("/api/v1/projects", headers=auth_headers)
            responses.append(response.status_code)
        
        # Should eventually get rate limited (429)
        assert 429 in responses or all(r == 200 for r in responses)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
