"""Docking service — AutoDock Vina integration + pocket detection."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import time
import uuid
from typing import Any, Dict, List, Optional

import structlog

from config import settings

log = structlog.get_logger()

# Path to the platform-managed tools directory
_TOOLS_BIN_DIR = os.path.join("apps", "api", "tools", "bin")

# Docking timeout in seconds
_DOCKING_TIMEOUT = 600


class DockingService:
    """AutoDock Vina docking engine with pocket detection and pose parsing."""

    SUPPORTED_ENGINES = ["vina", "smina", "gnina"]

    def __init__(self) -> None:
        self._runs_dir = os.path.join(settings.local_store_path, "docking_runs")
        os.makedirs(self._runs_dir, exist_ok=True)

    def _find_executable(self, engine: str) -> Optional[str]:
        """Find docking engine binary.

        Checks system PATH first, then the platform-managed tools/bin/ directory.
        """
        paths = {
            "vina": ["vina", "autodock_vina", "/usr/local/bin/vina"],
            "smina": ["smina", "/usr/local/bin/smina"],
            "gnina": ["gnina", "/usr/local/bin/gnina"],
        }
        # Check system PATH
        for p in paths.get(engine, []):
            if shutil.which(p):
                return p

        # Check platform-managed tools/bin/ directory
        system = os.name  # 'nt' for Windows, 'posix' for Unix
        local_name = f"{engine}.exe" if system == "nt" else engine
        local_path = os.path.join(_TOOLS_BIN_DIR, local_name)
        if os.path.isfile(local_path) and os.access(local_path, os.X_OK):
            return local_path

        return None

    @staticmethod
    def validate_docking_inputs(
        receptor_path: str,
        ligand_path: str,
        center: List[float],
        box_size: List[float],
    ) -> Optional[str]:
        """Validate docking inputs. Returns an error message or None if valid."""
        if not receptor_path or not receptor_path.strip():
            return "receptor_path is required"
        if not ligand_path or not ligand_path.strip():
            return "ligand_path is required"
        if not center or len(center) != 3:
            return "center must be a list of 3 floats [x, y, z]"
        if not box_size or len(box_size) != 3:
            return "box_size must be a list of 3 floats [sx, sy, sz]"
        for i, val in enumerate(center):
            if not isinstance(val, (int, float)):
                return f"center[{i}] must be a number"
        for i, val in enumerate(box_size):
            if not isinstance(val, (int, float)):
                return f"box_size[{i}] must be a number"
            if val <= 0:
                return f"box_size[{i}] must be positive"
        return None

    async def detect_pockets(
        self, receptor_path: str, method: str = "fpocket"
    ) -> List[Dict[str, Any]]:
        """Detect binding pockets using fpocket or P2Rank."""
        pockets: List[Dict[str, Any]] = []

        if method == "fpocket":
            fpocket_bin = shutil.which("fpocket")
            if not fpocket_bin:
                return [{"error": "fpocket not installed", "pockets": [], "method": "fpocket"}]
            try:
                proc = await asyncio.create_subprocess_exec(
                    fpocket_bin, "-f", receptor_path,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                # Parse fpocket output directory
                base = os.path.splitext(receptor_path)[0]
                pockets_dir = base + "_out"
                info_file = os.path.join(pockets_dir, "%s_info.txt" % os.path.basename(base))
                if os.path.exists(info_file):
                    pockets = self._parse_fpocket_info(info_file)
            except Exception as e:
                log.warning("fpocket_failed", error=str(e))
                pockets = [{"error": str(e)}]

        elif method == "p2rank":
            p2rank_bin = shutil.which("prank")
            if not p2rank_bin:
                return [{"error": "P2Rank (prank) not installed. Use fpocket instead.", "recommendation": "fpocket"}]
            try:
                proc = await asyncio.create_subprocess_exec(
                    p2rank_bin, "predict", "-f", receptor_path,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                # Parse P2Rank CSV output
                base = os.path.splitext(receptor_path)[0]
                csv_path = base + "_predictions.csv"
                if os.path.exists(csv_path):
                    with open(csv_path) as f:
                        lines = f.readlines()
                    for line in lines[1:]:  # skip header
                        parts = line.strip().split(",")
                        if len(parts) >= 3:
                            pockets.append({
                                "id": parts[0].strip(),
                                "score": float(parts[1].strip()) if parts[1].strip() else 0.0,
                                "residues": parts[2].strip() if len(parts) > 2 else "",
                            })
                else:
                    pockets = [{"error": "P2Rank completed but output CSV not found", "recommendation": "fpocket"}]
            except Exception as e:
                log.warning("p2rank_failed", error=str(e))
                pockets = [{"error": f"P2Rank execution failed: {e}", "recommendation": "fpocket"}]

        return pockets

    def _parse_fpocket_info(self, info_path: str) -> List[Dict[str, Any]]:
        pockets = []
        try:
            with open(info_path) as f:
                current = {}
                for line in f:
                    line = line.strip()
                    if line.startswith("Pocket"):
                        if current:
                            pockets.append(current)
                        current = {"id": line.split()[1] if len(line.split()) > 1 else "?"}
                    elif "Score" in line and ":" in line:
                        val = line.split(":")[-1].strip()
                        try:
                            current["druggability_score"] = float(val)
                        except ValueError:
                            pass
                    elif "Volume" in line and ":" in line:
                        val = line.split(":")[-1].strip()
                        try:
                            current["volume"] = float(val)
                        except ValueError:
                            pass
                if current:
                    pockets.append(current)
        except Exception:
            log.debug("fpocket output parsing failed")
        return pockets

    async def run_docking(
        self,
        receptor_path: str,
        ligand_path: str,
        center: List[float],
        box_size: List[float],
        engine: str = "vina",
        exhaustiveness: int = 8,
        num_modes: int = 9,
        energy_range: float = 3.0,
    ) -> Dict[str, Any]:
        """Run docking calculation and return poses.

        Validates inputs before execution. Enforces a 600-second timeout
        with process termination and partial log return on timeout.
        """
        run_id = str(uuid.uuid4())[:8]

        # ── Input validation ──
        validation_error = self.validate_docking_inputs(
            receptor_path, ligand_path, center, box_size
        )
        if validation_error:
            return {
                "run_id": run_id,
                "status": "validation_error",
                "error": validation_error,
                "poses": [],
            }

        run_dir = os.path.join(self._runs_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        exe = self._find_executable(engine)
        if not exe:
            return {
                "run_id": run_id,
                "status": "error",
                "error": (
                    f"{engine} not found on system PATH or in {_TOOLS_BIN_DIR}/. "
                    "Install it or use POST /api/v1/design/plugins/install."
                ),
                "poses": [],
            }

        output_path = os.path.join(run_dir, "docked_poses.pdbqt")
        log_path = os.path.join(run_dir, "docking.log")

        cmd = [
            exe,
            "--receptor", receptor_path,
            "--ligand", ligand_path,
            "--center_x", str(center[0]),
            "--center_y", str(center[1]),
            "--center_z", str(center[2]),
            "--size_x", str(box_size[0]),
            "--size_y", str(box_size[1]),
            "--size_z", str(box_size[2]),
            "--exhaustiveness", str(exhaustiveness),
            "--num_modes", str(num_modes),
            "--energy_range", str(energy_range),
            "--out", output_path,
            "--log", log_path,
        ]

        t0 = time.monotonic()
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_DOCKING_TIMEOUT
            )
            elapsed = time.monotonic() - t0

            poses = self._parse_vina_output(output_path) if os.path.exists(output_path) else []
            log_text = ""
            if os.path.exists(log_path):
                with open(log_path) as f:
                    log_text = f.read()

            # Save run metadata
            meta = {
                "run_id": run_id,
                "engine": engine,
                "receptor": receptor_path,
                "ligand": ligand_path,
                "center": center,
                "box_size": box_size,
                "exhaustiveness": exhaustiveness,
                "num_modes": num_modes,
                "elapsed_seconds": round(elapsed, 2),
                "num_poses": len(poses),
                "timestamp": time.time(),
            }
            with open(os.path.join(run_dir, "meta.json"), "w") as f:
                json.dump(meta, f, indent=2)

            return {
                "run_id": run_id,
                "status": "completed",
                "engine": engine,
                "elapsed_seconds": round(elapsed, 2),
                "poses": poses,
                "log": log_text[:2000],
                "output_path": output_path,
                "parameters": meta,
            }

        except asyncio.TimeoutError:
            # Terminate the process on timeout
            elapsed = time.monotonic() - t0
            if proc is not None:
                try:
                    proc.terminate()
                    # Give it a moment to clean up, then kill if needed
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        proc.kill()
                except ProcessLookupError:
                    pass  # Process already exited

            # Return partial log if available
            partial_log = ""
            if os.path.exists(log_path):
                try:
                    with open(log_path) as f:
                        partial_log = f.read()
                except Exception:
                    pass

            log.warning(
                "docking_timeout",
                run_id=run_id,
                elapsed=round(elapsed, 2),
                timeout=_DOCKING_TIMEOUT,
            )
            return {
                "run_id": run_id,
                "status": "timeout",
                "error": f"Docking timed out ({_DOCKING_TIMEOUT}s limit)",
                "elapsed_seconds": round(elapsed, 2),
                "log": partial_log[:2000] if partial_log else "",
                "poses": [],
            }
        except Exception as e:
            return {"run_id": run_id, "status": "error", "error": str(e), "poses": []}

    def _parse_vina_output(self, pdbqt_path: str) -> List[Dict[str, Any]]:
        """Parse Vina PDBQT multi-model output into ranked poses."""
        poses = []
        current_model = 0
        current_affinity = None

        try:
            with open(pdbqt_path) as f:
                for line in f:
                    if line.startswith("MODEL"):
                        current_model = int(line.split()[-1])
                    elif line.startswith("REMARK VINA RESULT"):
                        parts = line.split()
                        if len(parts) >= 4:
                            current_affinity = float(parts[3])
                            rmsd_lb = float(parts[4]) if len(parts) > 4 else None
                            rmsd_ub = float(parts[5]) if len(parts) > 5 else None
                            poses.append({
                                "rank": current_model,
                                "affinity_kcal": current_affinity,
                                "rmsd_lb": rmsd_lb,
                                "rmsd_ub": rmsd_ub,
                            })
        except Exception as e:
            log.warning("parse_vina_failed", error=str(e))

        return poses

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a saved docking run."""
        meta_path = os.path.join(self._runs_dir, run_id, "meta.json")
        if not os.path.exists(meta_path):
            return None
        with open(meta_path) as f:
            return json.load(f)

    def list_runs(self) -> List[Dict[str, Any]]:
        """List all saved docking runs."""
        runs = []
        if os.path.exists(self._runs_dir):
            for run_id in sorted(os.listdir(self._runs_dir), reverse=True)[:50]:
                meta = self.get_run(run_id)
                if meta:
                    runs.append(meta)
        return runs
