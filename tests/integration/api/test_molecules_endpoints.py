"""
Integration tests for Molecules API endpoints.

Tests the molecule management endpoints including:
- Molecule creation and import
- Molecule search and retrieval
- Molecular property calculation
- Similarity search
- Substructure search
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


class TestMoleculeCreationEndpoints:
    """Test molecule creation endpoints."""

    def test_create_molecule_from_smiles(self, client, auth_headers):
        """Test POST /api/v1/molecules endpoint with SMILES."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules",
                headers=auth_headers,
                json={
                    "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "name": "Aspirin",
                    "project_id": "proj-123"
                }
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "molecule_id" in data
            assert "smiles" in data

    def test_create_molecule_from_inchi(self, client, auth_headers):
        """Test POST /api/v1/molecules endpoint with InChI."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules",
                headers=auth_headers,
                json={
                    "inchi": "InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)",
                    "name": "Aspirin",
                    "project_id": "proj-123"
                }
            )
            
            assert response.status_code in [200, 201]

    def test_import_molecules_bulk(self, client, auth_headers):
        """Test POST /api/v1/molecules/bulk-import endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules/bulk-import",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "molecules": [
                        {"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "name": "Aspirin"},
                        {"smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "name": "Ibuprofen"}
                    ]
                }
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "molecule_ids" in data
            assert len(data["molecule_ids"]) == 2

    def test_import_from_sdf(self, client, auth_headers):
        """Test POST /api/v1/molecules/import-sdf endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            sdf_content = """
  Mrv0541 02231512512D          

  3  2  0  0  0  0            999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000    1.5000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2990    0.7500    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  2  3  1  0  0  0  0
M  END
$$$$
"""
            
            response = client.post(
                "/api/v1/molecules/import-sdf",
                headers=auth_headers,
                files={"file": ("molecules.sdf", sdf_content, "chemical/x-mdl-sdfile")},
                data={"project_id": "proj-123"}
            )
            
            assert response.status_code in [200, 201]


class TestMoleculeRetrievalEndpoints:
    """Test molecule retrieval endpoints."""

    def test_get_molecule(self, client, auth_headers):
        """Test GET /api/v1/molecules/{molecule_id} endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/molecules/mol-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "molecule_id" in data
                assert "smiles" in data

    def test_list_molecules(self, client, auth_headers):
        """Test GET /api/v1/molecules endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/molecules",
                headers=auth_headers,
                params={"project_id": "proj-123", "limit": 50}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "molecules" in data
            assert isinstance(data["molecules"], list)

    def test_get_molecule_structure(self, client, auth_headers):
        """Test GET /api/v1/molecules/{molecule_id}/structure endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/molecules/mol-123/structure",
                headers=auth_headers,
                params={"format": "svg"}
            )
            
            assert response.status_code in [200, 404]


