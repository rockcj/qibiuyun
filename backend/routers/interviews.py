"""Session (interview) router – POST /api/interviews, GET, finish, events, report."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.base import Interview
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/interviews", response_model=SessionResponse)
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new training session for the given scene.

    Supports interview, restaurant, and meeting scenes.
    """
    # Validate scene
    scene_config = get_scene(req.scene)
    if scene_config is None:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的场景: {req.scene}。可选: interview, restaurant, meeting",
        )

    # Validate requiresResumeJD for interview scenes
    if scene_config.get("requiresResumeJD") and not req.resumeId:
        raise HTTPException(
            status_code=400,
            detail="面试场景需要提供简历(resumeId)",
        )

    # Resolve persona display name
    persona_info = None
    if req.roleMode:
        for role in scene_config.get("roleModes", []):
            if role["roleMode"] == req.roleMode:
                persona_info = {"mode": role["roleMode"], "displayName": role["displayName"]}
                break

    # Build scene_config snapshot
    scene_config_snapshot = {
        "scene": req.scene,
        "topic": req.topic,
        "roleMode": req.roleMode,
        "personaMode": req.personaMode,
        "difficultyLevel": req.difficultyLevel,
        "durationMinutes": req.durationMinutes,
        "realtimeLightCorrection": req.realtimeLightCorrection,
        "rubric": scene_config.get("rubric", []),
        "correctionPolicy": scene_config.get("correctionPolicy", {}),
    }

    # Create interview record
    interview = Interview(
        user_id="demo-user",  # MVP: hardcoded demo user
        resume_id=req.resumeId,
        job_id=req.jobId,
        scene=req.scene,
        topic=req.topic,
        role_mode=req.roleMode,
        persona_mode=req.personaMode,
        scene_config=json.dumps(scene_config_snapshot, ensure_ascii=False),
        status="created",
    )
    db.add(interview)
    await db.flush()

    session_id = interview.id
    session_token = f"tok_{session_id}"  # MVP: simple token

    return SessionResponse(
        sessionId=session_id,
        sessionToken=session_token,
        websocketUrl=f"ws://localhost:8000/ws/interviews/{session_id}",
        scene=req.scene,
        topic=req.topic,
        persona=persona_info,
        status="created",
    )


@router.get("/interviews/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get session details."""
    interview = await db.get(Interview, session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return {
        "sessionId": interview.id,
        "scene": interview.scene,
        "topic": interview.topic,
        "roleMode": interview.role_mode,
        "status": interview.status,
        "startedAt": interview.started_at.isoformat() if interview.started_at else None,
        "createdAt": interview.created_at.isoformat(),
    }


@router.post("/interviews/{session_id}/finish")
async def finish_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """End a session and trigger report generation."""
    interview = await db.get(Interview, session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    interview.status = "completed"
    return {
        "sessionId": session_id,
        "status": "completed",
        "reportStatus": "generating",
    }


@router.get("/interviews/{session_id}/events")
async def get_session_events(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get VAR timeline events (returns empty list for now)."""
    interview = await db.get(Interview, session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return {"events": []}


@router.get("/interviews/{session_id}/report")
async def get_session_report(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get session report."""
    interview = await db.get(Interview, session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    if interview.status != "completed":
        raise HTTPException(status_code=400, detail="会话尚未结束")
    return {
        "reportId": f"rep_{session_id}",
        "sessionId": session_id,
        "scene": interview.scene,
        "scoreName": "Pending Score",
        "sceneScore": 0,
        "dimensionScores": {},
        "finalRecommendation": "报告正在生成中，请稍后刷新。",
    }
