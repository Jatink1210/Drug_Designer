"""Policy engine and hardware detector for LLM runtimes.

Reads/writes runtime_config.json for persistence across restarts.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from .airllm import IS_AIRLLM_AVAILABLE, AirLLMRuntime
from .llama_cpp import LlamaCppRuntime
from .remote_openai import RemoteOpenAIRuntime
from .base import BaseRuntime

log = logging.getLogger(__name__)

_active_runtime: Optional[BaseRuntime] = None


class RuntimeSelector:
    """Detects capabilities and provides the optimal active runtime."""

    @classmethod
    def detect_capabilities(cls) -> Dict[str, Any]:
        """Detect CPU cores, RAM, and GPU devices safely."""
        caps: Dict[str, Any] = {
            "cpu_cores": os.cpu_count(),
            "gpu": "unknown",
            "gpu_name": None,
            "vram_gb": 0,
            "airllm_installed": IS_AIRLLM_AVAILABLE,
        }

        try:
            import psutil
            caps["ram_gb"] = round(psutil.virtual_memory().total / (1024 ** 3), 1)
        except ImportError:
            caps["ram_gb"] = 0

        try:
            import torch
            if torch.cuda.is_available():
                caps["gpu"] = "cuda"
                caps["gpu_name"] = torch.cuda.get_device_name(0)
                try:
                    caps["vram_gb"] = round(
                        torch.cuda.get_device_properties(0).total_mem / (1024 ** 3), 1
                    )
                except Exception:
                    log.debug("GPU VRAM detection failed")
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                caps["gpu"] = "mps"
                caps["gpu_name"] = "Apple Silicon"
            else:
                caps["gpu"] = "none"
        except ImportError:
            caps["gpu"] = "none"

        return caps

    @classmethod
    def get_available_runtimes(cls) -> List[Dict[str, Any]]:
        """List all supported runtimes."""
        return [
            {
                "id": "llama.cpp",
                "name": "Local Llama.cpp / Ollama",
                "status": "ready",
                "capabilities": ["chat", "embeddings", "local", "cpu", "gpu"],
            },
            {
                "id": "airllm",
                "name": "AirLLM (Massive Models)",
                "status": "not_implemented" if IS_AIRLLM_AVAILABLE else "not_installed",
                "capabilities": ["local", "split_layer_inference"],
                "note": "AirLLM package detected but chat/embedding interfaces are not yet integrated.",
            },
            {
                "id": "remote",
                "name": "Remote Server (OpenAI Compatible)",
                "status": "ready",
                "capabilities": ["chat", "embeddings", "remote"],
            },
        ]

    @classmethod
    def _config_path(cls) -> str:
        from config import settings
        return os.path.join(settings.local_store_path, "runtime_config.json")

    @classmethod
    def _load_config(cls) -> Dict[str, Any]:
        """Load persisted runtime config, or return defaults."""
        path = cls._config_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                log.debug("Could not read runtime config file")
        return {
            "runtime_id": "llama.cpp",
            "model_name": "",
            "endpoint": "",
            "compute_mode": "auto",
        }

    @classmethod
    def _save_config(cls, config: Dict[str, Any]):
        """Persist runtime config (never save api_key)."""
        path = cls._config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        safe = {k: v for k, v in config.items() if k != "api_key"}
        with open(path, "w") as f:
            json.dump(safe, f, indent=2)

    @classmethod
    def set_active_runtime(
        cls,
        runtime_id: str,
        model_name: str = "",
        endpoint: str = "",
        api_key: str = "",
        compute_mode: str = "auto",
    ) -> BaseRuntime:
        """Select and persist a runtime. Returns the new active runtime."""
        global _active_runtime
        from config import settings

        config = {
            "runtime_id": runtime_id,
            "model_name": model_name,
            "endpoint": endpoint,
            "compute_mode": compute_mode,
        }
        cls._save_config(config)

        runtime = cls._build_runtime(runtime_id, model_name, endpoint, api_key, settings)
        _active_runtime = runtime
        log.info("Active runtime set to: %s (model=%s, compute=%s)", runtime_id, model_name, compute_mode)
        return runtime

    @classmethod
    def _build_runtime(
        cls,
        runtime_id: str,
        model_name: str,
        endpoint: str,
        api_key: str,
        settings: Any,
    ) -> BaseRuntime:
        if runtime_id == "llama.cpp":
            ep = endpoint or settings.ollama_host
            model = model_name or settings.ollama_model
            return LlamaCppRuntime(endpoint=ep, model=model)
        elif runtime_id == "airllm":
            return AirLLMRuntime(model_repo=model_name)
        elif runtime_id == "remote":
            ep = endpoint or "https://api.openai.com/v1"
            key = api_key or settings.openai_api_key
            model = model_name or settings.openai_model
            return RemoteOpenAIRuntime(base_url=ep, api_key=key, model=model)
        else:
            log.warning("Unknown runtime %s, defaulting to llama.cpp", runtime_id)
            return LlamaCppRuntime(
                endpoint=settings.ollama_host, model=settings.ollama_model
            )

    @classmethod
    def get_active_runtime(cls) -> BaseRuntime:
        """Returns the currently selected runtime (singleton, lazy-loaded)."""
        global _active_runtime
        if _active_runtime is not None:
            return _active_runtime

        from config import settings
        config = cls._load_config()
        _active_runtime = cls._build_runtime(
            runtime_id=config.get("runtime_id", "llama.cpp"),
            model_name=config.get("model_name", ""),
            endpoint=config.get("endpoint", ""),
            api_key="",
            settings=settings,
        )
        return _active_runtime

    @classmethod
    def get_active_runtime_id(cls) -> str:
        """Return the ID of the active runtime from persisted config."""
        config = cls._load_config()
        return config.get("runtime_id", "llama.cpp")

    @classmethod
    def get_compute_mode(cls) -> str:
        """Return the current compute mode from persisted config."""
        config = cls._load_config()
        return config.get("compute_mode", "auto")

    @classmethod
    def recommend_compute_mode(cls) -> str:
        """Auto-detect best compute mode based on hardware."""
        caps = cls.detect_capabilities()
        if caps.get("gpu") == "cuda" and caps.get("vram_gb", 0) >= 4:
            return "gpu"
        if caps.get("gpu") == "mps":
            return "gpu"
        return "cpu"

    @classmethod
    def _load_catalog(cls) -> list:
        """Load the models catalog from resources."""
        catalog_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "resources", "models_catalog.json"
        )
        if os.path.exists(catalog_path):
            try:
                with open(catalog_path, "r") as f:
                    return json.load(f)
            except Exception:
                log.debug("Could not read model catalog")
        return []

    @classmethod
    def recommend_model(cls, compute_mode: str = "auto") -> Dict[str, Any]:
        """Recommend the best model for current hardware and compute mode."""
        caps = cls.detect_capabilities()
        mode = compute_mode if compute_mode != "auto" else cls.recommend_compute_mode()
        catalog = cls._load_catalog()

        compatible = []
        for m in catalog:
            model_modes = m.get("compute_modes", ["cpu", "gpu"])
            if mode not in model_modes:
                continue
            if mode == "cpu":
                ram = caps.get("ram_gb", 0)
                if isinstance(ram, (int, float)) and ram < m.get("min_ram_gb", 999):
                    continue
            if mode == "gpu":
                vram = caps.get("vram_gb", 0)
                if isinstance(vram, (int, float)) and vram < m.get("min_vram_gb", 999):
                    continue
            compatible.append(m)

        if not compatible:
            compatible = [
                m for m in catalog
                if m.get("min_ram_gb", 999) <= 8
            ]

        compatible.sort(key=lambda m: (
            0 if "biomedical" in m.get("tags", []) else 1,
            m.get("size_gb", 99),
        ))

        return {
            "compute_mode": mode,
            "recommended_model": compatible[0] if compatible else None,
            "compatible_models": compatible,
            "hardware": caps,
        }

    @classmethod
    def reset(cls):
        """Reset the singleton (for testing)."""
        global _active_runtime
        _active_runtime = None
