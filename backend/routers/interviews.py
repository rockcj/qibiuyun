"""Session (interview) router – POST /api/interviews, GET, finish, events, report."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.dependencies import get_current_user
from config import settings
from database import get_db
from exceptions import ApiError
from models.base import Interview, Job, Report, Resume, TimelineEvent, User
from services.report_service import report_service
from services.scene_service import get_scene


def _utcnow():
    return datetime.now(timezone.utc)

router = APIRouter(prefix="/api", tags=["interviews"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class CreateSessionRequest(BaseModel):
    scene: str
    topic: Optional[str] = None
    roleMode: Optional[str] = None
    resumeId: Optional[str] = None
    jobId: Optional[str] = None
    personaMode: Optional[str] = None
    durationMinutes: Optional[int] = 15
    difficultyLevel: Optional[str] = "middle"
    realtimeLightCorrection: Optional[bool] = True


class SessionResponse(BaseModel):
    sessionId: str
    sessionToken: str
    websocketUrl: str
    scene: str
    topic: Optional[str] = None
    persona: Optional[dict] = None
    status: str = "created"


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    """将字符串解析为 UUID，失败时抛出业务异常。"""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ApiError("INVALID_ID", f"{field_name} 格式无效: {value}")


def _build_websocket_url(session_id: str) -> str:
    """根据配置生成 WebSocket 连接地址。"""
    ws_base = getattr(settings, "ws_base_url", None) or f"ws://localhost:{settings.backend_port}"
    return f"{ws_base.rstrip('/')}/ws/interviews/{session_id}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/interviews", response_model=SessionResponse)
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    创建训练会话，支持 interview / restaurant / meeting 场景。

    面试场景需绑定 resumeId 和 jobId；点餐/会议场景仅需主题和角色。
    """
    scene_config = get_scene(req.scene)
    if scene_config is None:
        raise ApiError(
            "SCENE_NOT_FOUND",
            f"不支持的场景: {req.scene}。可选: interview, restaurant, meeting",
        )

    # 面试场景必须提供简历和 JD
    if req.scene == "interview":
        if not req.resumeId:
            raise ApiError("RESUME_REQUIRED", "面试场景需要提供简历 resumeId")
        if not req.jobId:
            raise ApiError("JOB_REQUIRED", "面试场景需要提供岗位 jobId")

    # 校验 topic 和 roleMode
    if req.topic:
        valid_topics = {t["topic"] for t in scene_config.get("topics", [])}
        if req.topic not in valid_topics:
            raise ApiError("INVALID_TOPIC", f"不支持的子主题: {req.topic}")

    if req.roleMode:
        valid_roles = {r["roleMode"] for r in scene_config.get("roleModes", [])}
        if req.roleMode not in valid_roles:
            raise ApiError("INVALID_ROLE", f"不支持的角色模式: {req.roleMode}")

    # 解析并校验 resumeId / jobId
    resume_uuid = None
    job_uuid = None
    if req.resumeId:
        resume_uuid = _parse_uuid(req.resumeId, "resumeId")
        resume = await db.get(Resume, resume_uuid)
        if resume is None:
            raise ApiError("RESUME_NOT_FOUND", "简历不存在或已过期")

    if req.jobId:
        job_uuid = _parse_uuid(req.jobId, "jobId")
        job = await db.get(Job, job_uuid)
        if job is None:
            raise ApiError("JOB_NOT_FOUND", "岗位 JD 不存在或已过期")

    # 解析 Persona 展示名
    persona_info = None
    persona_mode = req.personaMode or req.roleMode
    if req.roleMode:
        for role in scene_config.get("roleModes", []):
            if role["roleMode"] == req.roleMode:
                persona_info = {"mode": role["roleMode"], "displayName": role["displayName"]}
                break

    # 构建场景配置快照
    scene_config_snapshot = {
        "scene": req.scene,
        "topic": req.topic,
        "roleMode": req.roleMode,
        "personaMode": persona_mode,
        "difficultyLevel": req.difficultyLevel,
        "durationMinutes": req.durationMinutes,
        "realtimeLightCorrection": req.realtimeLightCorrection,
        "rubric": scene_config.get("rubric", []),
        "correctionPolicy": scene_config.get("correctionPolicy", {}),
    }

    interview = Interview(
        user_id=user.id,
        resume_id=resume_uuid,
        job_id=job_uuid,
        scene=req.scene,
        topic=req.topic,
        role_mode=req.roleMode,
        persona_mode=persona_mode,
        scene_config=scene_config_snapshot,
        status="created",
    )
    db.add(interview)
    await db.flush()

    session_id = str(interview.id)
    session_token = f"tok_{session_id}"

    return SessionResponse(
        sessionId=session_id,
        sessionToken=session_token,
        websocketUrl=_build_websocket_url(session_id),
        scene=req.scene,
        topic=req.topic,
        persona=persona_info,
        status="created",
    )


