"""Role-Based Access Control (§55.2, §55.3).

Four roles with hierarchy: Admin > Owner > Collaborator > Viewer.

Usage examples
--------------
# Minimum role on a route:
@router.delete("/projects/{project_id}", dependencies=[Depends(require_role(Role.OWNER))])

# Operation-level permission check inside a handler:
await verify_project_access(user, project_id, min_role=Role.COLLABORATOR)

# Local Agent pre-shared key validation:
agent = verify_agent_key(request)
"""

import os
import secrets
from enum import Enum
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
import structlog

log = structlog.get_logger()

# Lazy import to avoid circular dependency — routers.auth may not be importable
# at module load time in all code paths.
try:
    from routers.auth import get_current_user  # type: ignore[import]
except ImportError:  # pragma: no cover
    get_current_user = None  # type: ignore[assignment]


# ── Role taxonomy (§55.2) ──────────────────────────────────────────────────

class Role(str, Enum):
    VIEWER = "viewer"
    COLLABORATOR = "collaborator"
    OWNER = "owner"
    ADMIN = "admin"


ROLE_HIERARCHY: dict[Role, int] = {
    Role.ADMIN: 4,
    Role.OWNER: 3,
    Role.COLLABORATOR: 2,
    Role.VIEWER: 1,
}

# Map operation keywords → minimum required role (§55.2 permissions matrix)
OPERATION_ROLE_MAP: dict[str, Role] = {
    # Viewer-level
    "read": Role.VIEWER,
    "list": Role.VIEWER,
    "export_view": Role.VIEWER,
    # Collaborator-level
    "write": Role.COLLABORATOR,
    "run_workflow": Role.COLLABORATOR,
    "generate_dossier": Role.COLLABORATOR,
    # Owner-level
    "delete_project": Role.OWNER,
    "invite_user": Role.OWNER,
    "change_runtime": Role.OWNER,
    # Admin-level
    "manage_users": Role.ADMIN,
    "view_system_health": Role.ADMIN,
    "configure_global_api_keys": Role.ADMIN,
}


# ── Dependency: minimum role ──────────────────────────────────────────────

def require_role(minimum: Role):
    """FastAPI dependency — enforces a minimum role level.

    Returns the authenticated user if their role meets the requirement.
    Raises HTTP 403 otherwise.
    """
    async def _checker(request: Request, user=Depends(get_current_user)):
        _assert_role(user, minimum)
        return user
    return _checker


def require_operation(operation: str):
    """FastAPI dependency — enforces the role required for a named operation.

    Example::

        @router.delete("/projects/{id}", dependencies=[Depends(require_operation("delete_project"))])
    """
    minimum = OPERATION_ROLE_MAP.get(operation, Role.COLLABORATOR)

    async def _checker(request: Request, user=Depends(get_current_user)):
        _assert_role(user, minimum)
        return user
    return _checker


def _assert_role(user, minimum: Role) -> None:
    """Raise HTTP 403 if user's role is below *minimum*."""
    user_role_str = getattr(user, "role", "collaborator")
    try:
        user_role = Role(user_role_str)
    except ValueError:
        user_role = Role.COLLABORATOR
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY[minimum]
    if user_level < required_level:
        log.warning(
            "rbac_denied",
            user_id=getattr(user, "id", "unknown"),
            user_role=user_role_str,
            required_role=minimum.value,
        )
        raise HTTPException(
            status_code=403,
            detail=f"Requires '{minimum.value}' role or higher. Current role: '{user_role_str}'.",
        )


# ── Project-level access helper (§55.3) ──────────────────────────────────

async def verify_project_access(
    user,
    project_id: str,
    min_role: Role = Role.VIEWER,
    db=None,
) -> None:
    """Verify the user has at least *min_role* on *project_id*.

    Platform Admins bypass project membership checks.
    Raises HTTP 403/404 on failure.

    Parameters
    ----------
    user : authenticated user object (must have .id and .role)
    project_id : UUID string of the project
    min_role : minimum role required on this project
    db : AsyncSession — pass from the router; if None, only platform-role check runs
    """
    # Admins can access any project
    user_role_str = getattr(user, "role", "collaborator")
    if user_role_str == Role.ADMIN.value:
        return

    # Without a DB session we can only do platform-role enforcement
    if db is None:
        _assert_role(user, min_role)
        return

    # Check project_members table
    from sqlalchemy import select, text as sa_text
    try:
        row = await db.execute(
            sa_text(
                "SELECT role FROM project_members WHERE project_id = :pid AND user_id = :uid LIMIT 1"
            ),
            {"pid": project_id, "uid": str(getattr(user, "id", ""))},
        )
        membership = row.fetchone()
    except Exception as exc:
        log.error("rbac_db_error", error=str(exc))
        raise HTTPException(status_code=403, detail="Unable to verify project access.")

    # Also accept if user is the project owner
    if membership is None:
        # Check if user is owner
        try:
            owner_row = await db.execute(
                sa_text("SELECT id FROM projects WHERE id = :pid AND owner_id = :uid LIMIT 1"),
                {"pid": project_id, "uid": str(getattr(user, "id", ""))},
            )
            if owner_row.fetchone() is None:
                raise HTTPException(status_code=404, detail="Project not found or access denied.")
            return  # Owner has full access
        except HTTPException:
            raise
        except Exception as exc:
            log.error("rbac_db_error", error=str(exc))
            raise HTTPException(status_code=403, detail="Unable to verify project access.")

    member_role_str = membership[0]
    try:
        member_role = Role(member_role_str)
    except ValueError:
        member_role = Role.COLLABORATOR
    member_level = ROLE_HIERARCHY.get(member_role, 0)
    required_level = ROLE_HIERARCHY[min_role]
    if member_level < required_level:
        raise HTTPException(
            status_code=403,
            detail=f"Project access requires '{min_role.value}' role. Your role: '{member_role_str}'.",
        )


# ── Local Agent pre-shared key (§55.4) ───────────────────────────────────

# The hosted server generates this key at startup; the Local Agent presents it
# on every /agent/* call via X-Agent-Token header.
_AGENT_TOKEN: Optional[str] = os.environ.get("LOCAL_AGENT_API_KEY") or None


def verify_agent_key(x_agent_token: str = Header(alias="X-Agent-Token", default=None)) -> str:
    """FastAPI dependency — validates the Local Agent pre-shared API key.

    Usage::

        @agent_router.post("/agent/v1/inference")
        async def inference(agent=Depends(verify_agent_key)):
            ...
    """
    if _AGENT_TOKEN is None:
        # Key not configured → agent endpoints disabled
        raise HTTPException(status_code=503, detail="Local agent not configured.")
    if not x_agent_token or not secrets.compare_digest(x_agent_token, _AGENT_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing agent token.")
    return x_agent_token
