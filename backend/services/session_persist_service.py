"""会话数据持久化 — 将 cache 中的分析与会话 transcript 写入 Interview 表。"""

import json
import uuid
from typing import Any, Optional

from services.cache_service import cache
from services.realtime import analysis_store


async def flush_session_data(session_id: str) -> None:
    """把分析汇总、transcript 与整场录音地址刷入 Interview 表。"""
    from database import async_session_factory
    from models.base import Interview

    try:
        interview_uuid = uuid.UUID(session_id)
    except ValueError:
        return

    # 分析数据（cache 为空时也写入空结构，便于报告页读取）
    analysis_data = await analysis_store.load(session_id)

    # transcript 与整场录音元数据
    transcript_turns: list[dict] = []
    full_audio_url: Optional[str] = None
    full_audio_storage_key: Optional[str] = None
    full_audio_storage_provider: Optional[str] = None
    try:
        raw = await cache.get(f"session:{session_id}")
        if raw:
            session_data = json.loads(raw)
            transcript_turns = session_data.get("transcriptTurns", [])
            full_audio_url = session_data.get("fullAudioUrl")
            full_audio_storage_key = session_data.get("fullAudioStorageKey")
            full_audio_storage_provider = session_data.get("fullAudioStorageProvider")
    except Exception:
        pass

    transcript_payload: dict[str, Any] = {"turns": transcript_turns}
    if full_audio_storage_key:
        transcript_payload["fullAudioStorageKey"] = full_audio_storage_key
    if full_audio_storage_provider:
        transcript_payload["fullAudioStorageProvider"] = full_audio_storage_provider

    try:
        async with async_session_factory() as db:
            interview = await db.get(Interview, interview_uuid)
            if interview is None:
                return
            interview.metrics_json = analysis_data
            interview.transcript = transcript_payload
            if full_audio_url:
                interview.audio_url = full_audio_url
            await db.commit()
            print(f"[Persist] Session data saved: {session_id[:8]}")
    except Exception as exc:
        print(f"[Persist] Failed to save session {session_id[:8]}: {exc}")


def build_analysis_response(
    session_id: str,
    metrics: Optional[dict],
    transcript: Optional[dict],
    *,
    full_audio_url: Optional[str] = None,
) -> dict[str, Any]:
    """构建 GET /analysis 响应体。"""
    data = metrics or {}
    turns = []
    resolved_full_url = full_audio_url
    if isinstance(transcript, dict):
        turns = transcript.get("turns", []) or []
        if not resolved_full_url:
            resolved_full_url = transcript.get("fullAudioUrl")

    return {
        "sessionId": session_id,
        "pronunciation": data.get("pronunciation", []),
        "corrections": data.get("corrections", []),
        "fillerCounts": data.get("fillerCounts", {}),
        "transcriptTurns": turns,
        "fullAudioUrl": resolved_full_url,
    }


def enrich_analysis_from_timeline(
    response: dict[str, Any],
    timeline_events: list,
) -> dict[str, Any]:
    """旧会话无 metrics 时，从时间轴事件补全纠正与发音估算。"""
    has_metrics = (
        len(response.get("pronunciation", [])) > 0
        or len(response.get("corrections", [])) > 0
        or sum(response.get("fillerCounts", {}).values()) > 0
    )
    if has_metrics:
        return response

    corrections: list[dict] = []
    filler_counts: dict[str, int] = {}
    pronunciation: list[dict] = []

    for event in timeline_events:
        event_type = getattr(event, "event_type", None) or event.get("eventType", "")
        if event_type == "grammar_error":
            evidence = getattr(event, "evidence", None) or event.get("evidence") or {}
            if isinstance(evidence, str):
                evidence = {}
            turn_id = getattr(event, "turn_id", None) or event.get("turnId", "")
            snippet = getattr(event, "transcript_snippet", None) or event.get("transcriptSnippet", "")
            severity = getattr(event, "severity", None) or event.get("severity", "minor")
            corrections.append({
                "turnId": turn_id,
                "original": evidence.get("original", snippet),
                "corrected": evidence.get("corrected", ""),
                "severity": "serious" if severity in ("high", "serious") else "minor",
                "transcript": snippet,
            })

    # 从 transcript 用户轮次估算 WPM
    for turn in response.get("transcriptTurns", []):
        if turn.get("role") != "user":
            continue
        text = turn.get("text", "")
        word_count = len(text.split())
        if word_count == 0:
            continue
        duration_ms = max(1000, turn.get("endMs", 0) - turn.get("startMs", 0))
        duration_sec = duration_ms / 1000.0
        wpm = round(word_count / duration_sec * 60, 1) if duration_sec > 0 else 0
        pause_count = max(0, text.count(",") + text.count(".") - 1)
        pronunciation.append({
            "turnId": turn.get("turnId", ""),
            "wordsPerMinute": wpm,
            "pauseCount": pause_count,
            "lowConfidenceWords": [],
            "durationSeconds": round(duration_sec, 2),
            "wordCount": word_count,
        })
        # 简单语气词统计
        for word in text.lower().replace(",", " ").replace(".", " ").split():
            w = word.strip(".,!?;:'\"")
            if w in ("um", "uh", "er", "ah", "like", "you", "know"):
                key = "um" if w in ("um", "uh", "er", "ah") else w
                filler_counts[key] = filler_counts.get(key, 0) + 1

    if not corrections and not pronunciation and not filler_counts:
        return response

    return {
        **response,
        "corrections": corrections,
        "fillerCounts": filler_counts,
        "pronunciation": pronunciation,
    }
