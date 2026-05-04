"""
Workbench Local Agent (WLA)
Companion daemon running on localhost:4133.
Executes local LLMs, orchestrates heavy local Python routines, and telemetry.
Includes handshake token auth (Section 16.3) and llama.cpp health check.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import os
import time

app = FastAPI(title="Workbench Local Runtime Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Handshake auth token — set via env var for security (Section 16.3)
AGENT_TOKEN = os.environ.get("WLA_AUTH_TOKEN", "")

@app.middleware("http")
async def verify_handshake(request: Request, call_next):
    """Require handshake token if one is configured."""
    if AGENT_TOKEN and request.url.path != "/health":
        token = request.headers.get("X-WLA-Token", "")
        if token != AGENT_TOKEN:
            raise HTTPException(401, "Invalid or missing handshake token (X-WLA-Token)")
    return await call_next(request)

def _get_physical_gpu():
    """Reads genuine PCIe NVML state."""
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=gpu_name", "--format=csv,noheader"], encoding="utf-8")
        return [o.strip() for o in out.split("\n") if o.strip()]
    except Exception:
        return ["Physical CPU Node (GPU Offline or NVIDIA-SMI missing)"]

@app.get("/health")
def read_health():
    return {"status": "online", "agent_name": "WLA-Core", "detected_hardware": _get_physical_gpu(), "auth_required": bool(AGENT_TOKEN)}

@app.get("/system/hardware")
def get_hardware_status():
    import psutil
    gpus = _get_physical_gpu()
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    cpu_pct = psutil.cpu_percent(interval=0.5)
    return {
        "devices": [
            {"id": "gpu0" if "CPU" not in gpus[0] else "cpu0",
             "name": gpus[0],
             "type": "gpu" if "CPU" not in gpus[0] else "cpu",
             "memory_gb": 8.0 if "CPU" not in gpus[0] else ram_gb,
             "utilization_pct": cpu_pct}
        ],
        "system_ram_gb": ram_gb,
        "cpu_percent": cpu_pct,
        "os": os.name,
        "recommended_tier": "70b_quantized" if "CPU" not in gpus[0] else "8b_instruct"
    }

@app.get("/system/diagnostics")
def get_diagnostics():
    import psutil
    import platform
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "disk_free_gb": round(psutil.disk_usage("/").free / (1024**3), 1),
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "llama_cpp_check": _check_llama_cpp()
    }

def _check_llama_cpp():
    """Check if llama.cpp server is reachable."""
    try:
        import httpx
        r = httpx.get("http://localhost:8080/health", timeout=2.0)
        return {"status": "online", "code": r.status_code}
    except Exception:
        return {"status": "offline"}


# ── J-1: Full hardware capability scan (pynvml + psutil) ─

@app.get("/hardware/capabilities")
def get_hardware_capabilities():
    """J-1: Deep hardware scan — GPU VRAM (pynvml), CPU, RAM, disk, model cache."""
    from engine import HardwareScanner
    scanner = HardwareScanner()
    return scanner.scan()


# ── J-2: Runtime inventory sync ───────────────────────────

@app.post("/runtime/sync")
async def sync_runtime_inventory(api_url: str = "http://localhost:8000", token: str = ""):
    """J-2: Build runtime_inventory_json and POST it to the API server."""
    from engine import RuntimeInventory
    inv = RuntimeInventory(api_url=api_url, token=token)
    inventory = inv.build()
    ok = await inv.sync_to_api()
    return {"status": "synced" if ok else "local_only", "inventory": inventory}


@app.get("/runtime/inventory")
def get_runtime_inventory():
    """J-2: Return current runtime inventory snapshot (without syncing)."""
    from engine import RuntimeInventory
    inv = RuntimeInventory()
    return inv.build()


# ── J-3: Local model dispatch ─────────────────────────────

@app.post("/agent/inference")
async def agent_inference(payload: dict):
    """J-3: Dispatch inference task to optimal backend (local GPU / Ollama / hosted API)."""
    from engine import LocalModelDispatcher
    dispatcher = LocalModelDispatcher()
    task = payload.get("task", "generate")
    result = await dispatcher.dispatch(task, payload)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=4133)

        return {"status": "offline"}

@app.post("/run_airllm_pass")
def run_airllm(model_id: str = "llama3"):
    from inference.airllm_optim import AirLLMPagingOptimizer
    optimizer = AirLLMPagingOptimizer(target_vram_gb=8)
    return optimizer.optimize_generation_pass(model_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=4133)

