"""API endpoints for user settings and setup wizard state."""

import json
import logging
import os
from typing import Dict, Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core.paths import get_app_dir
from services.runtime.selector import RuntimeSelector

router = APIRouter(prefix="/api/settings", tags=["settings"])
log = logging.getLogger(__name__)


class UserSettings(BaseModel):
    compute_mode: str = "auto"  # auto, cpu, gpu, remote
    runtime: str = "llama.cpp"  # llama.cpp, airllm, remote
    model_id: str = "BioMistral-7B"
    remote_base_url: Optional[str] = ""
    privacy_mode: bool = True
    setup_complete: bool = False


def _get_settings_path() -> str:
    """Path to the user's settings JSON file."""
    return os.path.join(get_app_dir(), "user_settings.json")


def _load_settings() -> UserSettings:
    """Load settings from disk or return default."""
    path = _get_settings_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return UserSettings(**data)
        except Exception:
            log.debug("Settings file not readable, using defaults")
    return UserSettings()


def _save_settings(user_settings: UserSettings) -> None:
    """Persist settings to disk."""
    path = _get_settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(user_settings.model_dump(), f, indent=2)


@router.get("")
async def get_settings() -> Dict[str, Any]:
    """Retrieve current user settings."""
    user_settings = _load_settings()
    return user_settings.model_dump()


@router.post("")
async def update_settings(new_settings: UserSettings) -> Dict[str, Any]:
    """Update and persist user settings, syncing with RuntimeSelector."""
    _save_settings(new_settings)

    try:
        RuntimeSelector.set_active_runtime(
            runtime_id=new_settings.runtime,
            model_name=new_settings.model_id,
            endpoint=new_settings.remote_base_url or "",
            compute_mode=new_settings.compute_mode,
        )
    except Exception as e:
        log.warning("Failed to sync RuntimeSelector: %s", e)

    return {"status": "success", "settings": new_settings.model_dump()}
