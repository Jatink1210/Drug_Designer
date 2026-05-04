"""
Integration tests for project management endpoints
"""

import pytest
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.core.db import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


TEST_DATABASE_URL = "postgresql://test:test@localhost:5432/drug_designer_test"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def client():
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    client.post("/api/v1/auth/register", json={
        "email": "project@example.com",
        "password": "SecurePassword123!",
        "full_name": "Project User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "project@example.com",
        "password": "SecurePassword123!"
    })
    
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_project(client, auth_headers):
    """Test project creation"""
    response = client.post("/api/v1/projects", json={
        "name": "IPEX Drug Discovery",
        "description": "Drug discovery project for IPEX syndrome",
        "disease": "IPEX syndrome",
        "status": "active"
    }, headers=auth_headers)
    
    assert response.status_code == 201
    project = response.json()
    assert project["name"] == "IPEX Drug Discovery"
    assert "id" in project
    assert "created_at" in project


def test_list_projects(client, auth_headers):
    """Test listing projects"""
    # Create test projects
    for i in range(3):
        client.post("/api/v1/projects", json={
            "name": f"Project {i}",
            "description": f"Description {i}",
            "disease": "Test Disease"
        }, headers=auth_headers)
    
    response = client.get("/api/v1/projects", headers=auth_headers)
    
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) >= 3


def test_get_project_by_id(client, auth_headers):
    """Test getting project by ID"""
    # Create project
    create_response = client.post("/api/v1/projects", json={
        "name": "Test Project",
        "description": "Test Description",
        "disease": "Test Disease"
    }, headers=auth_headers)
    
    project_id = create_response.json()["id"]
    
    # Get project
    response = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    
    assert response.status_code == 200
    project = response.json()
    assert project["id"] == project_id
    assert project["name"] == "Test Project"


def test_update_project(client, auth_headers):
    """Test updating project"""
    # Create project
    create_response = client.post("/api/v1/projects", json={
        "name": "Original Name",
        "description": "Original Description",
        "disease": "Test Disease"
    }, headers=auth_headers)
    
    project_id = create_response.json()["id"]
    
    # Update project
    response = client.patch(f"/api/v1/projects/{project_id}", json={
        "name": "Updated Name",
        "status": "completed"
    }, headers=auth_headers)
    
    assert response.status_code == 200
    updated_project = response.json()
    assert updated_project["name"] == "Updated Name"
    assert updated_project["status"] == "completed"


def test_delete_project(client, auth_headers):
    """Test deleting project"""
    # Create project
    create_response = client.post("/api/v1/projects", json={
        "name": "To Delete",
        "description": "Will be deleted",
        "disease": "Test Disease"
    }, headers=auth_headers)
    
    project_id = create_response.json()["id"]
    
    # Delete project
    response = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    
    assert response.status_code == 204
    
    # Verify deletion
    get_response = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_project_pagination(client, auth_headers):
    """Test project pagination"""
    # Create 15 projects
    for i in range(15):
        client.post("/api/v1/projects", json={
            "name": f"Project {i}",
            "description": f"Description {i}",
            "disease": "Test Disease"
        }, headers=auth_headers)
    
    # Get first page
    response = client.get("/api/v1/projects?page=1&limit=10", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["total"] >= 15
    assert data["page"] == 1


def test_project_filtering(client, auth_headers):
    """Test project filtering"""
    # Create projects with different statuses
    client.post("/api/v1/projects", json={
        "name": "Active Project",
        "description": "Active",
        "disease": "Disease A",
        "status": "active"
    }, headers=auth_headers)
    
    client.post("/api/v1/projects", json={
        "name": "Completed Project",
        "description": "Completed",
        "disease": "Disease B",
        "status": "completed"
    }, headers=auth_headers)
    
    # Filter by status
    response = client.get("/api/v1/projects?status=active", headers=auth_headers)
    
    assert response.status_code == 200
    projects = response.json()
    assert all(p["status"] == "active" for p in projects)


def test_project_search(client, auth_headers):
    """Test project search"""
    # Create searchable project
    client.post("/api/v1/projects", json={
        "name": "Unique IPEX Project",
        "description": "IPEX syndrome research",
        "disease": "IPEX syndrome"
    }, headers=auth_headers)
    
    # Search
    response = client.get("/api/v1/projects/search?q=IPEX", headers=auth_headers)
    
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert any("IPEX" in p["name"] or "IPEX" in p["description"] for p in results)


def test_project_unauthorized_access(client):
    """Test unauthorized project access"""
    response = client.get("/api/v1/projects")
    
    assert response.status_code == 401


def test_project_not_found(client, auth_headers):
    """Test accessing non-existent project"""
    response = client.get("/api/v1/projects/99999", headers=auth_headers)
    
    assert response.status_code == 404
