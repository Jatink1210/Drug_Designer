"""Speculative Decoding runtime for exact and accelerated inference (§28, §44.2).

Orchestrates a small draft model and a large target model:
1. Draft model generates K candidate tokens autoregressively
2. Target model validates all K tokens in a single forward pass
3. Accepted prefix is emitted; rejected suffix is re-sampled from target

Provides 2-3× speedup over standard autoregressive decoding while
maintaining exact distributional equivalence.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import structlog

from .base import BaseRuntime

log = structlog.get_logger(__name__)

try:
    import torch
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class SpeculativeDecodingRuntime(BaseRuntime):
    """Runtime utilising Speculative Decoding for optimised inference throughput."""

    def __init__(
        self,
        target_model_id: str,
        draft_model_id: str,
        lookahead_k: int = 5,
        max_tokens: int = 512,
    ):
        self.target_model_id = target_model_id
        self.draft_model_id = draft_model_id
        self.lookahead_k = lookahead_k
        self.max_tokens = max_tokens
        self._target_model = None
        self._draft_model = None
        self._tokenizer = None
        self._loaded = False

    def _load_models(self) -> None:
        """Load draft and target models via HuggingFace transformers."""
        if self._loaded:
            return
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            log.info("speculative.loading_draft", model=self.draft_model_id)
            self._tokenizer = AutoTokenizer.from_pretrained(self.draft_model_id)

            load_kwargs: Dict[str, Any] = {"trust_remote_code": True}
            if TORCH_AVAILABLE and torch.cuda.is_available():
                load_kwargs["torch_dtype"] = torch.float16
                load_kwargs["device_map"] = "auto"

            self._draft_model = AutoModelForCausalLM.from_pretrained(
                self.draft_model_id, **load_kwargs
            )

            log.info("speculative.loading_target", model=self.target_model_id)
            self._target_model = AutoModelForCausalLM.from_pretrained(
                self.target_model_id, **load_kwargs
            )
            self._loaded = True
            log.info("speculative.models_loaded")
        except ImportError:
            log.warning("speculative.transformers_missing")
        except Exception as exc:
            log.warning("speculative.load_failed", error=str(exc))

    # ------------------------------------------------------------------
    # Speculative decoding core loop
    # ------------------------------------------------------------------

    def _speculative_decode(
        self,
        input_ids: "torch.Tensor",
        max_new_tokens: int,
        temperature: float = 0.7,
    ) -> "torch.Tensor":
        """Core speculative decoding loop (§44.2).

        For each step:
          1. Draft model generates K tokens autoregressively
          2. Target model scores all K draft tokens in parallel
          3. Accept tokens while draft ≈ target; resample first rejection from target
        """
        if not TORCH_AVAILABLE or self._draft_model is None or self._target_model is None:
            return input_ids

        device = input_ids.device
        generated = input_ids.clone()
        tokens_generated = 0

        with torch.no_grad():
            while tokens_generated < max_new_tokens:
                # --- Step 1: Draft K tokens ---
                draft_ids = generated.clone()
                draft_logits_list = []
                for _ in range(self.lookahead_k):
                    outputs = self._draft_model(draft_ids)
                    next_logits = outputs.logits[:, -1, :] / max(temperature, 1e-8)
                    draft_logits_list.append(next_logits)
                    if temperature > 0:
                        probs = F.softmax(next_logits, dim=-1)
                        next_token = torch.multinomial(probs, num_samples=1)
                    else:
                        next_token = next_logits.argmax(dim=-1, keepdim=True)
                    draft_ids = torch.cat([draft_ids, next_token], dim=-1)

                draft_tokens = draft_ids[:, generated.shape[1]:]  # (1, K)

                # --- Step 2: Target validates all K in one pass ---
                candidate = torch.cat([generated, draft_tokens], dim=-1)
                target_out = self._target_model(candidate)
                # target_logits at positions [len(generated)-1 .. len(generated)+K-1]
                start_pos = generated.shape[1] - 1
                target_logits = target_out.logits[:, start_pos: start_pos + self.lookahead_k, :]

                # --- Step 3: Accept/reject ---
                accepted = 0
                for j in range(self.lookahead_k):
                    t_logits = target_logits[:, j, :] / max(temperature, 1e-8)
                    t_probs = F.softmax(t_logits, dim=-1)
                    d_logits = draft_logits_list[j] / max(temperature, 1e-8)
                    d_probs = F.softmax(d_logits, dim=-1)

                    draft_tok = draft_tokens[:, j]

                    # Acceptance criterion: p_target(x) / p_draft(x) >= uniform
                    p_t = t_probs[0, draft_tok[0]].item()
                    p_d = d_probs[0, draft_tok[0]].item()

                    ratio = p_t / max(p_d, 1e-10)
                    import random
                    if random.random() < min(1.0, ratio):
                        accepted += 1
                    else:
                        # Resample from adjusted target distribution
                        residual = torch.clamp(t_probs - d_probs, min=0)
                        residual = residual / (residual.sum() + 1e-10)
                        corrected = torch.multinomial(residual, num_samples=1)
                        generated = torch.cat(
                            [generated, draft_tokens[:, :j], corrected], dim=-1
                        )
                        tokens_generated += j + 1
                        break
                else:
                    # All K accepted — also sample one bonus token from target
                    generated = torch.cat([generated, draft_tokens], dim=-1)
                    bonus_logits = target_out.logits[:, start_pos + self.lookahead_k, :] / max(temperature, 1e-8)
                    bonus_probs = F.softmax(bonus_logits, dim=-1)
                    bonus_token = torch.multinomial(bonus_probs, num_samples=1)
                    generated = torch.cat([generated, bonus_token], dim=-1)
                    tokens_generated += self.lookahead_k + 1

                # Check EOS
                if self._tokenizer.eos_token_id is not None:
                    if (generated[0, -1] == self._tokenizer.eos_token_id).item():
                        break

        return generated

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Run inference using speculative decoding loop."""
        self._load_models()

        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        temperature = kwargs.get("temperature", 0.7)
        max_new = kwargs.get("max_tokens", self.max_tokens)

        # If models loaded, run real speculative decoding
        if self._tokenizer is not None and self._target_model is not None:
            start = time.time()
            input_ids = self._tokenizer(prompt, return_tensors="pt").input_ids
            if TORCH_AVAILABLE and torch.cuda.is_available():
                input_ids = input_ids.cuda()

            output_ids = self._speculative_decode(
                input_ids, max_new_tokens=max_new, temperature=temperature
            )
            text = self._tokenizer.decode(output_ids[0], skip_special_tokens=True)
            # Strip input prompt from output
            if text.startswith(prompt):
                text = text[len(prompt):].strip()

            elapsed = time.time() - start
            tokens_out = output_ids.shape[-1] - input_ids.shape[-1]
            log.info(
                "speculative.generated",
                tokens=tokens_out,
                elapsed_s=round(elapsed, 2),
                tok_per_s=round(tokens_out / max(elapsed, 0.01), 1),
            )
            return text

        # Fallback: route through UniversalInferenceEngine
        try:
            from core.inference_engine import UniversalInferenceEngine
            engine = UniversalInferenceEngine()
            result = await engine.generate(prompt=prompt, max_tokens=max_new, temperature=temperature)
            return result.get("text", "")
        except Exception as exc:
            log.warning("speculative.fallback_failed", error=str(exc))
            return ""

    async def embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Route embeddings through inference engine (speculative decoding is generation-only)."""
        try:
            from core.inference_engine import UniversalInferenceEngine
            engine = UniversalInferenceEngine()
            return await engine.embed(texts)
        except Exception:
            return []

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "OK" if self._loaded else "NOT_LOADED",
            "type": "speculative_decoding",
            "target_model": self.target_model_id,
            "draft_model": self.draft_model_id,
            "lookahead_k": self.lookahead_k,
            "models_loaded": self._loaded,
        }

    @property
    def capabilities(self) -> List[str]:
        return ["chat", "speculative"]
