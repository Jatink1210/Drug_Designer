"""Runtime environment bootstrap helpers.

Keeps local `.env` defaults available without letting them override real
runtime env injected by Docker, CI, or the shell.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def load_runtime_env(dotenv_path: Optional[str | Path] = None) -> bool:
    """Load local defaults without clobbering existing process env."""
    return load_dotenv(dotenv_path=dotenv_path, override=False)