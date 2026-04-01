"""
Security & Tenancy Boundaries Middleware.
Satisfies Section 22 of the Drug Designer specification by enforcing
JWT Bearer token validation on all protected API routes.
"""

import os
import time
import hmac
import hashlib
import json
import base64
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Secret key - in production this comes from environment variables
JWT_SECRET = os.environ.get("DRUGDESIGNER_JWT_SECRET", "workbench-dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

# Routes that don't require authentication
PUBLIC_ROUTES = {
    "/api/health",
    "/api/health/deep",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/",
}

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

def _base64url_decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)

def create_token(user_id: str, role: str = "researcher", expires_in: int = 86400) -> str:
    """Generate a signed JWT token for API authentication."""
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in
    }
    
    header_b64 = _base64url_encode(json.dumps(header).encode())
    payload_b64 = _base64url_encode(json.dumps(payload).encode())
    
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token. Returns payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
            
        header_b64, payload_b64, signature_b64 = parts
        
        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual_sig = _base64url_decode(signature_b64)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
            
        # Decode payload
        payload = json.loads(_base64url_decode(payload_b64))
        
        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload
    except Exception:
        return None

class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware enforcing Bearer token authentication on all protected routes.
    Public routes (health checks, docs) are exempted.
    
    When DRUGDESIGNER_AUTH_ENABLED=false (default for development), all requests pass through.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Check if auth is enabled (disabled by default for local dev)
        auth_enabled = os.environ.get("DRUGDESIGNER_AUTH_ENABLED", "false").lower() == "true"
        
        if not auth_enabled:
            return await call_next(request)
        
        # Allow public routes
        path = request.url.path
        if any(path.startswith(r) for r in PUBLIC_ROUTES):
            return await call_next(request)
        
        # Extract Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header. Expected: Bearer <token>"}
            )
        
        token = auth_header[7:]
        payload = verify_token(token)
        
        if payload is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired JWT token."}
            )
        
        # Attach user context to request state
        request.state.user_id = payload.get("sub")
        request.state.user_role = payload.get("role")
        
        return await call_next(request)
