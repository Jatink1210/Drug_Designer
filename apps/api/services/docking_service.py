"""Docking service — AutoDock Vina integration + pocket detection."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional

import structlog

from config import settings

log = structlog.get_logger()


class DockingService:
    """AutoDock Vina docking engine with pocket detection and pose parsing."""

    SUPPORTED_ENGINES = ["vina", "smina", "gnina"]

    def __init__(self) -> None:
        self._runs_dir = os.path.join(settings.local_store_path, "docking_runs")
        os.makedirs(self._runs_dir, exist_ok=True)

    def _find_executable(self, engine: str) -> Optional[str]:
        """Find docking engine binary."""
        paths = {
            "vina": ["vina", "autodock_vina", "/usr/local/bin/vina"],
            "smina": ["smina", "/usr/local/bin/smina"],
            "gnina": ["gnina", "/usr/local/bin/gnina"],
        }
        for p in paths.get(engine, []):
            if shutil.which(p):
                return p
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
        """Run docking calculation and return poses."""
        run_id = str(uuid.uuid4())[:8]
        run_dir = os.path.join(self._runs_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        exe = self._find_executable(engine)
        if not exe:
            return {
                "run_id": run_id,
                "status": "error",
                "error": "%s not found on system PATH. Install it or use a different engine." % engine,
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
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
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
            return {"run_id": run_id, "status": "timeout", "error": "Docking timed out (600s limit)", "poses": []}
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
