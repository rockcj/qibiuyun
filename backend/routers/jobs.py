"""JD 创建路由 – POST /api/jobs。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from exceptions import ApiError
from models.base import Job, User
from services.job_service import parse_job

router = APIRouter(prefix="/api", tags=["jobs"])


class CreateJobRequest(BaseModel):
    """创建 JD 请求体。"""

    title: str = Field(..., min_length=1, max_length=200)
    company: str = Field(default="", max_length=200)
    jdText: str = Field(..., min_length=10)


async def _get_demo_user(db: AsyncSession) -> User:
    """获取 MVP 演示用户。"""
    result = await db.execute(select(User).where(User.email == "demo@offergpt.local"))
    user = result.scalar_one_or_none()
    if user is None:
        raise ApiError("DEMO_USER_MISSING", "演示用户未初始化，请重启后端服务", 500)
    return user


@router.post("/jobs")
async def create_job(
    req: CreateJobRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    提交岗位 JD，解析并返回岗位画像。

    返回 jobId 和 parsedProfile（requiredSkills、competencies、difficultyLevel）。
    """
    try:
        parsed_profile = await parse_job(req.title, req.company, req.jdText)
    except ValueError as exc:
        raise ApiError("JD_PARSE_FAILED", str(exc))

    demo_user = await _get_demo_user(db)

    job = Job(
        user_id=demo_user.id,
        title=req.title.strip(),
        company=req.company.strip() or None,
        jd_text=req.jdText.strip(),
        parsed_profile=parsed_profile,
        difficulty_level=parsed_profile.get("difficultyLevel"),
    )
    db.add(job)
    await db.flush()

    return {
        "jobId": str(job.id),
        "parsedProfile": parsed_profile,
    }
