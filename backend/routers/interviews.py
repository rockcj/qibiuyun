"""Session (interview) router – POST /api/interviews, GET, finish, events, report."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from exceptions import ApiError
from models.base import Interview, Job, Resume, User
from services.scene_service import get_scene

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


async def _get_demo_user(db: AsyncSession) -> User:
    """获取 MVP 演示用户。"""
    result = await db.execute(select(User).where(User.email == "demo@offergpt.local"))
    user = result.scalar_one_or_none()
    if user is None:
        raise ApiError("DEMO_USER_MISSING", "演示用户未初始化，请重启后端服务", 500)
    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/interviews", response_model=SessionResponse)
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
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

    demo_user = await _get_demo_user(db)

    interview = Interview(
        user_id=demo_user.id,
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
    }


@router.post("/interviews/{session_id}/finish")
async def finish_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """结束会话并触发报告生成。"""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    interview = await db.get(Interview, sid)
    if interview is None:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    interview.status = "completed"
    return {
        "sessionId": session_id,
        "status": "completed",
        "reportStatus": "generating",
    }


@router.get("/interviews/{session_id}/events")
async def get_session_events(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取 VAR 时间轴事件（当前返回空列表）。"""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    interview = await db.get(Interview, sid)
    if interview is None:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    return {"events": []}


@router.get("/interviews/{session_id}/report")
async def get_session_report(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取场景报告。"""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    interview = await db.get(Interview, sid)
    if interview is None:
        raise ApiError("SESSION_NOT_FOUND", "会话不存在或已过期", 404)

    if interview.status != "completed":
        raise ApiError("SESSION_NOT_COMPLETED", "会话尚未结束")

    return {
        "reportId": f"rep_{session_id}",
        "sessionId": session_id,
        "scene": interview.scene,
        "scoreName": "Offer Score",
        "sceneScore": 0,
        "dimensionScores": {},
        "finalRecommendation": "报告正在生成中，请稍后刷新。",
    }
