"""K3: Structured log enrichment middleware.

Auto-injects request_id and trace_id into the structlog context for every request,
so all log events within a request automatically carry these correlation IDs.

Also enriches:
- user_id (if authenticated)
- path and method
- client IP (hashed for privacy)

Usage (add to FastAPI app in main.py):
    from middleware.log_enrichment import LogEnrichmentMiddleware
    app.add_middleware(LogEnrichmentMiddleware)
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Callable, Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger()

# Header names for trace propagation
REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"


def _generate_request_id() -> str:
    """Generate a new UUID4 request ID."""
    return str(uuid.uuid4())


def _hash_ip(ip: Optional[str]) -> Optional[str]:
    """One-way hash of client IP for privacy (§67)."""
    if not ip:
        return None
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


class LogEnrichmentMiddleware(BaseHTTPMiddleware):
    """
    K3: Middleware that binds request_id and trace_id to structlog context.

    Every log event emitted during a request will automatically carry:
    - request_id: UUID for this specific request
    - trace_id: Propagated from X-Trace-ID header or same as request_id
    - path: URL path
    - method: HTTP method
    - client_ip_hash: Hashed client IP for correlation without storing raw IPs
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or propagate request_id
        request_id = request.headers.get(REQUEST_ID_HEADER) or _generate_request_id()
        trace_id = request.headers.get(TRACE_ID_HEADER) or request_id

        # Hash client IP for privacy
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else None)
        )
        client_ip_hash = _hash_ip(client_ip)

        # Bind to structlog context for the duration of this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            path=request.url.path,
            method=request.method,
            client_ip_hash=client_ip_hash,
        )

        # Store on request.state so routers can access without re-parsing headers
        request.state.request_id = request_id
        request.state.trace_id = trace_id

        # Process request
        response = await call_next(request)

        # Propagate IDs in response headers for client-side correlation
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACE_ID_HEADER] = trace_id

        # Clear context after request completes
        structlog.contextvars.clear_contextvars()

        return response


def bind_run_context(run_id: str, job_id: Optional[str] = None) -> None:
    """
    Bind run_id and optional job_id to structlog context.

    Call this from worker tasks / long-running jobs to ensure all logs
    within the job carry run/job identifiers.

    Example:
        from middleware.log_enrichment import bind_run_context
        bind_run_context(run_id="run-abc123", job_id="job-xyz")
        logger.info("job_started")  # → includes run_id + job_id
    """
    ctx: dict = {"run_id": run_id}
    if job_id:
        ctx["job_id"] = job_id
    structlog.contextvars.bind_contextvars(**ctx)


def get_current_request_id() -> Optional[str]:
    """Return the current request_id from structlog context, if bound."""
    try:
        ctx = structlog.contextvars.get_contextvars()
        return ctx.get("request_id")
    except Exception:
        return None


def get_current_trace_id() -> Optional[str]:
    """Return the current trace_id from structlog context, if bound."""
    try:
        ctx = structlog.contextvars.get_contextvars()
        return ctx.get("trace_id")
    except Exception:
        return None
