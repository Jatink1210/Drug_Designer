"""
Integration tests for Pathways API endpoints.

Tests the biological pathway endpoints including:
- Pathway search and retrieval
- Pathway analysis
- Pathway enrichment
- Pathway visualization
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


class TestPathwaySearchEndpoints:
    """Test pathway search and retrieval endpoints."""

    def test_search_pathways(self, client, auth_headers):
        """Test POST /api/v1/pathways/search endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/search",
                headers=auth_headers,
                json={
                    "query": "apoptosis",
                    "databases": ["kegg", "reactome", "wikipathways"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "pathways" in data
            assert isinstance(data["pathways"], list)

    def test_get_pathway_details(self, client, auth_headers):
        """Test GET /api/v1/pathways/{pathway_id} endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/pathways/hsa04210",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "pathway_id" in data
                assert "name" in data

    def test_list_pathways_by_category(self, client, auth_headers):
        """Test GET /api/v1/pathways endpoint with category filter."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/pathways",
                headers=auth_headers,
                params={"category": "signal_transduction"}
            )
            
            assert response.status_code == 200

    def test_get_pathway_genes(self, client, auth_headers):
        """Test GET /api/v1/pathways/{pathway_id}/genes endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/pathways/hsa04210/genes",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestPathwayEnrichmentEndpoints:
    """Test pathway enrichment analysis endpoints."""

    def test_run_enrichment_analysis(self, client, auth_headers):
        """Test POST /api/v1/pathways/enrichment endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/enrichment",
                headers=auth_headers,
                json={
                    "gene_list": ["TP53", "BRCA1", "EGFR", "KRAS"],
                    "background": "genome",
                    "databases": ["kegg", "reactome"],
                    "p_value_cutoff": 0.05
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "enriched_pathways" in data

    def test_gsea_analysis(self, client, auth_headers):
        """Test POST /api/v1/pathways/gsea endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/gsea",
                headers=auth_headers,
                json={
                    "ranked_genes": {
                        "TP53": 5.2,
                        "BRCA1": 4.8,
                        "EGFR": -3.1
                    },
                    "gene_sets": ["hallmark", "kegg"]
                }
            )
            
            assert response.status_code == 200

    def test_over_representation_analysis(self, client, auth_headers):
        """Test POST /api/v1/pathways/ora endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/ora",
                headers=auth_headers,
                json={
                    "gene_list": ["TP53", "BRCA1", "EGFR"],
                    "universe": 20000,
                    "correction_method": "fdr_bh"
                }
            )
            
            assert response.status_code == 200


class TestPathwayAnalysisEndpoints:
    """Test pathway analysis endpoints."""

    def test_analyze_pathway_crosstalk(self, client, auth_headers):
        """Test POST /api/v1/pathways/crosstalk endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/crosstalk",
                headers=auth_headers,
                json={
                    "pathway_ids": ["hsa04210", "hsa04110", "hsa04151"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "crosstalk" in data

    def test_pathway_topology_analysis(self, client, auth_headers):
        """Test POST /api/v1/pathways/{pathway_id}/topology endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/hsa04210/topology",
                headers=auth_headers,
                json={
                    "metrics": ["centrality", "betweenness", "clustering"]
                }
            )
            
            assert response.status_code in [200, 404]

    def test_pathway_impact_analysis(self, client, auth_headers):
        """Test POST /api/v1/pathways/impact endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/impact",
                headers=auth_headers,
                json={
                    "gene_expression": {
                        "TP53": 2.5,
                        "BRCA1": -1.8
                    },
                    "pathway_id": "hsa04210"
                }
            )
            
            assert response.status_code in [200, 404]


class TestPathwayVisualizationEndpoints:
    """Test pathway visualization endpoints."""

    def test_get_pathway_diagram(self, client, auth_headers):
        """Test GET /api/v1/pathways/{pathway_id}/diagram endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/pathways/hsa04210/diagram",
                headers=auth_headers,
                params={"format": "svg"}
            )
            
            assert response.status_code in [200, 404]

    def test_generate_pathway_network(self, client, auth_headers):
        """Test POST /api/v1/pathways/{pathway_id}/network endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/hsa04210/network",
                headers=auth_headers,
                json={
                    "layout": "force_directed",
                    "include_compounds": True
                }
            )
            
            assert response.status_code in [200, 404]

    def test_overlay_expression_data(self, client, auth_headers):
        """Test POST /api/v1/pathways/{pathway_id}/overlay endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/hsa04210/overlay",
                headers=auth_headers,
                json={
                    "expression_data": {
                        "TP53": 2.5,
                        "BRCA1": -1.8
                    },
                    "color_scheme": "red_blue"
                }
            )
            
            assert response.status_code in [200, 404]


class TestPathwayComparisonEndpoints:
    """Test pathway comparison endpoints."""

    def test_compare_pathways(self, client, auth_headers):
        """Test POST /api/v1/pathways/compare endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/compare",
                headers=auth_headers,
                json={
                    "pathway_ids": ["hsa04210", "hsa04110"],
                    "comparison_type": "gene_overlap"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "comparison" in data

    def test_find_similar_pathways(self, client, auth_headers):
        """Test GET /api/v1/pathways/{pathway_id}/similar endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/pathways/hsa04210/similar",
                headers=auth_headers,
                params={"limit": 10}
            )
            
            assert response.status_code in [200, 404]


class TestPathwayDatabaseEndpoints:
    """Test pathway database endpoints."""

    def test_list_pathway_databases(self, client, auth_headers):
        """Test GET /api/v1/pathways/databases endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/pathways/databases",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "databases" in data

    def test_get_database_stats(self, client, auth_headers):
        """Test GET /api/v1/pathways/databases/{database}/stats endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/pathways/databases/kegg/stats",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestPathwayAnnotationEndpoints:
    """Test pathway annotation endpoints."""

    def test_annotate_genes_with_pathways(self, client, auth_headers):
        """Test POST /api/v1/pathways/annotate endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/annotate",
                headers=auth_headers,
                json={
                    "genes": ["TP53", "BRCA1", "EGFR"],
                    "databases": ["kegg", "reactome"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "annotations" in data

    def test_get_pathway_annotations(self, client, auth_headers):
        """Test GET /api/v1/pathways/{pathway_id}/annotations endpoint."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/pathways/hsa04210/annotations",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.post(
            "/api/v1/pathways/search",
            json={"query": "apoptosis"}
        )
        assert response.status_code == 401

    def test_invalid_pathway_id(self, client, auth_headers):
        """Test accessing non-existent pathway."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/pathways/invalid-pathway",
                headers=auth_headers
            )
            
            assert response.status_code == 404

    def test_invalid_gene_list(self, client, auth_headers):
        """Test enrichment with invalid gene list."""
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/pathways/enrichment",
                headers=auth_headers,
                json={"gene_list": []}
            )
            
            assert response.status_code in [400, 422]


# Performance tests
class TestPerformance:
    """Test performance of pathway endpoints."""

    def test_enrichment_performance(self, client, auth_headers):
        """Test pathway enrichment performance."""
        import time
        
        with patch("apps.api.routers.pathways.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.post(
                "/api/v1/pathways/enrichment",
                headers=auth_headers,
                json={
                    "gene_list": ["TP53", "BRCA1", "EGFR", "KRAS"],
                    "databases": ["kegg"]
                }
            )
            duration = time.time() - start
            
            assert response.status_code == 200
            assert duration < 5.0  # Should complete in under 5 seconds
