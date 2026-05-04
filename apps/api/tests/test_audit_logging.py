"""
Tests for audit logging functionality.

Verifies:
- Audit logging functions exist and have correct signatures
- Middleware can be instantiated
- Query functions return expected structure
- Export functions generate valid CSV/JSON
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from core.audit import (
    log_audit,
    log_clinical_data_access,
    query_audit_logs,
    get_audit_statistics,
    export_audit_logs,
    cleanup_old_audit_logs,
    detect_audit_anomalies,
)
from middleware.audit_logger import AuditLoggerMiddleware


class TestAuditLoggingFunctions:
    """Test audit logging core functions."""
    
    def test_log_audit_signature(self):
        """Verify log_audit function exists with correct signature."""
        import inspect
        sig = inspect.signature(log_audit)
        params = list(sig.parameters.keys())
        
        assert "session" in params
        assert "user_id" in params
        assert "action" in params
        assert "resource_type" in params
        assert "resource_id" in params
        assert "details" in params
        assert "ip_address" in params
        assert "user_agent" in params
    
    def test_log_clinical_data_access_signature(self):
        """Verify log_clinical_data_access function exists with correct signature."""
        import inspect
        sig = inspect.signature(log_clinical_data_access)
        params = list(sig.parameters.keys())
        
        assert "session" in params
        assert "user_id" in params
        assert "resource_type" in params
        assert "resource_id" in params
        assert "action" in params
        assert "ip_address" in params
        assert "user_agent" in params
    
    def test_query_audit_logs_signature(self):
        """Verify query_audit_logs function exists with correct signature."""
        import inspect
        sig = inspect.signature(query_audit_logs)
        params = list(sig.parameters.keys())
        
        assert "session" in params
        assert "user_id" in params
        assert "resource_type" in params
        assert "limit" in params
        assert "offset" in params
    
    def test_get_audit_statistics_signature(self):
        """Verify get_audit_statistics function exists with correct signature."""
        import inspect
        sig = inspect.signature(get_audit_statistics)
        params = list(sig.parameters.keys())
        
        assert "session" in params
    
    def test_export_audit_logs_signature(self):
        """Verify export_audit_logs function exists with correct signature."""
        import inspect
        sig = inspect.signature(export_audit_logs)
        params = list(sig.parameters.keys())
        
        assert "session" in params
        assert "format" in params
    
    def test_cleanup_old_audit_logs_signature(self):
        """Verify cleanup_old_audit_logs function exists with correct signature."""
        import inspect
        sig = inspect.signature(cleanup_old_audit_logs)
        params = list(sig.parameters.keys())
        
        assert "session" in params
        assert "retention_days" in params
    
    def test_detect_audit_anomalies_signature(self):
        """Verify detect_audit_anomalies function exists with correct signature."""
        import inspect
        sig = inspect.signature(detect_audit_anomalies)
        params = list(sig.parameters.keys())
        
        assert "session" in params


class TestAuditLoggerMiddleware:
    """Test audit logger middleware."""
    
    def test_middleware_instantiation(self):
        """Verify middleware can be instantiated."""
        from fastapi import FastAPI
        
        app = FastAPI()
        middleware = AuditLoggerMiddleware(app)
        
        assert middleware is not None
        assert hasattr(middleware, "dispatch")
    
    def test_middleware_dispatch_signature(self):
        """Verify middleware dispatch method has correct signature."""
        import inspect
        from fastapi import FastAPI
        
        app = FastAPI()
        middleware = AuditLoggerMiddleware(app)
        sig = inspect.signature(middleware.dispatch)
        params = list(sig.parameters.keys())
        
        assert "request" in params
        assert "call_next" in params


class TestQueryFunctions:
    """Test query and statistics functions."""
    
    @pytest.mark.asyncio
    async def test_query_audit_logs_returns_dict(self):
        """Verify query_audit_logs returns expected structure."""
        mock_session = AsyncMock()
        
        # Mock the database query results
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = await query_audit_logs(mock_session, limit=10)
        
        assert isinstance(result, dict)
        assert "logs" in result
        assert "total" in result
        assert "limit" in result
        assert "offset" in result
        assert isinstance(result["logs"], list)
    
    @pytest.mark.asyncio
    async def test_get_audit_statistics_returns_dict(self):
        """Verify get_audit_statistics returns expected structure."""
        mock_session = AsyncMock()
        
        # Mock the database query results
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = await get_audit_statistics(mock_session)
        
        assert isinstance(result, dict)
        assert "total_events" in result
        assert "events_by_action" in result
        assert "events_by_resource_type" in result
        assert "events_by_user" in result
        assert "phi_access_count" in result


class TestExportFunctions:
    """Test export functionality."""
    
    @pytest.mark.asyncio
    async def test_export_audit_logs_csv_format(self):
        """Verify export_audit_logs generates valid CSV."""
        mock_session = AsyncMock()
        
        # Mock query_audit_logs to return sample data
        with patch("core.audit.query_audit_logs") as mock_query:
            mock_query.return_value = {
                "logs": [
                    {
                        "id": "test-id",
                        "user_id": "user-1",
                        "action": "read",
                        "resource_type": "clinical",
                        "resource_id": "res-1",
                        "ip_address": "hash123",
                        "user_agent": "hash456",
                        "created_at": "2024-01-01T00:00:00",
                        "details": {"test": "data"}
                    }
                ],
                "total": 1
            }
            
            result = await export_audit_logs(mock_session, format="csv")
            
            assert isinstance(result, str)
            assert "id,user_id,action" in result
            assert "test-id" in result
            assert "user-1" in result
    
    @pytest.mark.asyncio
    async def test_export_audit_logs_json_format(self):
        """Verify export_audit_logs generates valid JSON."""
        mock_session = AsyncMock()
        
        # Mock query_audit_logs to return sample data
        with patch("core.audit.query_audit_logs") as mock_query:
            mock_query.return_value = {
                "logs": [
                    {
                        "id": "test-id",
                        "user_id": "user-1",
                        "action": "read",
                        "resource_type": "clinical",
                        "resource_id": "res-1",
                        "ip_address": "hash123",
                        "user_agent": "hash456",
                        "created_at": "2024-01-01T00:00:00",
                        "details": {"test": "data"}
                    }
                ],
                "total": 1
            }
            
            result = await export_audit_logs(mock_session, format="json")
            
            assert isinstance(result, str)
            import json
            data = json.loads(result)
            assert "export_date" in data
            assert "total_records" in data
            assert "logs" in data
            assert len(data["logs"]) == 1


class TestAnomalyDetection:
    """Test anomaly detection functionality."""
    
    @pytest.mark.asyncio
    async def test_detect_audit_anomalies_returns_list(self):
        """Verify detect_audit_anomalies returns list of anomalies."""
        mock_session = AsyncMock()
        
        # Mock the database query results
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = await detect_audit_anomalies(mock_session)
        
        assert isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
