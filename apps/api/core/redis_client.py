"""Shared Redis client for auth tokens, rate limits, and caching (§55.1)."""

import redis.asyncio as aioredis
from config import settings

_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return a shared async Redis connection, creating it lazily."""
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _pool


async def close_redis() -> None:
    """Gracefully close the Redis pool on shutdown."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
