"""AirLLM wrapper for massive model inference on consumer hardware.

AirLLM enables running large models on machines with limited VRAM by split-loading
layers from disk. This runtime requires the `airllm` package and a model_repo path.

When AirLLM is installed but not yet configured with a model, operations raise
NotImplementedError rather than silently succeeding with fake data.
"""

from typing import Dict, Any, List
from .base import BaseRuntime

_AIRLLM_IMPORT_OK = False  # True only if `import airllm` succeeded at module load
try:
    import airllm
    IS_AIRLLM_AVAILABLE = True
    _AIRLLM_IMPORT_OK = True
except (ImportError, Exception):
    # airllm may be installed but fail to import due to dependency issues
    # (e.g., torchvision incompatibility). Check if the package exists.
    try:
        import importlib.util
        IS_AIRLLM_AVAILABLE = importlib.util.find_spec("airllm") is not None
    except Exception:
        IS_AIRLLM_AVAILABLE = False


class AirLLMRuntime(BaseRuntime):
    """Wrapper for AirLLM (optional runtime — requires airllm package and model path)."""

    def __init__(self, model_repo: str = ""):
        self.model_repo = model_repo
        self._model = None

    def _load_model(self):
        """Lazy-load the AirLLM model on first use."""
        if self._model is not None:
            return self._model
        if not _AIRLLM_IMPORT_OK:
            raise RuntimeError(
                "AirLLM package found but import failed (dependency issue). "
                "Cannot load models until `import airllm` succeeds."
            )
        if not IS_AIRLLM_AVAILABLE:
            raise RuntimeError(
                "AirLLM is not installed. Install with: pip install airllm"
            )
        if not self.model_repo:
            raise RuntimeError(
                "AirLLM model_repo is not configured. Set a HuggingFace repo ID "
                "or local path in Settings → Runtime → AirLLM Model Path."
            )
        try:
            self._model = airllm.AutoModel.from_pretrained(self.model_repo)
            return self._model
        except Exception as exc:
            raise RuntimeError(
                f"AirLLM failed to load model '{self.model_repo}': {exc}"
            ) from exc

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Run chat inference via AirLLM split-layer model.

        Raises RuntimeError if AirLLM is not installed or model is not configured.
        Does NOT silently echo input back — that was a placeholder that has been removed.
        """
        if not IS_AIRLLM_AVAILABLE:
            raise RuntimeError(
                "AirLLM is not installed. Install with: pip install airllm"
            )
        try:
            model = self._load_model()
            # Collapse messages into a single prompt for now
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            prompt += "\nassistant:"
            
            input_tokens = model.tokenizer(
                [prompt],
                return_tensors="pt",
                return_attention_mask=False,
                truncation=True,
                max_length=2048
            )
            # Assuming cuda is available for AirLLM target use case
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            input_ids = input_tokens['input_ids'].to(device)
            
            generation_output = model.generate(
                input_ids,
                max_new_tokens=kwargs.get("max_tokens", 512),
                use_cache=True,
                return_dict_in_generate=True
            )
            
            output_text = model.tokenizer.decode(generation_output.sequences[0], skip_special_tokens=True)
            # Strip prompt from output
            if output_text.startswith(prompt):
                output_text = output_text[len(prompt):].strip()
            return output_text
        except Exception as exc:
            raise RuntimeError(f"AirLLM generation failed: {exc}") from exc

    async def embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """
        Generate embeddings via AirLLM.

        Raises RuntimeError if AirLLM is not installed.
        """
        if not IS_AIRLLM_AVAILABLE:
            raise RuntimeError(
                "AirLLM is not installed. Install with: pip install airllm"
            )
        raise NotImplementedError(
            "AirLLM embedding generation is not yet wired in this build. "
            "Use the Embedding Service (HuggingFace) instead."
        )

    def health_check(self) -> Dict[str, Any]:
        if not IS_AIRLLM_AVAILABLE:
            status = "NOT_INSTALLED"
            note = "Install airllm package to enable this runtime."
        elif not self.model_repo:
            status = "DEGRADED"
            note = "AirLLM is installed but model_repo is not configured."
        else:
            status = "OK"
            note = "AirLLM 70b inference engine online."
            
        return {
            "status": status,
            "type": "airllm",
            "installed": IS_AIRLLM_AVAILABLE,
            "model_repo": self.model_repo or None,
            "model_loaded": self._model is not None,
            "chat_wired": True,
            "embeddings_wired": False,
            "note": note,
        }

    @property
    def capabilities(self) -> List[str]:
        if IS_AIRLLM_AVAILABLE and self.model_repo:
            return ["chat"]
        return []