@router.get("/interviews/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """查询会话详情。"""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    interview = await db.get(Interview, sid)
    if interview is None:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    return {
        "sessionId": str(interview.id),
        "scene": interview.scene,
        "topic": interview.topic,
        "roleMode": interview.role_mode,
        "status": interview.status,
        "startedAt": interview.started_at.isoformat() if interview.started_at else None,
        "durationSeconds": interview.duration_seconds,
        "audioUrl": interview.audio_url,  # 录音文件地址（可能为 None）
    }


async def _get_interview_with_report(
    db: AsyncSession, sid: uuid.UUID
) -> Optional[Interview]:
    """加载会话及关联报告。"""
    result = await db.execute(
        select(Interview)
        .options(selectinload(Interview.report))
        .where(Interview.id == sid)
    )
    return result.scalar_one_or_none()


def _build_report_response(report: Report, session_id: str, scene: str) -> dict:
    """从 Report ORM 对象构建 API 响应。"""
    report_json = report.report_json or {}
    dim_evidence = report_json.get("dimensionEvidence", {})
    evidence_list = []
    for dim, info in dim_evidence.items():
        if isinstance(info, dict):
            evidence_list.append({
                "dimension": dim,
                "score": info.get("score", 0),
                "evidence": info.get("evidence", ""),
            })
        elif isinstance(info, (int, float)):
            evidence_list.append({"dimension": dim, "score": int(info), "evidence": ""})

    return {
        "reportId": f"rep_{session_id}",
        "sessionId": session_id,
        "scene": scene,
        "scoreName": report.score_name,
        "sceneScore": report.scene_score or 0,
        "dimensionScores": report.dimension_scores or {},
        "finalRecommendation": report_json.get("finalRecommendation", ""),
        "highlights": report_json.get("highlights", []),
        "improvements": report_json.get("improvements", []),
        "evidenceList": evidence_list,
        "reportStatus": "ready",
    }


def _build_generating_response(session_id: str, scene: str) -> dict:
    """返回报告生成中的模板响应。"""
    return {
        "reportId": None, "sessionId": session_id, "scene": scene,
        "scoreName": "Offer Score" if scene == "interview" else "Scene Score",
        "sceneScore": 0, "dimensionScores": {}, "finalRecommendation": "",
        "highlights": [], "improvements": [], "evidenceList": [],
        "reportStatus": "generating",
    }


async def _generate_report_background(session_id: str, interview_id_str: str):
    """后台任务：通过 LLM Agent 生成报告，失败时降级到规则引擎。"""
    from database import async_session_factory
    from services.cache_service import cache
    from services.realtime import analysis_store
    from services.report_agent import report_agent

    try:
        # Phase 1: 收集数据
        analysis_summary = await analysis_store.get_summary(session_id)
        if analysis_summary is None:
            analysis_summary = {"corrections": [], "fillerCounts": {}, "pronunciation": []}

        conversation_history = []
        try:
            raw = await cache.get(f"session:{session_id}")
            if raw:
                session_data = json.loads(raw)
                conversation_history = session_data.get("history", [])
        except Exception:
            pass

        interview_uuid = uuid.UUID(interview_id_str)

        async with async_session_factory() as bg_db:
            result = await bg_db.execute(
                select(TimelineEvent)
                .where(TimelineEvent.interview_id == interview_uuid)
                .order_by(TimelineEvent.start_ms)
            )
            existing_events = result.scalars().all()

            interview = await bg_db.get(Interview, interview_uuid)
            if interview is None:
                print(f"[ReportBg] Interview not found: {interview_id_str}")
                return

            scene_config = interview.scene_config or {}
            scene = interview.scene

            existing_events_data = [
                {"turnId": e.turn_id, "eventType": e.event_type, "severity": e.severity,
                 "title": e.title, "startMs": e.start_ms, "endMs": e.end_ms}
                for e in existing_events
            ]

            # Phase 2: 尝试 LLM
            llm_result = await report_agent.generate(
                session_id=session_id, scene=scene, scene_config=scene_config,
                analysis_summary=analysis_summary, conversation_history=conversation_history,
                existing_timeline_events=existing_events_data,
            )

            # Phase 3: 持久化
            if llm_result:
                dim_scores_simple = {}
                for dim, info in llm_result.get("dimensionScores", {}).items():
                    dim_scores_simple[dim] = info.get("score", 60) if isinstance(info, dict) else info

                bg_db.add(Report(
                    interview_id=interview_uuid,
                    scene_score=llm_result["sceneScore"],
                    score_name=llm_result.get("scoreName", "Offer Score"),
                    dimension_scores=dim_scores_simple,
                    report_json={
                        "dimensionEvidence": llm_result.get("dimensionScores", {}),
                        "highlights": llm_result.get("highlights", []),
                        "improvements": llm_result.get("improvements", []),
                        "finalRecommendation": llm_result.get("finalRecommendation", ""),
                        "generatedBy": "llm",
                    },
                ))
                for event in llm_result.get("timelineEvents", []):
                    bg_db.add(TimelineEvent(
                        interview_id=interview_uuid,
                        turn_id=event.get("turnId"),
                        event_type=event.get("eventType", "llm_detected"),
                        severity=event.get("severity", "medium"),
                        title=event.get("title", ""),
                        description=event.get("description", ""),
                        start_ms=event.get("startMs", 0),
                        end_ms=event.get("endMs", 0),
                        transcript_snippet=event.get("transcriptSnippet", ""),
                        suggestion=event.get("suggestion", ""),
                        evidence=event.get("evidence"),
                        display_priority=event.get("displayPriority", 0),
                    ))
                print(f"[ReportBg] LLM report saved for {interview_id_str}")
            else:
                # 规则兜底
                payload = await report_service.build_report_payload(session_id, scene)
                bg_db.add(Report(
                    interview_id=interview_uuid,
                    scene_score=payload["sceneScore"],
                    score_name=payload["scoreName"],
                    dimension_scores=payload["dimensionScores"],
                    report_json={
                        "highlights": payload.get("reportJson", {}).get("highlights", []),
                        "improvements": payload.get("reportJson", {}).get("improvements", []),
                        "finalRecommendation": payload.get("finalRecommendation", ""),
                        "generatedBy": "rules",
                    },
                ))
                print(f"[ReportBg] Rules-based report saved for {interview_id_str}")

            await bg_db.commit()
    except Exception as exc:
        print(f"[ReportBg] Fatal error: {exc}")


@router.post("/interviews/{session_id}/finish")
async def finish_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """结束会话并异步生成报告。"""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    interview = await _get_interview_with_report(db, sid)
    if interview is None:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    if interview.status != "completed":
        interview.status = "completed"
        interview.ended_at = _utcnow()

    if interview.report is not None:
        return {"sessionId": session_id, "status": "completed", "reportStatus": "ready",
                "sceneScore": interview.report.scene_score or 0}

    asyncio.create_task(_generate_report_background(session_id, str(interview.id)))
    return {"sessionId": session_id, "status": "completed", "reportStatus": "generating"}


@router.get("/interviews/{session_id}/events")
async def get_session_events(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取 VAR 时间轴事件，附带 AI 回复文本。"""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    interview = await db.get(Interview, sid)
    if interview is None:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    result = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.interview_id == sid)
        .order_by(TimelineEvent.start_ms)
    )
    events = result.scalars().all()

    # 从 Redis 读取对话历史，为每个事件匹配 AI 回复
    ai_responses: dict[str, str] = {}  # turn_id → ai 回复文本
    try:
        from services.cache_service import cache
        raw = await cache.get(f"session:{session_id}")
        if raw:
            session_data = json.loads(raw)
            history = session_data.get("history", [])
            # history 是 [{role, content}, ...] 列表，按 user/assistant 交替
            for idx, msg in enumerate(history):
                if msg.get("role") == "assistant":
                    turn_num = (idx // 2) + 1  # assistant 在第几个 turn
                    ai_responses[f"turn_{turn_num:03d}"] = msg.get("content", "")
    except Exception:
        pass  # Redis 不可用时跳过

    return {
        "sessionId": session_id,
        "events": [{
            "eventId": str(e.id), "turnId": e.turn_id, "eventType": e.event_type,
            "severity": e.severity, "title": e.title, "description": e.description,
            "startMs": e.start_ms, "endMs": e.end_ms,
            "transcriptSnippet": e.transcript_snippet, "evidence": e.evidence,
            "suggestion": e.suggestion, "displayPriority": e.display_priority,
            "aiResponse": ai_responses.get(e.turn_id),  # AI 回复文本
        } for e in events],
    }


@router.get("/interviews/{session_id}/report")
async def get_session_report(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取场景报告。生成中返回 reportStatus: 'generating'。"""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    interview = await _get_interview_with_report(db, sid)
    if interview is None:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    if interview.report is not None:
        return _build_report_response(interview.report, session_id, interview.scene)

    if interview.status == "completed":
        return _build_generating_response(session_id, interview.scene)

    raise ApiError("SESSION_NOT_COMPLETED", "会话尚未结束")
