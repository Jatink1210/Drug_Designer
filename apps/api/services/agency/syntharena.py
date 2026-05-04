"""
SynthArena Competitive Multi-Model Orchestrator.
Executes physical side-by-side LLM competitive swarms, tracking Tokens-Per-Second (TPS)
and mechanical decision divergence between separate Local LLM architectures concurrently.
"""

import httpx
import asyncio
import time
from typing import Dict, Any
import structlog

from services.runtime.policy import ollama_enabled

log = structlog.get_logger(__name__)

class SynthArenaScorer:
    def __init__(self, endpoint: str = "http://localhost:11434/api/chat"):
        self.endpoint = endpoint
        log.info("syntharena_scorer_online", target_bus=endpoint)
        
    async def _run_model(self, model: str, prompt: str) -> Dict[str, Any]:
        """Dispatches an absolute physical token prompt to the isolated hardware port."""
        start = time.monotonic()
        try:
            if not ollama_enabled():
                return {"model": model, "text": "[LLM_DISABLED_BY_POLICY]", "speed_tps": 0.0}
            async with httpx.AsyncClient(timeout=35.0) as client:
                res = await client.post(self.endpoint, json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False})
                res.raise_for_status()
                
                text = res.json().get("message", {}).get("content", "")
                tok_count = len(text.split())
                dur = time.monotonic() - start
                
                return {
                    "model": model, 
                    "text": text, 
                    "speed_tps": round(tok_count / max(dur, 0.1), 1)
                }
        except httpx.ConnectError:
            return {"model": model, "text": "[LLM_DAEMON_OFFLINE]", "speed_tps": 0.0}
        except Exception as e:
            return {"model": model, "text": f"[INFERENCE_CRASH] {str(e)}", "speed_tps": 0.0}

    async def execute_battle(self, prompt: str, model_a: str = "llama3-8b", model_b: str = "mistral-7b") -> Dict[str, Any]:
        """
        Mechanically forces two models to execute identical contextual reasoning logic,
        then mathematically calculates topological token divergence variance between them.
        """
        log.info("syntharena_execution_started", model_a=model_a, model_b=model_b)
        res_a, res_b = await asyncio.gather(self._run_model(model_a, prompt), self._run_model(model_b, prompt))
        
        # Calculate semantic length divergence representing decision variance (proxy for cognitive agreement)
        len_a, len_b = len(res_a["text"]), len(res_b["text"])
        divergence = round(abs(len_a - len_b) / max(len_a, len_b, 1), 2)
        
        # Speed heuristics prioritization
        winner = model_a if res_a["speed_tps"] > res_b["speed_tps"] else model_b
        
        return {
            "status": "syntharena_battle_complete",
            "prompt": prompt,
            "arena_results": [res_a, res_b],
            "cognitive_divergence_delta": divergence,
            "fastest_tps": winner
        }
