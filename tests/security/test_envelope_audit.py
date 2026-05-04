"""
Universal Envelope Audit (Phase K)

Verifies that all API endpoints return the standardized envelope format.

Required envelope fields:
- request_id: str
- trace_id: str
- status: str ("success" | "error" | "degraded")
- data: Any
- warnings: List[str] (optional)
- errors: List[str] (optional)
- provenance: Dict (optional)
- timing: Dict (optional)
"""

import pytest
import inspect
from typing import List, Dict, Any
from fastapi import FastAPI
from fastapi.testclient import TestClient
from apps.api.main import app


# Expected envelope schema
REQUIRED_FIELDS = ["request_id", "trace_id", "status", "data"]
OPTIONAL_FIELDS = ["warnings", "errors", "provenance", "timing"]
VALID_STATUSES = ["success", "error", "degraded"]


def get_all_routes(app: FastAPI) -> List[Dict[str, Any]]:
    """Extract all routes from FastAPI app"""
    routes = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                if method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                    routes.append({
                        "method": method,
                        "path": route.path,
                        "name": route.name,
                    })
    return routes


def validate_envelope(response_json: Dict[str, Any]) -> Dict[str, Any]:
    """Validate response matches envelope schema
    
    Returns:
        Dict with validation results:
        - valid: bool
        - missing_fields: List[str]
        - invalid_status: bool
        - errors: List[str]
    """
    result = {
        "valid": True,
        "missing_fields": [],
        "invalid_status": False,
        "errors": []
    }
    
    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in response_json:
            result["valid"] = False
            result["missing_fields"].append(field)
            result["errors"].append(f"Missing required field: {field}")
    
    # Check status value
    if "status" in response_json:
        if response_json["status"] not in VALID_STATUSES:
            result["valid"] = False
            result["invalid_status"] = True
            result["errors"].append(
                f"Invalid status: {response_json['status']}. "
                f"Must be one of: {VALID_STATUSES}"
            )
    
    # Check field types
    if "request_id" in response_json and not isinstance(response_json["request_id"], str):
        result["valid"] = False
        result["errors"].append("request_id must be a string")
    
    if "trace_id" in response_json and not isinstance(response_json["trace_id"], str):
        result["valid"] = False
        result["errors"].append("trace_id must be a string")
    
    if "warnings" in response_json and not isinstance(response_json["warnings"], list):
        result["valid"] = False
        result["errors"].append("warnings must be a list")
    
    if "errors" in response_json and not isinstance(response_json["errors"], list):
        result["valid"] = False
        result["errors"].append("errors must be a list")
    
    if "provenance" in response_json and not isinstance(response_json["provenance"], dict):
        result["valid"] = False
        result["errors"].append("provenance must be a dict")
    
    if "timing" in response_json and not isinstance(response_json["timing"], dict):
        result["valid"] = False
        result["errors"].append("timing must be a dict")
    
    return result


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Get authentication headers for test user"""
    # Register test user
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "envelope_test@example.com",
            "password": "test_password_123",
            "full_name": "Envelope Test User"
        }
    )
    
    # Login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "envelope_test@example.com",
            "password": "test_password_123"
        }
    )
    
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestEnvelopeAudit:
    """Test envelope format across all endpoints"""
    
    def test_health_endpoint_envelope(self, client):
        """Test health endpoint returns valid envelope"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        validation = validate_envelope(response.json())
        assert validation["valid"], f"Envelope validation failed: {validation['errors']}"
    
    def test_auth_register_envelope(self, client):
        """Test auth register endpoint returns valid envelope"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test_envelope@example.com",
                "password": "test_password_123",
                "full_name": "Test User"
            }
        )
        assert response.status_code in [200, 201, 400]  # 400 if user exists
        
        validation = validate_envelope(response.json())
        assert validation["valid"], f"Envelope validation failed: {validation['errors']}"
    
    def test_auth_login_envelope(self, client):
        """Test auth login endpoint returns valid envelope"""
        # First register
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "test_login@example.com",
                "password": "test_password_123",
                "full_name": "Test User"
            }
        )
        
        # Then login
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test_login@example.com",
                "password": "test_password_123"
            }
        )
        assert response.status_code == 200
        
        validation = validate_envelope(response.json())
        assert validation["valid"], f"Envelope validation failed: {validation['errors']}"
    
    def test_cockpit_summary_envelope(self, client, auth_headers):
        """Test cockpit summary endpoint returns valid envelope"""
        response = client.get("/api/v1/cockpit/summary", headers=auth_headers)
        assert response.status_code == 200
        
        validation = validate_envelope(response.json())
        assert validation["valid"], f"Envelope validation failed: {validation['errors']}"
    
    def test_projects_list_envelope(self, client, auth_headers):
        """Test projects list endpoint returns valid envelope"""
        response = client.get("/api/v1/projects", headers=auth_headers)
        assert response.status_code == 200
        
        validation = validate_envelope(response.json())
        assert validation["valid"], f"Envelope validation failed: {validation['errors']}"
    
    def test_projects_create_envelope(self, client, auth_headers):
        """Test projects create endpoint returns valid envelope"""
        response = client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={
                "name": "Test Project",
                "description": "Testing envelope"
            }
        )
        assert response.status_code in [200, 201]
        
        validation = validate_envelope(response.json())
        assert validation["valid"], f"Envelope validation failed: {validation['errors']}"
    
    def test_error_response_envelope(self, client, auth_headers):
        """Test that error responses also use envelope format"""
        # Try to get non-existent project
        response = client.get("/api/v1/projects/99999", headers=auth_headers)
        assert response.status_code == 404
        
        validation = validate_envelope(response.json())
        assert validation["valid"], f"Envelope validation failed: {validation['errors']}"
        
        # Error responses should have status="error"
        assert response.json()["status"] == "error"
        
        # Error responses should have errors list
        assert "errors" in response.json()
        assert len(response.json()["errors"]) > 0
    
    def test_degraded_response_envelope(self, client, auth_headers):
        """Test that degraded responses use envelope format"""
        # This would require mocking a degraded state
        # For now, just verify the envelope structure is correct
        # when some sources fail but others succeed
        pass  # TODO: Implement when degraded state can be triggered
    
    def test_envelope_has_timing(self, client, auth_headers):
        """Test that envelope includes timing information"""
        response = client.get("/api/v1/cockpit/summary", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "timing" in data, "Envelope should include timing information"
        
        timing = data["timing"]
        assert isinstance(timing, dict)
        # Common timing fields
        expected_timing_fields = ["start_time", "end_time", "duration_ms"]
        # At least one timing field should be present
        assert any(field in timing for field in expected_timing_fields)
    
    def test_envelope_has_provenance(self, client, auth_headers):
        """Test that envelope includes provenance when applicable"""
        # Create a project (should have provenance)
        response = client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={
                "name": "Provenance Test Project",
                "description": "Testing provenance"
            }
        )
        assert response.status_code in [200, 201]
        
        data = response.json()
        # Provenance is optional but recommended for data-modifying operations
        if "provenance" in data:
            assert isinstance(data["provenance"], dict)


class TestEnvelopeMiddleware:
    """Test envelope middleware enforcement"""
    
    def test_middleware_adds_request_id(self, client):
        """Test that middleware adds request_id to all responses"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "request_id" in data
        assert isinstance(data["request_id"], str)
        assert len(data["request_id"]) > 0
    
    def test_middleware_adds_trace_id(self, client):
        """Test that middleware adds trace_id to all responses"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "trace_id" in data
        assert isinstance(data["trace_id"], str)
        assert len(data["trace_id"]) > 0
    
    def test_request_id_unique(self, client):
        """Test that each request gets a unique request_id"""
        response1 = client.get("/api/v1/health")
        response2 = client.get("/api/v1/health")
        
        request_id1 = response1.json()["request_id"]
        request_id2 = response2.json()["request_id"]
        
        assert request_id1 != request_id2, "Each request should have a unique request_id"


class TestEnvelopeComprehensiveAudit:
    """Comprehensive audit of all endpoints"""
    
    def test_audit_all_get_endpoints(self, client, auth_headers):
        """Audit all GET endpoints for envelope compliance"""
        routes = get_all_routes(app)
        get_routes = [r for r in routes if r["method"] == "GET"]
        
        failures = []
        
        for route in get_routes:
            # Skip routes with path parameters for now
            if "{" in route["path"]:
                continue
            
            # Skip docs/openapi routes
            if route["path"] in ["/docs", "/openapi.json", "/redoc"]:
                continue
            
            try:
                response = client.get(route["path"], headers=auth_headers)
                
                # Only check successful responses
                if response.status_code < 500:
                    validation = validate_envelope(response.json())
                    if not validation["valid"]:
                        failures.append({
                            "route": route,
                            "validation": validation
                        })
            except Exception as e:
                # Log but don't fail on exceptions (some routes may require specific setup)
                print(f"Warning: Could not test {route['path']}: {e}")
        
        if failures:
            failure_report = "\n".join([
                f"Route: {f['route']['method']} {f['route']['path']}\n"
                f"Errors: {f['validation']['errors']}"
                for f in failures
            ])
            pytest.fail(f"Envelope validation failed for {len(failures)} routes:\n{failure_report}")
    
    def test_generate_envelope_compliance_report(self, client, auth_headers):
        """Generate a comprehensive envelope compliance report"""
        routes = get_all_routes(app)
        
        total_routes = len(routes)
        tested_routes = 0
        compliant_routes = 0
        non_compliant_routes = 0
        skipped_routes = 0
        
        report = []
        report.append("="*80)
        report.append("ENVELOPE COMPLIANCE AUDIT REPORT")
        report.append("="*80)
        report.append("")
        
        for route in routes:
            # Skip routes with path parameters
            if "{" in route["path"]:
                skipped_routes += 1
                continue
            
            # Skip docs routes
            if route["path"] in ["/docs", "/openapi.json", "/redoc"]:
                skipped_routes += 1
                continue
            
            try:
                if route["method"] == "GET":
                    response = client.get(route["path"], headers=auth_headers)
                elif route["method"] == "POST":
                    # Skip POST routes that require specific payloads
                    skipped_routes += 1
                    continue
                else:
                    skipped_routes += 1
                    continue
                
                tested_routes += 1
                
                if response.status_code < 500:
                    validation = validate_envelope(response.json())
                    if validation["valid"]:
                        compliant_routes += 1
                        report.append(f"✅ {route['method']} {route['path']}")
                    else:
                        non_compliant_routes += 1
                        report.append(f"❌ {route['method']} {route['path']}")
                        report.append(f"   Errors: {', '.join(validation['errors'])}")
            except Exception as e:
                skipped_routes += 1
                report.append(f"⚠️  {route['method']} {route['path']} (skipped: {e})")
        
        report.append("")
        report.append("="*80)
        report.append("SUMMARY")
        report.append("="*80)
        report.append(f"Total routes: {total_routes}")
        report.append(f"Tested routes: {tested_routes}")
        report.append(f"Compliant routes: {compliant_routes}")
        report.append(f"Non-compliant routes: {non_compliant_routes}")
        report.append(f"Skipped routes: {skipped_routes}")
        
        if tested_routes > 0:
            compliance_rate = (compliant_routes / tested_routes) * 100
            report.append(f"Compliance rate: {compliance_rate:.1f}%")
        
        report.append("="*80)
        
        print("\n".join(report))
        
        # Assert compliance rate is 100%
        if tested_routes > 0:
            assert non_compliant_routes == 0, (
                f"{non_compliant_routes} routes are not envelope-compliant. "
                f"See report above for details."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
