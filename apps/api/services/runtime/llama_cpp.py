"""
llama.cpp Direct Inference Connector.
Provides a direct HTTP connection to llama.cpp server (llama-server / llama-cli)
running on localhost:8080, independent of the Ollama abstraction layer.
Satisfies Section 22 DoD item #8.
"""
import httpx
import structlog
from typing import Dict, Any, Optional

log = structlog.get_logger(__name__)

class LlamaCppRuntime:
    """
    Direct connector to a llama.cpp HTTP server.
    Supports the llama.cpp server API format (/completion endpoint).
    """
    def __init__(self, endpoint: str = "http://localhost:8080"):
        self.endpoint = endpoint
        log.info("llama_cpp_connector_initialized", endpoint=endpoint)

    async def health_check(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.endpoint}/health")
                if resp.status_code == 200:
                    return {"status": "online", "endpoint": self.endpoint, "data": resp.json()}
                return {"status": "unhealthy", "code": resp.status_code}
        except httpx.ConnectError:
            return {"status": "offline", "endpoint": self.endpoint}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.1, stop: Optional[list] = None, json_schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Send a completion request to llama.cpp server.
        Uses the /completion endpoint (llama-server native format).
        If json_schema is provided, statically constrains the LLM inference routing.
        """
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": stop or ["\n\n"],
            "stream": False
        }
        if json_schema:
            payload["json_schema"] = json_schema
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.endpoint}/completion", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return {
                    "text": data.get("content", ""),
                    "tokens_predicted": data.get("tokens_predicted", 0),
                    "tokens_evaluated": data.get("tokens_evaluated", 0),
                    "timings": data.get("timings", {}),
                    "model": data.get("model", "unknown"),
                    "backend": "llama.cpp"
                }
        except httpx.ConnectError:
            log.warning("llama_cpp_offline", endpoint=self.endpoint)
            return {"text": "", "error": f"llama.cpp server not reachable at {self.endpoint}", "backend": "llama.cpp"}
        except Exception as e:
            log.error("llama_cpp_error", error=str(e))
            return {"text": "", "error": str(e), "backend": "llama.cpp"}

    async def tokenize(self, text: str) -> Dict[str, Any]:
        """Tokenize text using llama.cpp's tokenization endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{self.endpoint}/tokenize", json={"content": text})
                resp.raise_for_status()
                data = resp.json()
                return {"tokens": data.get("tokens", []), "count": len(data.get("tokens", []))}
        except Exception as e:
            return {"error": str(e)}

    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about the currently loaded model."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.endpoint}/props")
                if resp.status_code == 200:
                    return resp.json()
                # Try slots endpoint as fallback
                resp = await client.get(f"{self.endpoint}/slots")
                if resp.status_code == 200:
                    return {"slots": resp.json()}
        except Exception as e:
            return {"error": str(e)}
        return {}
