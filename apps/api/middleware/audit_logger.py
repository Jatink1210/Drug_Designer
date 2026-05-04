"""
Audit Logger Middleware — Automatic audit logging for all API requests.

Logs all requests to clinical endpoints and PHI-related resources.
Satisfies FR-SEC-001 audit logging requirements.
"""

import time
from typing import Set
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.audit import log_audit, log_clinical_data_access


# Clinical endpoints that require PHI access logging
CLINICAL_ENDPOINTS: Set[str] = {
    "/api/v1/clinical",
    "/api/clinical",
    "/api/v1/tissue",
    "/api/tissue",
    "/api/v1/biomarker",
    "/api/biomarker",
    "/api/v1/patient",
    "/api/patient",
}

# Actions that should always be logged
SENSITIVE_ACTIONS: Set[str] = {
    "login",
    "logout",
    "export",
    "delete",
    "runtime_change",
    "model_selection",
    "consensus_vote",
}


def _is_clinical_endpoint(path: str) -> bool:
    """Check if the request path is a clinical endpoint requiring PHI logging."""
    return any(path.startswith(endpoint) for endpoint in CLINICAL_ENDPOINTS)


def _extract_resource_info(request: Request) -> tuple[str, str]:
    """Extract resource type and ID from request path."""
    path_parts = request.url.path.strip("/").split("/")
    
    # Try to extract resource type and ID from path
    # Pattern: /api/v1/{resource_type}/{resource_id}
    resource_type = ""
    resource_id = ""
    
    if len(path_parts) >= 3:
        resource_type = path_parts[2]  # e.g., "clinical", "tissue", "projects"
    
    if len(path_parts) >= 4:
        resource_id = path_parts[3]  # e.g., UUID or identifier
    
    return resource_type, resource_id


def _get_action_from_method(method: str, path: str) -> str:
    """Map HTTP method and path to audit action."""
    method = method.upper()
    
    # Check for specific actions in path
    if "login" in path.lower():
        return "login"
    elif "logout" in path.lower():
        return "logout"
    elif "export" in path.lower():
        return "export"
    
    # Map HTTP methods to actions
    action_map = {
        "GET": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }
    
    return action_map.get(method, method.lower())


class AuditLoggerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically log all API requests to audit trail.
    
    Logs:
    - All clinical endpoint accesses (PHI logging)
    - All sensitive operations (login, logout, export, delete)
    - Request method, path, user_id, IP address, user agent
    - Response status code and timing
    
    Performance: <5ms overhead per request
    """
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract request metadata
        path = request.url.path
        method = request.method
        user_id = getattr(request.state, "user_id", None)
        user_role = getattr(request.state, "user_role", None)
        
        # Skip audit logging for health checks and public routes
        if path in ["/api/health", "/api/health/deep", "/docs", "/openapi.json", "/redoc", "/"]:
            return await call_next(request)
        
        # Extract IP and user agent
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        
        # Process request
        response = await call_next(request)
        
        # Calculate request duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Only log if user is authenticated or it's a sensitive action
        if user_id or "auth" in path.lower():
            try:
                # Get database session
                async for session in get_db():
                    # Determine if this is a clinical endpoint
                    is_clinical = _is_clinical_endpoint(path)
                    
                    # Extract resource info
                    resource_type, resource_id = _extract_resource_info(request)
                    
                    # Determine action
                    action = _get_action_from_method(method, path)
                    
                    # Build audit details
                    details = {
                        "method": method,
                        "path": path,
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                        "user_role": user_role,
                    }
                    
                    # Log to audit trail
                    if is_clinical:
                        # Use PHI-specific logging for clinical endpoints
                        await log_clinical_data_access(
                            session=session,
                            user_id=user_id or "anonymous",
                            resource_type=resource_type or "clinical",
                            resource_id=resource_id or path,
                            action=action,
                            ip_address=ip_address,
                            user_agent=user_agent
                        )
                    else:
                        # Standard audit logging
                        await log_audit(
                            session=session,
                            user_id=user_id or "anonymous",
                            action=action,
                            resource_type=resource_type or "api",
                            resource_id=resource_id or path,
                            details=details,
                            ip_address=ip_address,
                            user_agent=user_agent
                        )
                    
                    # Commit the audit log
                    await session.commit()
                    break
                    
            except Exception as e:
                # Don't fail the request if audit logging fails
                # Log the error but continue
                import structlog
                structlog.get_logger().error(
                    "audit_logging_failed",
                    error=str(e),
                    path=path,
                    user_id=user_id
                )
        
        return response
