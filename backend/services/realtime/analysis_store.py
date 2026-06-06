"""会话级分析数据存储 — 基于 cache_service（Redis 不可用时自动内存兜底）。

存储 key: analysis:{session_id}
结构:
{
  "corrections": [...],      # 所有语法纠正记录（含轻微）
  "fillerCounts": {"um": 2}, # 语气词累计计数
  "pronunciation": [...]     # 每轮发音分析
}
"""

import json
from typing import Any, Optional

from config import settings
from services.cache_service import cache


def _cache_key(session_id: str) -> str:
    """生成会话分析数据的 cache key。"""
    return f"analysis:{session_id}"


async def _load(session_id: str) -> dict:
    """从 cache 读取分析数据，不存在则返回空结构。"""
    raw = await cache.get(_cache_key(session_id))
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return {"corrections": [], "fillerCounts": {}, "pronunciation": []}


async def _save(session_id: str, data: dict) -> None:
    """写入 cache，TTL 与会话一致。"""
    await cache.set(
        _cache_key(session_id),
        json.dumps(data, ensure_ascii=False),
        ex=settings.session_ttl_seconds,
    )


async def append_correction(session_id: str, record: dict) -> None:
    """追加一条语法纠正记录。"""
    data = await _load(session_id)
    data["corrections"].append(record)
    await _save(session_id, data)


async def incr_filler(session_id: str, filler_word: str, count: int = 1) -> dict:
    """累加语气词计数，返回更新后的 fillerCounts。"""
    data = await _load(session_id)
    counts = data.setdefault("fillerCounts", {})
    counts[filler_word] = counts.get(filler_word, 0) + count
    await _save(session_id, data)
    return counts


async def append_pronunciation(session_id: str, record: dict) -> None:
    """追加一条发音分析记录。"""
    data = await _load(session_id)
    data["pronunciation"].append(record)
    await _save(session_id, data)


async def get_summary(session_id: str) -> Optional[dict]:
    """获取会话分析汇总，无数据时返回 None。"""
    data = await _load(session_id)
    if not data["corrections"] and not data["fillerCounts"] and not data["pronunciation"]:
        return None
    return data
