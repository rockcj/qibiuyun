"""Async cache service – Redis when available, in-memory fallback."""

import json
import time
from typing import Any, Optional

import redis.asyncio as aioredis

from config import settings


class InMemoryCache:
    """Simple in-memory cache with TTL support for local development."""

    def __init__(self):
        self._store: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: str, ex: int = 3600) -> None:
        self._store[key] = (time.monotonic() + ex, value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def ping(self) -> bool:
        return True


class CacheService:
    """Unified cache interface (Redis or in-memory)."""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._fallback = InMemoryCache()

    async def connect(self):
        """Connect to Redis if remote URL configured, else in-memory fallback."""
        # Auto-detect: connect if not localhost
        is_local = "localhost" in settings.redis_url or "127.0.0.1" in settings.redis_url
        if is_local and not settings.redis_url.startswith("redis://:"):
            print("[Cache] Using in-memory fallback (local dev)")
            return
        try:
            self._redis = aioredis.from_url(settings.redis_url, socket_connect_timeout=5)
            await self._redis.ping()
            print(f"[Cache] Redis connected: {settings.redis_url}")
        except Exception as exc:
            print(f"[Cache] Redis unavailable ({exc}), using fallback")
            self._redis = None

    async def disconnect(self):
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def get(self, key: str) -> Optional[str]:
        if self._redis:
            try:
                return await self._redis.get(key)
            except Exception:
                pass
        return await self._fallback.get(key)

    async def set(self, key: str, value: str, ex: int = 3600) -> None:
        if self._redis:
            try:
                await self._redis.set(key, value, ex=ex)
                return
            except Exception:
                pass
        await self._fallback.set(key, value, ex=ex)

    async def delete(self, key: str) -> None:
        if self._redis:
            try:
                await self._redis.delete(key)
                return
            except Exception:
                pass
        await self._fallback.delete(key)

    async def ping(self) -> bool:
        if self._redis:
            try:
                return await self._redis.ping()
            except Exception:
                pass
        return await self._fallback.ping()


# Global singleton
cache = CacheService()
