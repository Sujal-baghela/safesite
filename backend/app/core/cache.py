"""
Redis cache client with typed helpers.

Usage:
    from app.core.cache import cache

    await cache.set("key", value, ttl=60)
    value = await cache.get("key")
    await cache.delete("key")
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# TTL constants (seconds) — tune these for your query patterns
TTL_VIOLATIONS_COUNT = 60       # violation counts per site
TTL_ANALYTICS = 300             # charts / aggregates (5 min)
TTL_CAMERA_LIST = 300           # camera list per company
TTL_USER_SESSION = 900          # user permissions cache (15 min)
TTL_R2_SIGNED_URL = 3000        # signed URLs (50 min < R2's 1-hour expiry)


class RedisCache:
    """Thin async wrapper around redis-py with JSON serialisation."""

    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Initialise the Redis connection pool."""
        self._client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )

    async def disconnect(self) -> None:
        """Close all connections in the pool."""
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("RedisCache not initialised — call connect() first.")
        return self._client

    # -------------------------------------------------------------------------
    # Core operations
    # -------------------------------------------------------------------------

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Serialise *value* to JSON and store it under *key*."""
        try:
            serialised = json.dumps(value, default=str)
            if ttl:
                await self.client.setex(key, ttl, serialised)
            else:
                await self.client.set(key, serialised)
        except Exception:
            logger.warning("Cache SET failed for key=%s", key, exc_info=True)

    async def get(self, key: str) -> Any | None:
        """Return the deserialised value for *key*, or None on miss/error."""
        try:
            raw = await self.client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:
            logger.warning("Cache GET failed for key=%s", key, exc_info=True)
            return None

    async def delete(self, key: str) -> None:
        """Delete a single key."""
        try:
            await self.client.delete(key)
        except Exception:
            logger.warning("Cache DELETE failed for key=%s", key, exc_info=True)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching *pattern*. Returns count deleted."""
        try:
            keys = await self.client.keys(pattern)
            if keys:
                return await self.client.delete(*keys)
            return 0
        except Exception:
            logger.warning("Cache DELETE_PATTERN failed for pattern=%s", pattern, exc_info=True)
            return 0

    async def exists(self, key: str) -> bool:
        """Return True if the key exists in Redis."""
        try:
            return bool(await self.client.exists(key))
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Domain-specific key builders
    # -------------------------------------------------------------------------

    @staticmethod
    def key_violations_count(site_id: str) -> str:
        return f"violations:count:{site_id}"

    @staticmethod
    def key_analytics(site_id: str, period: str) -> str:
        return f"analytics:{site_id}:{period}"

    @staticmethod
    def key_cameras(company_id: str) -> str:
        return f"cameras:company:{company_id}"

    @staticmethod
    def key_user_permissions(user_id: str) -> str:
        return f"user:perms:{user_id}"

    @staticmethod
    def key_signed_url(object_key: str) -> str:
        return f"r2:signed:{object_key}"


# Singleton — import this everywhere
cache = RedisCache()
