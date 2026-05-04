"""ToolInstaller — Auto-downloads and installs computational chemistry binaries.

Handles OS detection, platform-specific binary resolution, streaming download,
and permission management for AutoDock Vina and fpocket.
"""

from __future__ import annotations

import os
import platform
import shutil
import stat
import time
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger(__name__)


# ── Data Models ───────────────────────────────────────────

class ToolStatus(BaseModel):
    name: str
    status: Literal["available", "not_detected", "installing", "install_failed"]
    version: str = ""
    path: str = ""
    error: Optional[str] = None
    install_hint: str = ""


class InstallResult(BaseModel):
    tool: str
    status: Literal["installed", "already_available", "failed"]
    path: str = ""
    error: Optional[str] = None
    duration_seconds: float = 0.0


# ── ToolInstaller Service ────────────────────────────────

class ToolInstaller:
    """Auto-downloads and installs computational chemistry binaries."""

    TOOLS_DIR = os.path.join("apps", "api", "tools", "bin")

    VINA_VERSION = "1.2.5"
    VINA_RELEASES_BASE = "https://github.com/ccsb-scripps/AutoDock-Vina/releases"

    # Platform-specific binary mapping: (system, machine) -> binary filename
    PLATFORM_MAP: Dict[Tuple[str, str], str] = {
        ("Linux", "x86_64"): "vina_1.2.5_linux_x86_64",
        ("Darwin", "x86_64"): "vina_1.2.5_mac_x86_64",
        ("Darwin", "arm64"): "vina_1.2.5_mac_arm64",
        ("Windows", "AMD64"): "vina_1.2.5_win32.exe",
    }

    def __init__(self, tools_dir: Optional[str] = None) -> None:
        if tools_dir is not None:
            self.tools_dir = tools_dir
        else:
            self.tools_dir = self.TOOLS_DIR
        os.makedirs(self.tools_dir, exist_ok=True)

    @staticmethod
    def detect_os() -> Tuple[str, str]:
        """Return (system, machine) tuple using the platform module."""
        return platform.system(), platform.machine()

    def get_download_url(self, tool: str) -> str:
        """Resolve the platform-specific download URL for a tool.

        Currently supports 'vina'. Raises ValueError for unsupported
        tools or platforms.
        """
        if tool != "vina":
            raise ValueError(f"Unsupported tool for download: {tool}")

        system, machine = self.detect_os()
        key = (system, machine)
        binary_name = self.PLATFORM_MAP.get(key)
        if not binary_name:
            raise ValueError(
                f"No Vina binary available for {system}/{machine}. "
                f"Supported platforms: {list(self.PLATFORM_MAP.keys())}"
            )
        return (
            f"{self.VINA_RELEASES_BASE}/download/"
            f"v{self.VINA_VERSION}/{binary_name}"
        )

    async def install_tool(self, tool: str) -> InstallResult:
        """Download and install a tool binary.

        Uses httpx streaming download. Sets chmod 755 on Unix systems.
        Returns an InstallResult with status and path.
        """
        t0 = time.monotonic()

        if tool == "fpocket":
            return self._handle_fpocket_install(t0)

        if tool != "vina":
            return InstallResult(
                tool=tool,
                status="failed",
                error=f"Unknown tool: {tool}. Supported: vina, fpocket",
                duration_seconds=round(time.monotonic() - t0, 2),
            )

        # Check if already available
        availability = self.check_availability()
        vina_status = availability.get("vina")
        if vina_status and vina_status.status == "available":
            return InstallResult(
                tool="vina",
                status="already_available",
                path=vina_status.path,
                duration_seconds=round(time.monotonic() - t0, 2),
            )

        # Resolve download URL
        try:
            url = self.get_download_url("vina")
        except ValueError as exc:
            log.error("vina_url_resolution_failed", error=str(exc))
            return InstallResult(
                tool="vina",
                status="failed",
                error=str(exc),
                duration_seconds=round(time.monotonic() - t0, 2),
            )

        # Determine local filename
        system, _ = self.detect_os()
        binary_filename = "vina.exe" if system == "Windows" else "vina"
        dest_path = os.path.join(self.tools_dir, binary_filename)

        # Download with httpx streaming
        try:
            import httpx

            log.info("vina_download_start", url=url, dest=dest_path)
            async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with open(dest_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)

            # Set executable permissions on Unix
            if system != "Windows":
                os.chmod(dest_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)  # 755

            log.info("vina_download_complete", path=dest_path)
            return InstallResult(
                tool="vina",
                status="installed",
                path=dest_path,
                duration_seconds=round(time.monotonic() - t0, 2),
            )

        except Exception as exc:
            log.error(
                "vina_install_failed",
                error=str(exc),
                manual_instructions=(
                    "Download Vina manually from "
                    "https://github.com/ccsb-scripps/AutoDock-Vina/releases "
                    f"and place the binary in {self.tools_dir}/"
                ),
            )
            # Clean up partial download
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
            return InstallResult(
                tool="vina",
                status="failed",
                error=(
                    f"Download failed: {exc}. "
                    "Manual install: download from "
                    "https://github.com/ccsb-scripps/AutoDock-Vina/releases "
                    f"and place the binary in {self.tools_dir}/"
                ),
                duration_seconds=round(time.monotonic() - t0, 2),
            )

    def _handle_fpocket_install(self, t0: float) -> InstallResult:
        """Handle fpocket: check PATH, provide install instructions if missing."""
        fpocket_bin = shutil.which("fpocket")
        if fpocket_bin:
            return InstallResult(
                tool="fpocket",
                status="already_available",
                path=fpocket_bin,
                duration_seconds=round(time.monotonic() - t0, 2),
            )

        # Also check tools/bin
        local_fpocket = os.path.join(self.tools_dir, "fpocket")
        if os.path.isfile(local_fpocket) and os.access(local_fpocket, os.X_OK):
            return InstallResult(
                tool="fpocket",
                status="already_available",
                path=local_fpocket,
                duration_seconds=round(time.monotonic() - t0, 2),
            )

        # fpocket cannot be auto-downloaded easily — provide instructions
        log.warning(
            "fpocket_not_found",
            install_hint=(
                "Install fpocket via: conda install -c bioconda fpocket "
                "or build from https://github.com/Discngine/fpocket"
            ),
        )
        return InstallResult(
            tool="fpocket",
            status="failed",
            error=(
                "fpocket not found on PATH or in tools directory. "
                "Install via: conda install -c bioconda fpocket "
                "or build from https://github.com/Discngine/fpocket"
            ),
            duration_seconds=round(time.monotonic() - t0, 2),
        )

    def check_availability(self) -> Dict[str, ToolStatus]:
        """Check which tools are available (system PATH and tools/bin/).

        Returns a dict mapping tool name to its ToolStatus.
        """
        results: Dict[str, ToolStatus] = {}

        # ── Vina ──
        vina_names = ["vina", "autodock_vina"]
        vina_path: Optional[str] = None

        # Check system PATH first
        for name in vina_names:
            found = shutil.which(name)
            if found:
                vina_path = found
                break

        # Check tools/bin directory
        if not vina_path:
            system, _ = self.detect_os()
            local_name = "vina.exe" if system == "Windows" else "vina"
            local_path = os.path.join(self.tools_dir, local_name)
            if os.path.isfile(local_path) and os.access(local_path, os.X_OK):
                vina_path = local_path

        if vina_path:
            results["vina"] = ToolStatus(
                name="vina",
                status="available",
                path=vina_path,
            )
        else:
            results["vina"] = ToolStatus(
                name="vina",
                status="not_detected",
                install_hint=(
                    "Install from https://github.com/ccsb-scripps/AutoDock-Vina/releases "
                    "or use POST /api/v1/design/plugins/install"
                ),
            )

        # ── fpocket ──
        fpocket_path = shutil.which("fpocket")
        if not fpocket_path:
            local_fpocket = os.path.join(self.tools_dir, "fpocket")
            if os.path.isfile(local_fpocket) and os.access(local_fpocket, os.X_OK):
                fpocket_path = local_fpocket

        if fpocket_path:
            results["fpocket"] = ToolStatus(
                name="fpocket",
                status="available",
                path=fpocket_path,
            )
        else:
            results["fpocket"] = ToolStatus(
                name="fpocket",
                status="not_detected",
                install_hint=(
                    "Install via: conda install -c bioconda fpocket "
                    "or build from https://github.com/Discngine/fpocket"
                ),
            )

        return results

    async def ensure_tools_available(self) -> None:
        """Called on app startup — attempt to install missing tools.

        Logs results but never raises, so the API starts regardless.
        """
        log.info("tool_installer_startup_check")
        availability = self.check_availability()

        for tool_name, status in availability.items():
            if status.status == "available":
                log.info("tool_available", tool=tool_name, path=status.path)
                continue

            log.info("tool_missing_attempting_install", tool=tool_name)
            result = await self.install_tool(tool_name)
            if result.status == "installed":
                log.info(
                    "tool_installed_on_startup",
                    tool=tool_name,
                    path=result.path,
                    duration=result.duration_seconds,
                )
            elif result.status == "already_available":
                log.info("tool_already_available", tool=tool_name, path=result.path)
            else:
                log.warning(
                    "tool_install_failed_on_startup",
                    tool=tool_name,
                    error=result.error,
                )
