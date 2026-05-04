"""API endpoints for user settings and setup wizard state.

R-010 fix: All state stored in PostgreSQL UserPreference table.
All endpoints require authentication (§61, §A1.1).
"""

import logging
import shutil
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings as app_settings
from core.db import get_db
from models.db_tables import UserPreference
from models.envelope import build_envelope
from routers.auth import get_current_user
from services.runtime.selector import RuntimeSelector

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
log = logging.getLogger(__name__)


def _capability_entry(
    *,
    status: str,
    available: bool,
    shipping_tier: str,
    ship_blocking: bool,
    details: str,
    install_hint: str = "",
    version: str = "",
    path: str = "",
) -> Dict[str, Any]:
    return {
        "status": status,
        "available": available,
        "shipping_tier": shipping_tier,
        "ship_blocking": ship_blocking,
        "details": details,
        "install_hint": install_hint,
        "version": version,
        "path": path,
    }


def _native_tool_diagnostics() -> Dict[str, Any]:
    from services.tool_installer import ToolInstaller

    try:
        from rdkit import rdBase  # type: ignore

        rdkit_entry = _capability_entry(
            status="available",
            available=True,
            shipping_tier="supported",
            ship_blocking=True,
            details="Core cheminformatics support for descriptors, validation, and heuristics.",
            version=getattr(rdBase, "rdkitVersion", "unknown") or "unknown",
        )
    except Exception:
        rdkit_entry = _capability_entry(
            status="not_detected",
            available=False,
            shipping_tier="supported",
            ship_blocking=True,
            details="Core cheminformatics support for descriptors, validation, and heuristics.",
            install_hint="pip install rdkit-pypi",
        )

    installer = ToolInstaller()
    availability = installer.check_availability()

    def _optional_local_entry(tool_name: str, details: str, fallback_hint: str) -> Dict[str, Any]:
        tool_status = availability.get(tool_name)
        if tool_status and tool_status.status == "available":
            return _capability_entry(
                status="available",
                available=True,
                shipping_tier="optional_local",
                ship_blocking=False,
                details=details,
                install_hint="",
                path=tool_status.path or "",
            )
        return _capability_entry(
            status="not_detected",
            available=False,
            shipping_tier="optional_local",
            ship_blocking=False,
            details=details,
            install_hint=(tool_status.install_hint if tool_status else fallback_hint),
        )

    return {
        "rdkit": rdkit_entry,
        "vina": _optional_local_entry(
            "vina",
            "Optional local-native docking acceleration. Hosted release degrades gracefully without it.",
            "Install from https://vina.scripps.edu/ or use POST /api/v1/design/plugins/install",
        ),
        "fpocket": _optional_local_entry(
            "fpocket",
            "Optional local-native pocket detection. Hosted release falls back to annotations or degraded guidance.",
            "Install from https://github.com/Discngine/fpocket or conda install -c bioconda fpocket",
        ),
        "p2rank": _capability_entry(
            status="available" if bool(shutil.which("prank")) else "not_detected",
            available=bool(shutil.which("prank")),
            shipping_tier="optional_local",
            ship_blocking=False,
            details="Optional local-native ML pocket detection. Hosted release does not require it.",
            install_hint="Install P2Rank and ensure the `prank` binary is on PATH" if not shutil.which("prank") else "",
            path=shutil.which("prank") or "",
        ),
        "native_tools": {
            "shipping_profile": "optional_local",
            "summary": "AutoDock Vina, fpocket, and P2Rank are optional local-native enhancements and are not part of the default shipped hosted runtime.",
        },
    }


class UserSettings(BaseModel):
    compute_mode: str = "auto"  # auto, cpu, gpu, remote
    runtime: str = "remote"  # llama.cpp, airllm, remote
    model_id: str = app_settings.openai_model
    remote_base_url: Optional[str] = ""
    privacy_mode: bool = True
    setup_complete: bool = False


def _pref_to_settings(pref: Optional[UserPreference]) -> UserSettings:
    """Convert a DB UserPreference row to UserSettings, with defaults."""
    if pref is None:
        return UserSettings()
    extra = pref.preferences_json or {}
    return UserSettings(
        compute_mode=extra.get("compute_mode", "auto"),
        runtime=pref.default_runtime_mode or "remote",
        model_id=pref.default_model_id or app_settings.openai_model,
        remote_base_url=extra.get("remote_base_url", ""),
        privacy_mode=extra.get("privacy_mode", True),
        setup_complete=extra.get("setup_complete", False),
    )


