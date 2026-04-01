"""Cross-platform path resolution and storage policy for DrugSynth Workbench."""

import os
from platformdirs import PlatformDirs

class StorageMode:
    ONLINE_ONLY = "online_only"
    LOCAL_EMBEDDED = "local_embedded"

# Load settings directly from environment to avoid circular dependencies with config.py
DSS_DATA_MODE = os.getenv("DSS_DATA_MODE", StorageMode.ONLINE_ONLY)
_DSS_DATA_DIR = os.getenv("DSS_DATA_DIR")
_DSS_CACHE_DIR = os.getenv("DSS_CACHE_DIR")

_dirs = PlatformDirs(appname="DrugSynthStudio", appauthor="DSS")

def get_app_dir() -> str:
    """Directory for configuration and user preferences."""
    return _dirs.user_config_dir

def get_data_dir() -> str:
    """Directory for databases, job logs, and generated artifacts."""
    if _DSS_DATA_DIR:
        return _DSS_DATA_DIR
    return _dirs.user_data_dir

def get_cache_dir() -> str:
    """Directory for caching online queries (e.g., SQLite HTTP cache)."""
    if _DSS_CACHE_DIR:
        return _DSS_CACHE_DIR
    return _dirs.user_cache_dir

def get_data_mode() -> str:
    """Returns the current data mode (default: online_only)."""
    return DSS_DATA_MODE

def ensure_dirs():
    """Ensure that the platform-specific directories exist."""
    os.makedirs(get_app_dir(), exist_ok=True)
    os.makedirs(get_data_dir(), exist_ok=True)
    os.makedirs(get_cache_dir(), exist_ok=True)

# Ensure directories exist upon module load
ensure_dirs()
