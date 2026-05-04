"""
Integration tests for export endpoints
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
        "email": "export@example.com",
        "password": "SecurePassword123!",
        "full_name": "Export User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "export@example.com",
        "password": "SecurePassword123!"
    })
    
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_export_pdf_dossier(client, auth_headers):
    """Test PDF dossier export"""
    response = client.post("/api/v1/exports/pdf", json={
        "project_id": "test_project_001",
        "include_sections": ["summary", "targets", "evidence", "provenance"],
        "format_options": {
            "include_toc": True,
            "include_appendix": True
        }
    }, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 0


def test_export_docx_report(client, auth_headers):
    """Test DOCX report export"""
    response = client.post("/api/v1/exports/docx", json={
        "project_id": "test_project_001",
        "template": "standard",
        "include_sections": ["executive_summary", "methodology", "results"]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_export_sdf_molecules(client, auth_headers):
    """Test SDF molecule export"""
    response = client.post("/api/v1/exports/sdf", json={
        "molecule_ids": ["mol_001", "mol_002", "mol_003"],
        "include_properties": True,
        "include_3d_coordinates": True
    }, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "chemical/x-mdl-sdfile"
    content = response.content.decode('utf-8')
    assert "$$$$" in content  # SDF delimiter


def test_export_bulk_project(client, auth_headers):
    """Test bulk project export"""
    response = client.post("/api/v1/exports/bulk", json={
        "project_id": "test_project_001",
        "include_data": ["targets", "evidence", "molecules", "reports"],
        "format": "zip"
    }, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "manifest.json" in str(response.content) or len(response.content) > 1000


def test_export_csv_data(client, auth_headers):
    """Test CSV data export"""
    response = client.post("/api/v1/exports/csv", json={
        "data_type": "targets",
        "project_id": "test_project_001",
        "columns": ["gene_symbol", "protein_name", "druggability_score", "priority_score"]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv"
    content = response.content.decode('utf-8')
    assert "gene_symbol" in content


def test_export_json_data(client, auth_headers):
    """Test JSON data export"""
    response = client.post("/api/v1/exports/json", json={
        "project_id": "test_project_001",
        "data_types": ["targets", "evidence", "molecules"]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "targets" in data or "evidence" in data


def test_export_with_provenance(client, auth_headers):
    """Test export with provenance tracking"""
    response = client.post("/api/v1/exports/pdf", json={
        "project_id": "test_project_001",
        "include_sections": ["summary", "provenance"],
        "provenance_detail": "full"
    }, headers=auth_headers)
    
    assert response.status_code == 200
    # Check export was logged
    history_response = client.get("/api/v1/exports/history", headers=auth_headers)
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) > 0


def test_export_large_dataset(client, auth_headers):
    """Test exporting large dataset"""
    response = client.post("/api/v1/exports/bulk", json={
        "project_id": "large_project_001",
        "include_data": ["all"],
        "compression": "high"
    }, headers=auth_headers, timeout=60)
    
    assert response.status_code in [200, 202]  # 202 for async processing


def test_export_custom_template(client, auth_headers):
    """Test export with custom template"""
    response = client.post("/api/v1/exports/docx", json={
        "project_id": "test_project_001",
        "template_id": "custom_template_001",
        "variables": {
            "company_name": "Test Pharma",
            "report_date": "2026-04-23"
        }
    }, headers=auth_headers)
    
    assert response.status_code == 200


def test_export_unauthorized(client):
    """Test export without authentication"""
    response = client.post("/api/v1/exports/pdf", json={
        "project_id": "test_project_001"
    })
    
    assert response.status_code == 401


def test_export_performance(client, auth_headers):
    """Test export performance"""
    import time
    
    start = time.time()
    response = client.post("/api/v1/exports/pdf", json={
        "project_id": "test_project_001",
        "include_sections": ["summary"]
    }, headers=auth_headers)
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 90.0  # Should complete in under 90 seconds
