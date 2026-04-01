"""
Runtime Fabric — CPU/GPU/Auto selection with persistence and fallback logic.
Satisfies Section 14.1 of the specification.
"""
import json
import os
import logging
from typing import Dict, Any, Optional
from enum import Enum

log = logging.getLogger(__name__)

class RuntimeMode(str, Enum):
    CPU = "cpu"
    GPU = "gpu"
    AUTO = "auto"

class RuntimeFabric:
    """
    Manages runtime lane selection (CPU/GPU/Auto) with persistent configuration
    and automatic fallback logic.
    """
    PERSIST_PATH = "data/runtime_config.json"

    def __init__(self):
        self.config = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.PERSIST_PATH):
            try:
                with open(self.PERSIST_PATH) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "mode": RuntimeMode.AUTO.value,
            "hosted_endpoint": "http://localhost:8000",
            "local_agent_endpoint": "http://localhost:4133",
            "llm_endpoint": "http://localhost:11434",
            "llama_cpp_endpoint": "http://localhost:8080",
            "fallback_order": ["local_gpu", "local_cpu", "hosted"],
            "model_preferences": {
                "chat": "llama3",
                "retrieval": "nomic-embed-text",
                "summarization": "llama3",
                "disease_intelligence": "llama3",
                "dossier": "llama3"
            }
        }

    def _save(self):
        os.makedirs(os.path.dirname(self.PERSIST_PATH) or ".", exist_ok=True)
        with open(self.PERSIST_PATH, "w") as f:
            json.dump(self.config, f, indent=2)

    def get_mode(self) -> str:
        return self.config.get("mode", RuntimeMode.AUTO.value)

    def set_mode(self, mode: str):
        if mode not in [m.value for m in RuntimeMode]:
            raise ValueError(f"Invalid mode: {mode}. Must be cpu, gpu, or auto.")
        self.config["mode"] = mode
        self._save()
        log.info(f"Runtime mode set to: {mode}")

    def get_inference_endpoint(self) -> str:
        """Returns the best inference endpoint based on current mode and availability."""
        mode = self.get_mode()
        if mode == RuntimeMode.GPU.value:
            return self.config.get("local_agent_endpoint", "http://localhost:4133")
        elif mode == RuntimeMode.CPU.value:
            return self.config.get("llm_endpoint", "http://localhost:11434")
        else:  # AUTO
            # Try GPU first, then CPU, then hosted
            import httpx
            for endpoint_key in ["local_agent_endpoint", "llm_endpoint", "hosted_endpoint"]:
                ep = self.config.get(endpoint_key, "")
                try:
                    resp = httpx.get(f"{ep}/health" if "/health" not in ep else ep, timeout=2.0)
                    if resp.status_code == 200:
                        return ep
                except Exception:
                    continue
            return self.config.get("llm_endpoint", "http://localhost:11434")

    def get_config(self) -> Dict[str, Any]:
        return {**self.config, "resolved_endpoint": self.get_inference_endpoint()}

    def update_config(self, updates: Dict[str, Any]):
        self.config.update(updates)
        self._save()

    def get_model_for_role(self, role: str) -> str:
        return self.config.get("model_preferences", {}).get(role, "llama3")

    def set_model_for_role(self, role: str, model: str):
        self.config.setdefault("model_preferences", {})[role] = model
        self._save()


_fabric: Optional[RuntimeFabric] = None

def get_runtime_fabric() -> RuntimeFabric:
    global _fabric
    if _fabric is None:
        _fabric = RuntimeFabric()
    return _fabric
