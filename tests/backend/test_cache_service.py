"""缓存服务单元测试 – 内存兜底、TTL、读写。"""

import asyncio

import pytest

from services.cache_service import InMemoryCache


class TestInMemoryCache:
    """内存缓存兜底实现测试。"""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """应能正常写入和读取。"""
        cache = InMemoryCache()
        await cache.set("key1", "value1", ex=60)
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing_key_returns_none(self):
        """不存在的 key 应返回 None。"""
        cache = InMemoryCache()
        assert await cache.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_delete_removes_key(self):
        """delete 应移除指定 key。"""
        cache = InMemoryCache()
        await cache.set("key1", "value1")
        await cache.delete("key1")
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """过期后应返回 None。"""
        cache = InMemoryCache()
        await cache.set("key1", "value1", ex=1)
        await asyncio.sleep(1.1)
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_ping_returns_true(self):
        """健康检查应返回 True。"""
        cache = InMemoryCache()
        assert await cache.ping() is True