class TestMolecularPropertyEndpoints:
    """Test molecular property calculation endpoints."""

    def test_calculate_properties(self, client, auth_headers):
        """Test POST /api/v1/molecules/{molecule_id}/properties endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules/mol-123/properties",
                headers=auth_headers,
                json={
                    "properties": [
                        "molecular_weight",
                        "logp",
                        "tpsa",
                        "hbd",
                        "hba",
                        "rotatable_bonds"
                    ]
                }
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "properties" in data

    def test_calculate_descriptors(self, client, auth_headers):
        """Test POST /api/v1/molecules/{molecule_id}/descriptors endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules/mol-123/descriptors",
                headers=auth_headers,
                json={
                    "descriptor_types": ["rdkit", "mordred"]
                }
            )
            
            assert response.status_code in [200, 404]

    def test_calculate_fingerprints(self, client, auth_headers):
        """Test POST /api/v1/molecules/{molecule_id}/fingerprints endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules/mol-123/fingerprints",
                headers=auth_headers,
                json={
                    "fingerprint_types": ["morgan", "maccs", "topological"]
                }
            )
            
            assert response.status_code in [200, 404]


class TestSimilaritySearchEndpoints:
    """Test similarity search endpoints."""

    def test_similarity_search(self, client, auth_headers):
        """Test POST /api/v1/molecules/similarity-search endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules/similarity-search",
                headers=auth_headers,
                json={
                    "query_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "threshold": 0.7,
                    "fingerprint_type": "morgan",
                    "limit": 100
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert isinstance(data["results"], list)

    def test_batch_similarity_search(self, client, auth_headers):
        """Test POST /api/v1/molecules/batch-similarity-search endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules/batch-similarity-search",
                headers=auth_headers,
                json={
                    "query_smiles_list": [
                        "CC(=O)OC1=CC=CC=C1C(=O)O",
                        "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
                    ],
                    "threshold": 0.7
                }
            )
            
            assert response.status_code == 200


class TestSubstructureSearchEndpoints:
    """Test substructure search endpoints."""

    def test_substructure_search(self, client, auth_headers):
        """Test POST /api/v1/molecules/substructure-search endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules/substructure-search",
                headers=auth_headers,
                json={
                    "query_smarts": "c1ccccc1",  # Benzene ring
                    "project_id": "proj-123",
                    "limit": 100
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "results" in data

    def test_mcs_search(self, client, auth_headers):
        """Test POST /api/v1/molecules/mcs-search endpoint (Maximum Common Substructure)."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules/mcs-search",
                headers=auth_headers,
                json={
                    "molecule_ids": ["mol-123", "mol-456", "mol-789"]
                }
            )
            
            assert response.status_code == 200


class TestMoleculeFilteringEndpoints:
    """Test molecule filtering endpoints."""

    def test_filter_by_properties(self, client, auth_headers):
        """Test POST /api/v1/molecules/filter endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules/filter",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "filters": {
                        "molecular_weight": {"min": 200, "max": 500},
                        "logp": {"min": -2, "max": 5},
                        "hbd": {"max": 5},
                        "hba": {"max": 10}
                    }
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "molecules" in data

    def test_apply_lipinski_filter(self, client, auth_headers):
        """Test POST /api/v1/molecules/filter/lipinski endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules/filter/lipinski",
                headers=auth_headers,
                json={"project_id": "proj-123"}
            )
            
            assert response.status_code == 200


class TestMoleculeUpdateEndpoints:
    """Test molecule update endpoints."""

    def test_update_molecule(self, client, auth_headers):
        """Test PATCH /api/v1/molecules/{molecule_id} endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.patch(
                "/api/v1/molecules/mol-123",
                headers=auth_headers,
                json={
                    "name": "Updated Molecule Name",
                    "notes": "Added notes"
                }
            )
            
            assert response.status_code in [200, 404]

    def test_add_molecule_tags(self, client, auth_headers):
        """Test POST /api/v1/molecules/{molecule_id}/tags endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules/mol-123/tags",
                headers=auth_headers,
                json={"tags": ["lead", "high-affinity", "selective"]}
            )
            
            assert response.status_code in [200, 404]


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.get("/api/v1/molecules/mol-123")
        assert response.status_code == 401

    def test_invalid_smiles(self, client, auth_headers):
        """Test creating molecule with invalid SMILES."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/molecules",
                headers=auth_headers,
                json={
                    "smiles": "INVALID_SMILES",
                    "project_id": "proj-123"
                }
            )
            
            assert response.status_code in [400, 422]

    def test_delete_molecule(self, client, auth_headers):
        """Test DELETE /api/v1/molecules/{molecule_id} endpoint."""
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/molecules/mol-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]


# Performance tests
class TestPerformance:
    """Test performance of molecule endpoints."""

    def test_similarity_search_performance(self, client, auth_headers):
        """Test similarity search performance."""
        import time
        
        with patch("apps.api.routers.molecules.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.post(
                "/api/v1/molecules/similarity-search",
                headers=auth_headers,
                json={
                    "query_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "threshold": 0.7,
                    "limit": 1000
                }
            )
            duration = time.time() - start
            
            assert response.status_code == 200
            assert duration < 5.0  # Should complete in under 5 seconds
