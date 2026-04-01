"""Remote OpenAI-compatible runtime client."""

import httpx
from typing import Dict, Any, List
from .base import BaseRuntime

class RemoteOpenAIRuntime(BaseRuntime):
    """Client for any OpenAI-compatible remote endpoint (e.g. OpenAI, vLLM, Ollama)."""
    
    def __init__(self, base_url: str, api_key: str = "", model: str = ""):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": messages,
                    **kwargs
                },
                timeout=60.0
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json={
                    "model": self.model,
                    "input": texts,
                    **kwargs
                },
                timeout=30.0
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            return [d["embedding"] for d in data]

    def health_check(self) -> Dict[str, Any]:
        """Perform a real HTTP check against the configured endpoint.

        Attempts GET /models (standard OpenAI endpoint).
        Returns status=PASS only if the endpoint responds with HTTP < 400.
        """
        if not self.base_url:
            return {
                "status": "FAIL",
                "type": "remote_openai",
                "endpoint": "",
                "error": "No endpoint URL configured.",
            }
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
                if resp.status_code < 400:
                    return {
                        "status": "PASS",
                        "type": "remote_openai",
                        "endpoint": self.base_url,
                        "model": self.model,
                        "http_status": resp.status_code,
                    }
                return {
                    "status": "FAIL",
                    "type": "remote_openai",
                    "endpoint": self.base_url,
                    "error": f"Endpoint returned HTTP {resp.status_code}",
                }
        except httpx.ConnectError as exc:
            return {"status": "FAIL", "type": "remote_openai",
                    "endpoint": self.base_url, "error": f"Connection refused: {exc}"}
        except httpx.TimeoutException:
            return {"status": "FAIL", "type": "remote_openai",
                    "endpoint": self.base_url, "error": "Connection timed out (5s)"}
        except Exception as exc:
            return {"status": "FAIL", "type": "remote_openai",
                    "endpoint": self.base_url, "error": str(exc)}

    @property
    def capabilities(self) -> List[str]:
        return ["chat", "embeddings", "remote"]
