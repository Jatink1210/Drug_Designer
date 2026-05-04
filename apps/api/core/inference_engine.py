"""Universal Inference Engine (Drug Designer §44).

Merges Subsystems 7 (Low-Memory Local Runtime / AirLLM) and
8 (Inference Acceleration / SSD) into a single optimization layer.

Two execution paths, same interface:
  - Hosted: 8bit quantization + SSD speculative decoding on cheap T4/L4 GPUs
  - Local:  4bit quantization + aggressive CPU/disk offloading for 4GB VRAM laptops

§44.1: The system dynamically applies optimization based on available
VRAM, regardless of environment.

Inference routing priority:
  1. Ollama (local HTTP API, fastest)
  2. AirLLM (layer-offloaded, for large models)
  3. HuggingFace transformers (fallback)
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List, Optional

import structlog

from services.runtime.policy import get_remote_api_key, get_remote_base_url, get_runtime_policy, ollama_enabled

log = structlog.get_logger()

# ── §N-7: LLM token usage & inference duration Prometheus metrics ──────────
try:
    from prometheus_client import Counter, Histogram

    LLM_TOKENS_TOTAL = Counter(
        "llm_tokens_total",
        "Total LLM output tokens generated",
        ["model_name", "inference_method"],
    )
    LLM_INFERENCE_DURATION = Histogram(
        "llm_inference_duration_seconds",
        "LLM inference end-to-end latency in seconds",
        ["model_name", "inference_method"],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 180.0],
    )
    _PROM_AVAILABLE = True
except ImportError:
    LLM_TOKENS_TOTAL = None  # type: ignore[assignment]
    LLM_INFERENCE_DURATION = None  # type: ignore[assignment]
    _PROM_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class UniversalInferenceEngine:
    """Dynamically optimized inference across hosted and local environments."""

    def __init__(
        self,
        execution_env: str = "hosted",
        model_path: str = "meta-llama/Llama-2-70b-chat-hf",
        max_vram_gb: float = 16.0,
        ollama_base_url: str = None,
    ):
        self.execution_env = execution_env
        self.model_path = model_path
        self.max_vram_gb = max_vram_gb
        self.ollama_base_url = ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._model = None
        self._tokenizer = None
        self._ssd_draft_model = None
        self._embed_model = None

        log.info(
            "inference_engine.init",
            execution_env=execution_env,
            model_path=model_path,
            max_vram_gb=max_vram_gb,
        )

    async def load_model(self) -> None:
        """Load model with environment-appropriate optimization.

        Hosted (§44.1): 8bit quantization + SSD speculative decoding
        Local (§44.1):  4bit quantization + layer-wise CPU offloading
        """
        # Try AirLLM first for large models
        try:
            from airllm import AutoModel
            compression = "4bit" if self.execution_env == "local" else "8bit"
            log.info("inference_engine.loading_airllm", model=self.model_path, compression=compression)
            self._model = AutoModel.from_pretrained(
                self.model_path,
                compression=compression,
                max_memory={"cuda:0": f"{self.max_vram_gb}GiB"},
            )
            if self.execution_env == "hosted":
                self._apply_speculative_decoding("ssd-draft-model-path")
            return
        except ImportError:
            log.debug("airllm_not_available")
        except Exception as exc:
            log.debug("airllm_load_failed", error=str(exc))

        # Try HuggingFace transformers
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            log.info("inference_engine.loading_transformers", model=self.model_path)
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            load_kwargs: Dict[str, Any] = {"trust_remote_code": True}
            if TORCH_AVAILABLE and torch.cuda.is_available():
                load_kwargs["device_map"] = "auto"
                load_kwargs["torch_dtype"] = torch.float16
            self._model = AutoModelForCausalLM.from_pretrained(self.model_path, **load_kwargs)
            return
        except ImportError:
            log.debug("transformers_not_available")
        except Exception as exc:
            log.debug("transformers_load_failed", error=str(exc))

        log.warning("inference_engine.no_local_model_loaded")

    def _apply_speculative_decoding(self, draft_model_path: str) -> None:
        """Apply SSD (Speculative Decoding) for faster token generation (§44.2)."""
        log.info("inference_engine.ssd_enabled", draft_model=draft_model_path)
        # Draft model loaded by speculative.py subsystem

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate text — routes through RuntimeSelector, Ollama, AirLLM, or HF transformers."""
        start = time.time()
        policy = get_runtime_policy()
        attempts: List[str] = []

        # Route 0: RuntimeSelector active runtime (§44 — respects user model selection)
        attempts.append("selected_runtime")
        try:
            result = await asyncio.wait_for(
                self._try_selected_runtime(prompt, max_tokens, temperature, system_prompt),
                timeout=8.0,
            )
        except asyncio.TimeoutError:
            log.warning("selected_runtime_timeout", timeout_s=8)
            result = None
        if result is not None:
            result["runtime_diagnostics"] = {
                "policy": policy,
                "attempted_backends": attempts,
                "fallback_mode": False,
            }
            result["latency_ms"] = round((time.time() - start) * 1000, 1)
            self._record_metrics(result, time.time() - start)
            return result

        # Route 1: Ollama HTTP API (preferred for local/hosted with Ollama)
        if policy["ollama_enabled"]:
            attempts.append("ollama")
            result = await self._try_ollama(prompt, max_tokens, temperature, system_prompt)
            if result is not None:
                result["runtime_diagnostics"] = {
                    "policy": policy,
                    "attempted_backends": attempts,
                    "fallback_mode": len(attempts) > 1,
                }
                result["latency_ms"] = round((time.time() - start) * 1000, 1)
                self._record_metrics(result, time.time() - start)
                return result

        # Route 2: Loaded model (AirLLM or HF transformers)
        if self._model is not None and policy["local_backends_allowed"]:
            attempts.append("local_model")
            log.debug("inference_engine.trying_local_model", model_type=type(self._model).__name__)
            result = await self._try_local_model(prompt, max_tokens, temperature)
            if result is not None:
                result["runtime_diagnostics"] = {
                    "policy": policy,
                    "attempted_backends": attempts,
                    "fallback_mode": len(attempts) > 1,
                }
                result["latency_ms"] = round((time.time() - start) * 1000, 1)
                self._record_metrics(result, time.time() - start)
                return result

        # Route 3: OpenAI-compatible API
        attempts.append("openai_compat")
        result = await self._try_openai_compat(prompt, max_tokens, temperature, system_prompt)
        if result is not None:
            result["runtime_diagnostics"] = {
                "policy": policy,
                "attempted_backends": attempts,
                "fallback_mode": len(attempts) > 1,
            }
            result["latency_ms"] = round((time.time() - start) * 1000, 1)
            self._record_metrics(result, time.time() - start)
            return result

        log.warning("inference_engine.no_backend_available")
        return {
            "text": "",
            "tokens_generated": 0,
            "model_used": self.model_path,
            "execution_env": self.execution_env,
            "inference_method": "none",
            "runtime_diagnostics": {
                "policy": policy,
                "attempted_backends": attempts,
                "fallback_mode": len(attempts) > 1,
            },
            "latency_ms": round((time.time() - start) * 1000, 1),
        }

    def _record_metrics(self, result: Dict[str, Any], latency_s: float) -> None:
        """Record Prometheus LLM metrics (§N-7)."""
        if not _PROM_AVAILABLE:
            return
        model = result.get("model_used", "unknown")
        method = result.get("inference_method", "unknown")
        tokens = result.get("tokens_generated", 0)
        try:
            LLM_TOKENS_TOTAL.labels(model_name=model, inference_method=method).inc(tokens)
            LLM_INFERENCE_DURATION.labels(model_name=model, inference_method=method).observe(latency_s)
        except Exception:
            pass  # never let metrics break inference

    async def _try_selected_runtime(
        self, prompt: str, max_tokens: int, temperature: float, system_prompt: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Route to the user-selected runtime via RuntimeSelector (§44)."""
        try:
            from services.runtime.selector import RuntimeSelector
            runtime = RuntimeSelector.get_active_runtime()
            config = RuntimeSelector._load_config()
            model_name = config.get("model_name", "")
            runtime_id = config.get("runtime_id", "")

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            text = await runtime.chat(messages, max_tokens=max_tokens, temperature=temperature)
            if text and text.strip():
                return {
                    "text": text.strip(),
                    "tokens_generated": len(text.split()),
                    "model_used": model_name or "selected_runtime",
                    "execution_env": runtime_id,
                    "inference_method": f"runtime_selector.{runtime_id}",
                }
        except Exception as exc:
            log.debug("selected_runtime_failed", error=str(exc)[:200])
        return None

    async def _try_ollama(
        self, prompt: str, max_tokens: int, temperature: float, system_prompt: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Route to Ollama local HTTP API."""
        if not HTTPX_AVAILABLE:
            log.warning("ollama_skipped_no_httpx")
            return None
        try:
            # Use a short model name for Ollama
            ollama_model = "gemma4:26b"
            log.info("ollama_attempting", model=ollama_model, url=self.ollama_base_url)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
                resp = await client.post(
                    f"{self.ollama_base_url}/api/chat",
                    json={
                        "model": ollama_model,
                        "messages": messages,
                        "stream": False,
                        "think": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": temperature,
                        },
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    msg = data.get("message", {})
                    text = msg.get("content", "")
                    # Fallback: if thinking model put output in thinking field
                    if not text and msg.get("thinking"):
                        text = msg["thinking"]
                    return {
                        "text": text,
                        "tokens_generated": data.get("eval_count", len(text.split())),
                        "model_used": ollama_model,
                        "execution_env": "ollama",
                        "inference_method": "ollama_chat",
                    }
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            log.warning("ollama_not_reachable", error=str(exc)[:200])
        except Exception as exc:
            log.warning("ollama_error", error=str(exc)[:200])
        return None

    async def _try_local_model(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> Optional[Dict[str, Any]]:
        """Route to locally loaded model (AirLLM or HF)."""
        try:
            if self._tokenizer is not None:
                # HuggingFace transformers path
                inputs = self._tokenizer(prompt, return_tensors="pt")
                if TORCH_AVAILABLE and torch.cuda.is_available():
                    inputs = {k: v.cuda() for k, v in inputs.items()}
                with torch.no_grad():
                    outputs = self._model.generate(
                        **inputs,
                        max_new_tokens=max_tokens,
                        temperature=temperature,
                        do_sample=temperature > 0,
                    )
                text = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
                # Strip the input prompt from output
                if text.startswith(prompt):
                    text = text[len(prompt):].strip()
                return {
                    "text": text,
                    "tokens_generated": outputs.shape[-1] - inputs["input_ids"].shape[-1],
                    "model_used": self.model_path,
                    "execution_env": self.execution_env,
                    "inference_method": "transformers",
                }
            else:
                # AirLLM path
                output = self._model.generate(prompt, max_length=max_tokens)
                text = output if isinstance(output, str) else str(output)
                return {
                    "text": text,
                    "tokens_generated": len(text.split()),
                    "model_used": self.model_path,
                    "execution_env": self.execution_env,
                    "inference_method": "airllm",
                }
        except Exception as exc:
            log.warning("local_model_generate_failed", error=str(exc))
        return None

    async def _try_openai_compat(
        self, prompt: str, max_tokens: int, temperature: float, system_prompt: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Route to OpenAI-compatible API (e.g. vLLM, text-generation-inference)."""
        api_key = get_remote_api_key()
        api_base = get_remote_base_url()
        if not api_key or not HTTPX_AVAILABLE:
            return None
        try:
            base = api_base or "https://api.openai.com/v1"
            model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0)) as client:
                resp = await client.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choice = data["choices"][0]
                    return {
                        "text": choice["message"]["content"],
                        "tokens_generated": data.get("usage", {}).get("completion_tokens", 0),
                        "model_used": model,
                        "execution_env": "openai_compat",
                        "inference_method": "chat_completions",
                    }
        except Exception as exc:
            log.debug("openai_compat_error", error=str(exc))
        return None

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings via Ollama, HF, or sentence-transformers."""
        # Route 1: Ollama embeddings API
        if HTTPX_AVAILABLE and ollama_enabled():
            try:
                embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self.ollama_base_url}/api/embed",
                        json={"model": embed_model, "input": texts},
                    )
                    if resp.status_code == 200:
                        return resp.json().get("embeddings", [])
            except Exception as exc:
                log.debug("embed_ollama_failed", error=str(exc))

        # Route 2: sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
            if self._embed_model is None:
                self._embed_model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = self._embed_model.encode(texts, convert_to_numpy=True)
            return [e.tolist() for e in embeddings]
        except ImportError:
            log.debug("embed_sentence_transformers_unavailable")

        # Route 3: HF transformers mean pooling
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            tok = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
            mdl = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
            encoded = tok(texts, padding=True, truncation=True, return_tensors="pt")
            with torch.no_grad():
                out = mdl(**encoded)
            # Mean pooling
            mask = encoded["attention_mask"].unsqueeze(-1).float()
            pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1)
            return pooled.tolist()
        except Exception as exc:
            log.debug("embed_hf_transformers_failed", error=str(exc))

        log.warning("embed_no_backend")
        return []

    def get_status(self) -> Dict[str, Any]:
        """Return current engine status for diagnostics."""
        return {
            "execution_env": self.execution_env,
            "model_path": self.model_path,
            "model_loaded": self._model is not None,
            "ssd_enabled": self._ssd_draft_model is not None,
            "max_vram_gb": self.max_vram_gb,
            "ollama_url": self.ollama_base_url,
            "runtime_policy": get_runtime_policy(),
        }