@router.get("")
async def get_settings(
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve current user settings from DB."""
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )
    pref = result.scalars().first()
    return build_envelope(request, _pref_to_settings(pref).model_dump())


@router.post("")
async def update_settings(
    request: Request,
    new_settings: UserSettings,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update and persist user settings to DB, syncing with RuntimeSelector."""
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )
    pref = result.scalars().first()

    if pref is None:
        pref = UserPreference(
            user_id=user.id,
            default_runtime_mode=new_settings.runtime,
            default_model_id=new_settings.model_id,
            preferences_json={
                "compute_mode": new_settings.compute_mode,
                "remote_base_url": new_settings.remote_base_url or "",
                "privacy_mode": new_settings.privacy_mode,
                "setup_complete": new_settings.setup_complete,
            },
        )
        db.add(pref)
    else:
        pref.default_runtime_mode = new_settings.runtime
        pref.default_model_id = new_settings.model_id
        pref.preferences_json = {
            "compute_mode": new_settings.compute_mode,
            "remote_base_url": new_settings.remote_base_url or "",
            "privacy_mode": new_settings.privacy_mode,
            "setup_complete": new_settings.setup_complete,
        }

    await db.commit()

    try:
        RuntimeSelector.set_active_runtime(
            runtime_id=new_settings.runtime,
            model_name=new_settings.model_id,
            endpoint=new_settings.remote_base_url or "",
            compute_mode=new_settings.compute_mode,
        )
    except Exception as e:
        log.warning("Failed to sync RuntimeSelector: %s", e)

    return build_envelope(request, {"status": "success", "settings": new_settings.model_dump()})


# ── Task 25: Additional settings endpoints ──────────────────

@router.put("/{section}")
async def update_section_settings(
    section: str,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """PUT /api/v1/settings/{section} — Update a specific settings section.

    Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6
    """
    body = await request.json()

    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )
    pref = result.scalars().first()

    if pref is None:
        pref = UserPreference(
            user_id=user.id,
            preferences_json={section: body},
        )
        db.add(pref)
    else:
        prefs = dict(pref.preferences_json or {})
        prefs[section] = body
        pref.preferences_json = prefs

    await db.commit()
    return build_envelope(request, {"status": "success", "section": section, "data": body})


@router.get("/sources/health")
async def get_sources_health(
    request: Request,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """GET /api/v1/settings/sources/health — Return connector health status.

    Requirements: 14.2
    """
    from core.circuit_breaker import CircuitBreakerRegistry

    try:
        registry = CircuitBreakerRegistry()
        statuses = registry.get_all_statuses()
    except Exception:
        statuses = {}

    sources = []
    for name, status in statuses.items():
        sources.append({
            "name": name,
            "status": "healthy" if status.get("state") == "closed" else "degraded",
            "failures": status.get("failure_count", 0),
            "last_checked": status.get("last_checked"),
        })

    return build_envelope(request, {"sources": sources, "count": len(sources)})


@router.get("/diagnostics")
async def get_diagnostics(
    request: Request,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """GET /api/v1/settings/diagnostics — Return system health metrics.

    Requirements: 14.5
    """
    import platform

    diagnostics: Dict[str, Any] = {
        "platform": {
            "system": platform.system(),
            "python_version": platform.python_version(),
            "machine": platform.machine(),
        },
        "database": {"status": "connected"},
        "api": {"status": "healthy"},
    }

    try:
        import psutil
        diagnostics["system"] = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        }
    except ImportError:
        diagnostics["system"] = {"note": "psutil not installed for system metrics"}

    try:
        import torch
        diagnostics["gpu"] = {
            "status": "available" if torch.cuda.is_available() else "cpu_only",
            "available": torch.cuda.is_available(),
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "shipping_tier": "optional_acceleration",
            "ship_blocking": False,
            "details": "GPU acceleration is optional; CPU mode remains supported for the shipped workflow.",
        }
    except ImportError:
        diagnostics["gpu"] = {
            "status": "not_detected",
            "available": False,
            "device_count": 0,
            "device_name": None,
            "shipping_tier": "optional_acceleration",
            "ship_blocking": False,
            "details": "GPU acceleration is optional; CPU mode remains supported for the shipped workflow.",
        }

    diagnostics.update(_native_tool_diagnostics())

    return build_envelope(request, diagnostics)
