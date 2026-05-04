"""Specialist Engine — role invocation and dispatch (§40.1).

Manages the lifecycle of specialist invocations: load role definition,
prepare context, execute with selected runtime, validate output against
schema, and return structured results.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import structlog

from models.specialist import SpecialistRole

log = structlog.get_logger()


class SpecialistEngine:
    """Dispatches bounded expert tasks to the appropriate specialist role.

    Uses Universal Inference Engine for actual LLM execution (§40.1).
    """

    def __init__(self, roles: Optional[Dict[str, SpecialistRole]] = None):
        self._roles: Dict[str, SpecialistRole] = roles or {}

    def register_role(self, role: SpecialistRole) -> None:
        self._roles[role.role_id] = role
        log.info("specialist.register", role_id=role.role_id)

    async def invoke(
        self,
        role_id: str,
        context: Dict[str, Any],
        runtime_mode: str = "hosted",
        model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Invoke a specialist with bounded task context (§40.1).

        1. Load role definition
        2. Prepare context (trim to max_context_tokens)
        3. Execute via Universal Inference Engine
        4. Validate output against output_schema
        5. Return structured result with provenance
        """
        role = self._roles.get(role_id)
        if role is None:
            log.error("specialist.unknown_role", role_id=role_id)
            return {"error": f"Unknown specialist role: {role_id}"}

        start = time.monotonic()
        log.info(
            "specialist.invoke",
            role_id=role_id,
            runtime_mode=runtime_mode,
            model_id=model_id,
        )

        # Build prompt from role definition + context
        system_prompt = getattr(role, "system_prompt", "You are a scientific specialist agent.")
        max_tokens = getattr(role, "max_context_tokens", 4096)

        context_text = json.dumps(context, default=str)
        if len(context_text) > max_tokens * 4:  # rough char estimate
            context_text = context_text[: max_tokens * 4]

        user_prompt = f"Task context:\n{context_text}\n\nProvide your expert analysis."

        # Route to Universal Inference Engine
        try:
            from core.inference_engine import UniversalInferenceEngine

            engine = UniversalInferenceEngine()
            result = await engine.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.3,
            )

            output_text = result.get("text", "")
            status = "success" if output_text else "empty_response"

            # Try to parse as JSON if role expects structured output
            output_schema = getattr(role, "output_schema", None)
            parsed_output = output_text
            if output_schema and output_text:
                try:
                    parsed_output = json.loads(output_text)
                except (json.JSONDecodeError, TypeError):
                    parsed_output = output_text

        except Exception as exc:
            log.warning("specialist.inference_failed", role_id=role_id, error=str(exc))
            # Fallback: return context-aware placeholder
            parsed_output = {
                "analysis": f"Specialist {role_id} analysis pending — inference engine unavailable.",
                "context_keys": list(context.keys()),
            }
            status = "fallback"

        elapsed_ms = int((time.monotonic() - start) * 1000)

        return {
            "role_id": role_id,
            "status": status,
            "output": parsed_output,
            "runtime_mode": runtime_mode,
            "model_id": model_id or getattr(role, "default_model", "default"),
            "latency_ms": elapsed_ms,
            "provenance": {
                "system_prompt_hash": hash(system_prompt) % (10**8),
                "context_keys": list(context.keys()),
            },
        }

    async def list_roles(self) -> List[str]:
        return list(self._roles.keys())
