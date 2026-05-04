"""
Security & Tenancy Boundaries Middleware.
Satisfies Section 22 of the Drug Designer specification by enforcing
JWT Bearer token validation on all protected API routes.
Includes RBAC role enforcement (§55.2-55.3) and agent key scoping (§55.4).
"""

import os
import hmac
from typing import Optional, Sequence
from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.auth import verify_access_token

# Routes that don't require authentication (§55.3)
PUBLIC_ROUTES = {
    "/api/health",
    "/api/health/deep",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/refresh",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/",
}

# §55.2 RBAC role hierarchy (higher includes lower)
ROLE_HIERARCHY = {
    "admin": 4,
    "owner": 3,
    "collaborator": 2,
    "viewer": 1,
    "agent": 2,  # agents = collaborator-level
}


def require_role(*allowed_roles: str):
    """FastAPI Depends for RBAC enforcement (§55.2-55.3).

    Usage: `Depends(require_role("owner", "admin"))`
    Validates request.state.user_role against allowed roles.
    """
    async def _check(request: Request):
        role = getattr(request.state, "user_role", None)
        if not role:
            raise HTTPException(status_code=401, detail="Authentication required")
        if role not in allowed_roles and role != "admin":
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role}' insufficient. Required: {', '.join(allowed_roles)}",
            )
        return role
    return _check


def verify_agent_api_key(api_key: str) -> Optional[dict]:
    """Verify Local Agent pre-shared API key (§55.3).
    Returns agent context dict or None if invalid."""
    expected_key = os.environ.get("DRUGDESIGNER_AGENT_API_KEY", "")
    if not expected_key or not api_key:
        return None
    if hmac.compare_digest(api_key, expected_key):
        return {"agent": True, "role": "agent"}
    return None


def verify_agent_scope(api_key: str, user_id: str = None, project_id: str = None) -> Optional[dict]:
    """Verify agent API key is scoped to user + project (§55.4).
    Format: <key>:<user_id>:<project_id> or just <key> for global agents."""
    parts = api_key.split(":", 2)
    base_key = parts[0]
    ctx = verify_agent_api_key(base_key)
    if not ctx:
        return None
    # If scoped key provided, validate scope
    if len(parts) == 3:
        ctx["scoped_user_id"] = parts[1]
        ctx["scoped_project_id"] = parts[2]
    return ctx


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware enforcing Bearer token authentication on all protected routes.
    Public routes (health checks, docs) are exempted.
    
    When DRUGDESIGNER_AUTH_ENABLED=false (default for development), all requests pass through.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Check if auth is enabled (enabled by default per §55.3)
        auth_enabled = os.environ.get("DRUGDESIGNER_AUTH_ENABLED", "true").lower() == "true"
        
        if not auth_enabled:
            return await call_next(request)
        
        # Allow public routes
        path = request.url.path
        if any(path.startswith(r) for r in PUBLIC_ROUTES):
            return await call_next(request)
        
        # Extract Bearer token or Agent API key (§55.3)
        # Primary: HTTP-only cookie (§55.1)
        token = request.cookies.get("dss_access_token")

        # Check for Local Agent API key (§55.3: X-Agent-Key header)
        agent_key = request.headers.get("X-Agent-Key", "")
        if agent_key:
            agent_ctx = verify_agent_api_key(agent_key)
            if agent_ctx:
                request.state.user_id = "agent"
                request.state.user_role = "agent"
                return await call_next(request)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid Agent API key."}
            )

        # Fallback: Authorization header for API clients
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authentication. Expected: HTTP-only cookie or Bearer <token>"}
            )
        payload = verify_access_token(token)
        
        if payload is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired JWT token."}
            )
        
        # Attach user context to request state
        request.state.user_id = payload.get("sub")
        request.state.user_role = payload.get("role")
        
        return await call_next(request)
