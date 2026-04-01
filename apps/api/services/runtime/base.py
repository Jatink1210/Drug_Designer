"""Base interface for all LLM runtimes."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseRuntime(ABC):
    """Abstract interface for LLM inference engines."""

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Standard chat completions."""
        pass

    @abstractmethod
    async def embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Generate text embeddings."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check runtime status and loaded models."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """e.g. ['chat', 'embeddings', 'streaming']"""
        pass
