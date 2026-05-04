"""
User-facing Rate Limit Middleware (§68.3).

Limits:
    - Authenticated users: 120 requests / minute
    - Unauthenticated users: 10 requests / minute

Uses in-memory sliding window per IP/user. In production with replicas,
swap to Redis-backed counters.
"""

import os
import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


def _env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return default


# §68.3 Rate limits
AUTHENTICATED_LIMIT = _env_int("DRUGDESIGNER_RATE_LIMIT_AUTHENTICATED", 120)   # per minute (§17.3)
UNAUTHENTICATED_LIMIT = _env_int("DRUGDESIGNER_RATE_LIMIT_UNAUTHENTICATED", 10)  # per minute (§17.3)
WINDOW_SECONDS = _env_int("DRUGDESIGNER_RATE_LIMIT_WINDOW_SECONDS", 60)


class _SlidingWindow:
    """Simple sliding window counter."""
    __slots__ = ("timestamps",)

    def __init__(self):
        self.timestamps: list[float] = []

    def hit(self, now: float, limit: int) -> bool:
        cutoff = now - WINDOW_SECONDS
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        if len(self.timestamps) >= limit:
            return False
        self.timestamps.append(now)
        return True

    def remaining(self, now: float, limit: int) -> int:
        cutoff = now - WINDOW_SECONDS
        active = sum(1 for t in self.timestamps if t > cutoff)
        return max(0, limit - active)


# Per-key sliding windows
_windows: dict[str, _SlidingWindow] = defaultdict(_SlidingWindow)


# Routes exempt from rate limiting (health checks, auth, docs)
_RATE_LIMIT_EXEMPT = (
    "/api/health",
    "/api/v1/auth/",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-user / per-IP request rate limits (§68.3)."""

    async def dispatch(self, request: Request, call_next):
        # Exempt public/health routes from rate limiting
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _RATE_LIMIT_EXEMPT):
            return await call_next(request)

        now = time.time()

        # Determine identity and limit
        auth_enabled = os.environ.get("DRUGDESIGNER_AUTH_ENABLED", "true").lower() == "true"
        user_id = getattr(request.state, "user_id", None) if hasattr(request, "state") else None
        if not auth_enabled:
            key = "user:local_desktop"
            limit = AUTHENTICATED_LIMIT
        elif user_id:
            key = f"user:{user_id}"
            limit = AUTHENTICATED_LIMIT
        else:
            client_ip = request.client.host if request.client else "unknown"
            key = f"ip:{client_ip}"
            limit = UNAUTHENTICATED_LIMIT

        window = _windows[key]
        if not window.hit(now, limit):
            remaining = 0
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(WINDOW_SECONDS),
                },
            )

        response = await call_next(request)
        remaining = window.remaining(now, limit)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
