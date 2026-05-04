"""Hardware status & recommendations — Drug Designer §133.

GET /hardware/local     — current system hardware detection
GET /hardware/recommendations — model↔hardware compatibility guidance
"""

from __future__ import annotations

import os
import platform
import shutil
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from models.envelope import build_envelope
from routers.auth import get_current_user

router = APIRouter(prefix="/api/v1/hardware", tags=["hardware"], dependencies=[Depends(get_current_user)])


def _detect_gpu() -> Dict[str, Any]:
    """Attempt GPU detection via torch (optional)."""
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "available": True,
                "name": torch.cuda.get_device_name(0),
                "vram_mb": round(torch.cuda.get_device_properties(0).total_mem / 1024 / 1024),
                "cuda_version": torch.version.cuda or "",
            }
    except ImportError:
        pass
    return {"available": False, "name": "", "vram_mb": 0, "cuda_version": ""}


@router.get("/local")
async def get_local_hardware(
    request: Request,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Return detected local hardware capabilities (§133)."""
    disk = shutil.disk_usage(os.getcwd())
    gpu = _detect_gpu()
    try:
        import psutil
        ram_total = round(psutil.virtual_memory().total / 1024 / 1024)
        cpu_count = psutil.cpu_count(logical=True)
    except ImportError:
        ram_total = 0
        cpu_count = os.cpu_count() or 0

    data = {
        "platform": platform.system(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "cpu_count": cpu_count,
        "ram_total_mb": ram_total,
        "disk_free_mb": round(disk.free / 1024 / 1024),
        "gpu": gpu,
    }
    return build_envelope(request, data)


# Recommendation thresholds
_MODEL_REQS = [
    {"model": "BioMistral-7B", "min_ram_mb": 8000, "min_vram_mb": 6000, "fallback": "hosted"},
    {"model": "BioGPT", "min_ram_mb": 4000, "min_vram_mb": 2000, "fallback": "cpu"},
    {"model": "ESM-C 600M", "min_ram_mb": 3000, "min_vram_mb": 1500, "fallback": "cpu"},
    {"model": "ESM-3 Large (Forge API)", "min_ram_mb": 0, "min_vram_mb": 0, "fallback": "api"},
    {"model": "ChemBERTa", "min_ram_mb": 2000, "min_vram_mb": 0, "fallback": "cpu"},
]


@router.get("/recommendations")
async def get_hardware_recommendations(
    request: Request,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Recommend runtime mode per model based on local hardware (§133)."""
    gpu = _detect_gpu()
    try:
        import psutil
        ram_total = round(psutil.virtual_memory().total / 1024 / 1024)
    except ImportError:
        ram_total = 0

    recs = []
    for spec in _MODEL_REQS:
        can_gpu = gpu["available"] and gpu["vram_mb"] >= spec["min_vram_mb"]
        can_cpu = ram_total >= spec["min_ram_mb"]
        if can_gpu:
            mode = "local_gpu"
        elif can_cpu:
            mode = "local_cpu"
        else:
            mode = spec["fallback"]
        recs.append({
            "model": spec["model"],
            "recommended_mode": mode,
            "meets_gpu": can_gpu,
            "meets_cpu": can_cpu,
        })

    return build_envelope(request, {"recommendations": recs})
