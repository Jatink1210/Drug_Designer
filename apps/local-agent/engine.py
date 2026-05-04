"""Local Agent — Universal Inference Engine (Drug Designer §44.1).

Local-side inference engine using AirLLM 4bit quantization and
SSD speculative decoding for consumer GPUs (4GB-8GB VRAM).

This file runs inside the Local Runtime Agent process on the user's
machine, NOT on the hosted server.
"""

from __future__ import annotations

import platform
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger()


class LocalInferenceEngine:
    """AirLLM-powered inference on consumer hardware.

    Dynamically pages model layers between CPU RAM, NVMe disk,
    and limited VRAM to enable 70B model execution on 4GB GPUs.
    """

    def __init__(self, model_path: str = "", max_vram_gb: float = 4.0):
        self.model_path = model_path
        self.max_vram_gb = max_vram_gb
        self._model = None
        self._loaded = False
        self._tokenizer = None

    async def load(self) -> Dict[str, Any]:
        """Load model with AirLLM 4-bit quantization (§44.1)."""
        log.info("local_engine.load", model=self.model_path, vram=self.max_vram_gb)
        if not self.model_path:
            return {"status": "error", "message": "No model path specified"}
        try:
            from airllm import AutoModel
            self._model = AutoModel.from_pretrained(
                self.model_path,
                compression="4bit",
            )
            self._loaded = True
            log.info("local_engine.loaded", model=self.model_path)
            return {"status": "loaded", "model": self.model_path, "vram_gb": self.max_vram_gb}
        except ImportError:
            log.warning("airllm_not_installed")
            self._loaded = False
            return {"status": "degraded", "message": "airllm package not installed"}
        except Exception as e:
            log.error("local_engine.load_failed", error=str(e))
            self._loaded = False
            return {"status": "error", "message": str(e)}

    async def generate(self, prompt: str, max_tokens: int = 256) -> Dict[str, Any]:
        """Generate text locally using AirLLM (§44.1)."""
        if not self._loaded or self._model is None:
            return {"error": "Model not loaded", "status": "degraded", "text": ""}
        try:
            # AirLLM generate interface
            input_ids = self._model.tokenizer(prompt, return_tensors="pt").input_ids
            output = self._model.generate(
                input_ids,
                max_new_tokens=max_tokens,
                do_sample=True,
                temperature=0.7,
            )
            text = self._model.tokenizer.decode(output[0][input_ids.shape[1]:], skip_special_tokens=True)
            return {
                "text": text,
                "tokens_generated": len(output[0]) - input_ids.shape[1],
                "model": self.model_path,
                "status": "ok",
            }
        except Exception as e:
            log.error("local_engine.generate_failed", error=str(e))
            return {"error": str(e), "status": "degraded", "text": ""}

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings locally, projecting to 512d (§44.1)."""
        if not self._loaded or self._model is None:
            return []
        try:
            import torch
            embeddings = []
            for text in texts:
                input_ids = self._model.tokenizer(text, return_tensors="pt", truncation=True, max_length=512).input_ids
                with torch.no_grad():
                    outputs = self._model.model(input_ids, output_hidden_states=True)
                    hidden = outputs.hidden_states[-1].mean(dim=1).squeeze()
                    # Project to 512d
                    if hidden.shape[0] > 512:
                        hidden = hidden[:512]
                    elif hidden.shape[0] < 512:
                        hidden = torch.nn.functional.pad(hidden, (0, 512 - hidden.shape[0]))
                    embeddings.append(hidden.tolist())
            return embeddings
        except Exception as e:
            log.error("local_engine.embed_failed", error=str(e))
            return []


def detect_hardware() -> Dict[str, Any]:
    """Detect local hardware capabilities.

    §27.4: Hardware detection for CPU, RAM, GPU VRAM, disk space.
    """
    import os

    info: Dict[str, Any] = {
        "platform": platform.system().lower(),
        "cpu": platform.processor(),
        "cpu_count": os.cpu_count(),
        "ram_gb": None,
        "gpu_name": None,
        "gpu_vram_gb": None,
        "disk_free_gb": None,
    }

    # RAM detection
    try:
        import psutil
        info["ram_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        info["disk_free_gb"] = round(psutil.disk_usage("/").free / (1024**3), 1)
    except ImportError:
        pass

    # GPU detection
    try:
        import torch
        if torch.cuda.is_available():
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_vram_gb"] = round(
                torch.cuda.get_device_properties(0).total_mem / (1024**3), 1
            )
    except ImportError:
        pass

    return info


# ──────────────────────────────────────────────────────────
# J-1: Hardware Capability Scanner (pynvml + psutil)
# ──────────────────────────────────────────────────────────

class HardwareScanner:
    """J-1: Full hardware capability scanner — GPU VRAM (pynvml), CPU RAM, disk, model cache."""

    # ESM-C threshold per spec §56
    ESMC_MIN_VRAM_GB: float = 1.5
    # Ollama 7B threshold
    OLLAMA_7B_MIN_VRAM_GB: float = 6.0
    OLLAMA_70B_MIN_VRAM_GB: float = 40.0  # full; AirLLM handles below

    def scan(self) -> Dict[str, Any]:
        """Run full hardware scan; return structured capability report."""
        report: Dict[str, Any] = {
            "cpu": self._cpu_info(),
            "ram": self._ram_info(),
            "gpu": self._gpu_info(),
            "disk": self._disk_info(),
            "model_cache": self._model_cache_inventory(),
        }
        report["dispatch_recommendations"] = self._dispatch_recommendations(report)
        log.info("hardware_scan_complete",
                 gpu_vram_gb=report["gpu"].get("vram_gb"),
                 ram_gb=report["ram"].get("total_gb"))
        return report

    # ── helpers ──────────────────────────────────────────

    def _cpu_info(self) -> Dict[str, Any]:
        import os
        info: Dict[str, Any] = {"count": os.cpu_count() or 0, "name": platform.processor()}
        try:
            import psutil
            info["freq_mhz"] = round(psutil.cpu_freq().current) if psutil.cpu_freq() else 0
        except Exception:
            pass
        return info

    def _ram_info(self) -> Dict[str, Any]:
        try:
            import psutil
            vm = psutil.virtual_memory()
            return {
                "total_gb": round(vm.total / (1024**3), 1),
                "available_gb": round(vm.available / (1024**3), 1),
                "used_pct": vm.percent,
            }
        except Exception:
            return {"total_gb": 0, "available_gb": 0, "used_pct": 0}

    def _gpu_info(self) -> Dict[str, Any]:
        """Try pynvml first (most accurate), fall back to torch."""
        # pynvml path
        try:
            import pynvml
            pynvml.nvmlInit()
            n = pynvml.nvmlDeviceGetCount()
            gpus = []
            for i in range(n):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                name = pynvml.nvmlDeviceGetName(handle)
                # pynvml may return bytes or str depending on version
                if isinstance(name, bytes):
                    name = name.decode()
                gpus.append({
                    "index": i,
                    "name": name,
                    "vram_total_gb": round(mem.total / (1024**3), 2),
                    "vram_free_gb": round(mem.free / (1024**3), 2),
                    "vram_used_gb": round(mem.used / (1024**3), 2),
                })
            pynvml.nvmlShutdown()
            primary = gpus[0] if gpus else {}
            return {
                "available": len(gpus) > 0,
                "count": len(gpus),
                "devices": gpus,
                "name": primary.get("name", ""),
                "vram_gb": primary.get("vram_total_gb", 0),
                "vram_free_gb": primary.get("vram_free_gb", 0),
                "source": "pynvml",
            }
        except Exception:
            pass
        # torch fallback
        try:
            import torch
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                return {
                    "available": True,
                    "count": torch.cuda.device_count(),
                    "name": torch.cuda.get_device_name(0),
                    "vram_gb": round(props.total_mem / (1024**3), 2),
                    "vram_free_gb": 0,  # torch doesn't expose free easily pre-load
                    "source": "torch",
                }
        except Exception:
            pass
        return {"available": False, "count": 0, "name": "", "vram_gb": 0, "vram_free_gb": 0, "source": "none"}

    def _disk_info(self) -> Dict[str, Any]:
        import os, shutil
        try:
            import psutil
            usage = psutil.disk_usage(os.path.expanduser("~"))
            return {
                "total_gb": round(usage.total / (1024**3), 1),
                "free_gb": round(usage.free / (1024**3), 1),
                "used_pct": usage.percent,
            }
        except Exception:
            try:
                usage = shutil.disk_usage(os.path.expanduser("~"))
                return {
                    "total_gb": round(usage.total / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "used_pct": round((usage.used / usage.total) * 100, 1),
                }
            except Exception:
                return {"total_gb": 0, "free_gb": 0, "used_pct": 0}

    def _model_cache_inventory(self) -> List[Dict[str, Any]]:
        """Scan standard model cache dirs for downloaded checkpoints."""
        import os, glob as _glob
        cache_dirs = [
            os.path.expanduser("~/.cache/huggingface/hub"),
            os.path.expanduser("~/.ollama/models"),
            os.path.expanduser("~/.cache/torch/hub"),
        ]
        items: List[Dict[str, Any]] = []
        for d in cache_dirs:
            if not os.path.isdir(d):
                continue
            source = "ollama" if "ollama" in d else "huggingface" if "huggingface" in d else "torch"
            # List top-level model directories
            for entry in os.scandir(d):
                if not entry.is_dir():
                    continue
                size_bytes = sum(
                    f.stat().st_size for f in _glob.iglob(os.path.join(entry.path, "**"), recursive=True)
                    if os.path.isfile(f)
                )
                items.append({
                    "name": entry.name,
                    "source": source,
                    "path": entry.path,
                    "size_gb": round(size_bytes / (1024**3), 2),
                })
        return items

    def _dispatch_recommendations(self, report: Dict[str, Any]) -> Dict[str, str]:
        """J-3: Determine optimal dispatch route per model type."""
        vram = report["gpu"].get("vram_gb", 0)
        ram = report["ram"].get("total_gb", 0)
        recs: Dict[str, str] = {}
        # ESM-C 600M: local if VRAM ≥ 1.5 GB
        recs["esmc"] = "local_gpu" if vram >= self.ESMC_MIN_VRAM_GB else "cpu" if ram >= 3 else "hosted_api"
        # Ollama 7B: local GPU if VRAM ≥ 6 GB else CPU if RAM ≥ 8 GB else hosted
        recs["ollama_7b"] = "local_gpu" if vram >= self.OLLAMA_7B_MIN_VRAM_GB else "local_cpu" if ram >= 8 else "hosted_api"
        # Ollama 70B: AirLLM sharding if any GPU else hosted
        recs["ollama_70b"] = "airllm_sharded" if vram > 0 else "hosted_api"
        # BioMistral 7B: same as ollama_7b
        recs["biomistral"] = recs["ollama_7b"]
        return recs


# ──────────────────────────────────────────────────────────
# J-2: Runtime Inventory + API sync
# ──────────────────────────────────────────────────────────

class RuntimeInventory:
    """J-2: Populate runtime_inventory_json and sync to API server."""

    def __init__(self, api_url: str = "http://localhost:8000", token: str = ""):
        self.api_url = api_url
        self.token = token
        self._scanner = HardwareScanner()

    def build(self) -> Dict[str, Any]:
        """Build a full runtime inventory snapshot."""
        hw = self._scanner.scan()
        return {
            "timestamp": __import__("time").time(),
            "hardware": hw,
            "agent_version": "1.0.0",
            "python_version": platform.python_version(),
            "os": platform.system(),
        }

    async def sync_to_api(self) -> bool:
        """J-2: POST runtime inventory to API /api/v1/runtimes/inventory."""
        inventory = self.build()
        try:
            import httpx
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.api_url}/api/v1/runtimes/inventory",
                    json=inventory,
                    headers=headers,
                )
                resp.raise_for_status()
                log.info("runtime_inventory_synced", status=resp.status_code)
                return True
        except Exception as exc:
            log.warning("runtime_inventory_sync_failed", error=str(exc))
            return False


# ──────────────────────────────────────────────────────────
# J-3: Local Model Dispatcher
# ──────────────────────────────────────────────────────────

class LocalModelDispatcher:
    """J-3: Route inference requests to local or hosted backend based on VRAM."""

    def __init__(self, api_url: str = "http://localhost:8000", ollama_url: str = "http://localhost:11434"):
        self.api_url = api_url
        self.ollama_url = ollama_url
        self._scanner = HardwareScanner()
        self._hw: Optional[Dict[str, Any]] = None

    def _ensure_hw(self) -> Dict[str, Any]:
        if self._hw is None:
            self._hw = self._scanner.scan()
        return self._hw

    def should_use_local_esmc(self) -> bool:
        """J-3: Use local ESM-C when VRAM ≥ 1.5 GB."""
        hw = self._ensure_hw()
        return hw["gpu"].get("vram_gb", 0) >= HardwareScanner.ESMC_MIN_VRAM_GB

    def should_use_local_ollama(self, model_vram_req_gb: float = 6.0) -> bool:
        """J-3: Use local Ollama when VRAM ≥ required threshold."""
        hw = self._ensure_hw()
        return hw["gpu"].get("vram_gb", 0) >= model_vram_req_gb

    async def dispatch(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route inference task to optimal backend."""
        hw = self._ensure_hw()
        vram = hw["gpu"].get("vram_gb", 0)
        recs = hw.get("dispatch_recommendations", {})

        if task == "esmc_embed":
            if self.should_use_local_esmc():
                return await self._call_local_esmc(payload)
            else:
                return await self._call_api(f"{self.api_url}/api/v1/embeddings/esmc", payload)

        elif task in ("generate", "chat"):
            model = payload.get("model", "biomistral")
            if recs.get("ollama_7b") == "local_gpu":
                return await self._call_ollama(payload)
            elif recs.get("ollama_70b") == "airllm_sharded" and "70b" in model.lower():
                # J-4: AirLLM sharding path
                engine = LocalInferenceEngine(
                    model_path=payload.get("model_path", model),
                    max_vram_gb=vram,
                )
                await engine.load()
                return await engine.generate(payload.get("prompt", ""), payload.get("max_tokens", 256))
            else:
                return await self._call_api(f"{self.api_url}/api/v1/inference/generate", payload)
        else:
            return await self._call_api(f"{self.api_url}/api/v1/inference/{task}", payload)

    async def _call_local_esmc(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call local ESM-C via engine embed."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self.api_url}/api/v1/embeddings/esmc-local", json=payload)
                return resp.json()
        except Exception as e:
            log.warning("local_esmc_failed_fallback", error=str(e))
            return await self._call_api(f"{self.api_url}/api/v1/embeddings/esmc", payload)

    async def _call_ollama(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.ollama_url}/api/generate", json=payload)
                return resp.json()
        except Exception as e:
            log.warning("ollama_failed", error=str(e))
            return {"error": str(e), "status": "degraded"}

    async def _call_api(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload)
                return resp.json()
        except Exception as e:
            log.warning("api_call_failed", url=url, error=str(e))
            return {"error": str(e), "status": "degraded"}
