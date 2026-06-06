"""JWT 认证依赖注入 — 供所有路由使用的 get_current_user。"""

from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import decode_token
from config import settings
from database import get_db
from exceptions import ApiError
from models.base import User


async def get_current_user(
    authorization: str = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    从 Authorization header 提取 Bearer token 并解析当前用户。

    行为：
    - 正式用户：验证 JWT 返回对应用户
    - Demo 模式（无 token）：回落到 demo 用户，保持向后兼容
    - 无效 token：返回 401

    用法：
        @router.get("/foo")
        async def foo(user: User = Depends(get_current_user)):
            ...
    """
    # 有 token → 正式认证
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        payload = decode_token(token)
        if payload is None or payload.get("type") != "access":
            raise ApiError("UNAUTHORIZED", "登录已过期，请重新登录", 401)

        user_id = payload.get("sub")
        user = await db.get(User, UUID(user_id))
        if user is None:
            raise ApiError("UNAUTHORIZED", "用户不存在", 401)
        return user

    # 无 token → demo 模式回退
    if settings.demo_mode_enabled:
        result = await db.execute(
            select(User).where(User.email == "demo@offergpt.local")
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ApiError("DEMO_USER_MISSING", "演示用户未初始化，请重启后端服务", 500)
        return user

    # 生产模式无 token → 拒绝
    raise ApiError("UNAUTHORIZED", "请先登录", 401)
