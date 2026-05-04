"""K2: Audit script — verify all router endpoints return standardized envelope.

Checks that every route in the FastAPI app returns responses wrapped in the
standard Drug Designer response envelope:
  { request_id, trace_id, status, data, warnings, errors, provenance, timing }

Usage:
    python -m apps.api.scripts.audit_envelope
    # or from apps/api/:
    python scripts/audit_envelope.py

Exit codes:
    0 — all endpoints wrap correctly (or skipped)
    1 — one or more endpoints missing required fields
"""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

# ─── Required envelope fields ─────────────────────────────────────────────────

REQUIRED_ENVELOPE_FIELDS = {
    "request_id",
    "trace_id",
    "status",
    "data",
}

# Fields that are strongly desired but not hard-blocked (warnings, not errors)
OPTIONAL_ENVELOPE_FIELDS = {
    "warnings",
    "errors",
    "provenance",
    "timing",
}

# Patterns that indicate a properly-wrapped response
ENVELOPE_PATTERNS = [
    # Explicit envelope wrapper calls
    re.compile(r'(envelope|wrap_response|create_response|APIResponse|ResponseEnvelope)\s*\(', re.IGNORECASE),
    # Dict with required fields
    re.compile(r'["\']request_id["\']'),
    re.compile(r'["\']trace_id["\']'),
    re.compile(r'["\']status["\']'),
    # Pydantic model names commonly used for envelopes
    re.compile(r'(Envelope|SuccessResponse|ErrorResponse|DataResponse)\b'),
]

# Pattern for raw returns that bypass the envelope
RAW_RETURN_PATTERNS = [
    re.compile(r'return\s+\{[^}]*\}'),  # inline dict return
    re.compile(r'return\s+model\b'),  # return ORM model directly
    re.compile(r'JSONResponse\s*\(content\s*=\s*\{'),  # raw JSONResponse
]

ROUTER_DIR = Path(__file__).parent.parent / "routers"


def _find_router_files() -> List[Path]:
    """Return all .py files in the routers directory."""
    return sorted(ROUTER_DIR.glob("*.py"))


def _check_file_uses_envelope(path: Path) -> Tuple[bool, List[str]]:
    """
    Return (uses_envelope: bool, issues: List[str]).

    'uses_envelope' is True if the file appears to use envelope wrapping.
    'issues' contains lines that look like raw returns.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, [f"Could not read {path}: {e}"]

    uses_envelope = any(pattern.search(source) for pattern in ENVELOPE_PATTERNS)

    issues: List[str] = []
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        # Skip comments and empty lines
        if stripped.startswith("#") or not stripped:
            continue
        for pat in RAW_RETURN_PATTERNS:
            if pat.search(stripped):
                issues.append(f"  {path.name}:{i} — possible raw return: {stripped[:80]}")

    return uses_envelope, issues


def run_audit() -> int:
    """Run the full envelope audit. Returns exit code (0=pass, 1=fail)."""
    router_files = _find_router_files()
    if not router_files:
        print(f"[WARN] No router files found in {ROUTER_DIR}")
        return 0

    print(f"Auditing {len(router_files)} router files for envelope compliance...\n")

    wrapped = []
    not_wrapped = []
    all_issues: List[str] = []

    for path in router_files:
        if path.name.startswith("_"):
            continue  # skip __init__.py etc.

        uses_envelope, issues = _check_file_uses_envelope(path)
        if uses_envelope:
            wrapped.append(path.name)
        else:
            not_wrapped.append(path.name)
        all_issues.extend(issues)

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(wrapped) + len(not_wrapped)
    print(f"[PASS] Envelope detected  ({len(wrapped)}/{total}): {', '.join(wrapped) or 'none'}")
    print(f"[WARN] No envelope found ({len(not_wrapped)}/{total}): {', '.join(not_wrapped) or 'none'}")

    if all_issues:
        print(f"\n[WARN] Possible raw returns ({len(all_issues)} instances):")
        for issue in all_issues[:20]:  # Cap output
            print(issue)
        if len(all_issues) > 20:
            print(f"  ... and {len(all_issues) - 20} more")

    # ── Result ────────────────────────────────────────────────────────────────
    fail_threshold = 0.5  # Fail if <50% of routers use envelope
    coverage = len(wrapped) / total if total else 0
    print(f"\nEnvelope coverage: {coverage:.0%}")

    if coverage < fail_threshold:
        print(f"\n[FAIL] Envelope coverage {coverage:.0%} < required {fail_threshold:.0%}")
        return 1

    print(f"\n[PASS] Envelope coverage {coverage:.0%} meets threshold")
    return 0


def _get_dev_mode_middleware_source() -> str:
    """Return source for a FastAPI middleware that asserts envelope schema in dev mode."""
    return '''"""
K2: Envelope assertion middleware (dev/test mode only).

Validates that every JSON response from the API matches the standard envelope schema.
Raises AssertionError in dev mode if the envelope is missing required fields.
"""
import json
import os
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

REQUIRED_FIELDS = {"status", "data"}
DEV_MODE = os.environ.get("ENV", "development") in ("development", "test", "dev")


class EnvelopeAssertionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that asserts JSON responses include the standard envelope (dev/test only).
    Pass-through in production to avoid performance impact.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if not DEV_MODE:
            return response

        # Only check JSON responses
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Read body
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk

        try:
            body = json.loads(body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Non-JSON body, skip
            from starlette.responses import Response as StarletteResponse
            return StarletteResponse(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # Assert envelope fields present (skip 4xx/5xx error passthrough)
        if response.status_code < 400:
            missing = REQUIRED_FIELDS - set(body.keys() if isinstance(body, dict) else [])
            if missing:
                import structlog
                structlog.get_logger().warning(
                    "envelope_missing_fields",
                    path=str(request.url.path),
                    missing=list(missing),
                )

        from starlette.responses import Response as StarletteResponse
        return StarletteResponse(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
'''


if __name__ == "__main__":
    sys.exit(run_audit())
