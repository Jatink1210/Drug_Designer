"""Enhanced base connector using ResilientClient + two-tier cache + provenance."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import structlog

from core.http_client import ResilientClient, payload_hash
from core.cache import cache_key, two_tier_get, two_tier_put
from core.provenance import ProvenanceRecord

log = structlog.get_logger()

DEFAULT_CACHE_TTL = 86400  # 24h


class BaseConnector(ABC):
    """All connectors: cached search + fetch_by_id + normalize + evidence extraction."""

    name: str = "base"
    cache_ttl: float = DEFAULT_CACHE_TTL

    def __init__(self) -> None:
        self._client = ResilientClient()

    async def close(self) -> None:
        await self._client.close()

    # ── HTTP helpers (cached) ─────────────────────────────
    async def _cached_get(
        self, url: str, params: Optional[Dict[str, Any]] = None, extra_key: str = ""
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        key = cache_key(self.name, url, str(params) + extra_key)
        cached = two_tier_get(key)
        if cached is not None:
            return cached, {"cache_hit": True, "source": self.name}
        body, meta = await self._client.get(url, params=params)
        if body is not None:
            phash = payload_hash(body)
            two_tier_put(key, self.name, url, body, ttl=self.cache_ttl, payload_hash=phash)
            meta["payload_hash"] = phash
        meta["source"] = self.name
        return body, meta

    async def _cached_post(
        self, url: str, json_body: Optional[Dict[str, Any]] = None, extra_key: str = ""
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        key = cache_key(self.name, url, str(json_body) + extra_key)
        cached = two_tier_get(key)
        if cached is not None:
            return cached, {"cache_hit": True, "source": self.name}
        body, meta = await self._client.post(url, json_body=json_body)
        if body is not None:
            phash = payload_hash(body)
            two_tier_put(key, self.name, url, body, ttl=self.cache_ttl, payload_hash=phash)
            meta["payload_hash"] = phash
        meta["source"] = self.name
        return body, meta

    def _prov(
        self, url: str = "", phash: str = "",
        confidence: float = 1.0, reasoning: str = "", ext_id: str = "",
    ) -> ProvenanceRecord:
        return ProvenanceRecord.from_connector(
            source=self.name, url=url, payload_hash=phash,
            confidence=confidence, reasoning=reasoning, external_id=ext_id,
        )

    # ── Abstract interface ────────────────────────────────
    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search and return dicts (legacy) or normalized entities."""
        ...

    def normalize(self, raw_data: Dict[str, Any]) -> Any:
        """Normalize raw API data into canonical EntityBase schemas. Override in subclasses."""
        return raw_data

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single entity by canonical ID."""
        return None

    async def count(self, query: str) -> Optional[int]:
        """Return total hit count for a query."""
        return None

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """Extract evidence records linked to an entity."""
        return []
