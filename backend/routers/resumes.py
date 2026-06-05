"""简历上传路由 – POST /api/resumes。"""

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from exceptions import ApiError
from models.base import Resume, User
from services.resume_service import (
    detect_file_type,
    extract_text_from_file,
    parse_resume,
    save_resume_file,
)

router = APIRouter(prefix="/api", tags=["resumes"])


async def _get_demo_user(db: AsyncSession) -> User:
    """获取 MVP 演示用户。"""
    result = await db.execute(select(User).where(User.email == "demo@offergpt.local"))
    user = result.scalar_one_or_none()
    if user is None:
        raise ApiError("DEMO_USER_MISSING", "演示用户未初始化，请重启后端服务", 500)
    return user


@router.post("/resumes")
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    上传简历文件（PDF/TXT），解析文本并提取结构化画像。

    返回 resumeId 和 parsedProfile（技能、项目、风险信号）。
    """
    if not file.filename:
        raise ApiError("FILE_REQUIRED", "请上传简历文件")

    file_bytes = await file.read()
    if not file_bytes:
        raise ApiError("FILE_EMPTY", "上传的文件为空")

    if len(file_bytes) > 10 * 1024 * 1024:
        raise ApiError("FILE_TOO_LARGE", "简历文件不能超过 10MB")

    file_type = detect_file_type(file.filename, file.content_type)

    try:
        raw_text = extract_text_from_file(file_bytes, file_type, file.filename)
    except ValueError as exc:
        raise ApiError("PARSE_FAILED", str(exc))

    if not raw_text.strip():
        raise ApiError("EMPTY_RESUME", "未能从文件中提取到文本内容")

    # 解析结构化画像
    parsed_profile = await parse_resume(raw_text)

    # 保存文件到本地存储
    file_url = save_resume_file(file_bytes, file.filename)

    demo_user = await _get_demo_user(db)

    resume = Resume(
        user_id=demo_user.id,
        file_url=file_url,
        file_type=file_type,
        raw_text=raw_text,
        parsed_profile=parsed_profile,
        parse_status="success",
    )
    db.add(resume)
    await db.flush()

    return {
        "resumeId": str(resume.id),
        "parseStatus": "success",
        "parsedProfile": parsed_profile,
    }
