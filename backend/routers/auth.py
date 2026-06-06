"""认证路由 — POST /api/auth/register, /login, /refresh, GET /me。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.jwt import create_access_token, create_refresh_token, decode_token
from auth.passwords import hash_password, verify_password
from auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from database import get_db
from exceptions import ApiError
from models.base import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_to_response(user: User) -> UserResponse:
    """将 ORM User 转为公开响应。"""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatarUrl=user.avatar_url,
        plan=user.plan,
    )


def _build_token_response(user: User, user_id: str) -> TokenResponse:
    """为指定用户生成 token 对和响应。"""
    return TokenResponse(
        accessToken=create_access_token(user_id),
        refreshToken=create_refresh_token(user_id),
        tokenType="bearer",
        user=_user_to_response(user),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户，成功后直接返回 token（免去二次登录）。"""
    # 检查邮箱是否已注册
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none() is not None:
        raise ApiError("EMAIL_EXISTS", "该邮箱已注册")

    user = User(
        email=req.email,
        name=req.name or req.email.split("@")[0],
        hashed_password=hash_password(req.password),
        plan="free",
    )
    db.add(user)
    await db.flush()
    return _build_token_response(user, str(user.id))


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """邮箱 + 密码登录，返回 JWT token 对。"""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if user is None or user.hashed_password is None:
        raise ApiError("INVALID_CREDENTIALS", "邮箱或密码错误", 401)

    if not verify_password(req.password, user.hashed_password):
        raise ApiError("INVALID_CREDENTIALS", "邮箱或密码错误", 401)

    return _build_token_response(user, str(user.id))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """用 refresh token 换取新的 token 对（token 轮换）。"""
    payload = decode_token(req.refreshToken)
    if payload is None or payload.get("type") != "refresh":
        raise ApiError("INVALID_TOKEN", "refresh_token 无效或已过期", 401)

    user = await db.get(User, UUID(payload["sub"]))
    if user is None:
        raise ApiError("UNAUTHORIZED", "用户不存在", 401)

    return _build_token_response(user, str(user.id))


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """获取当前登录用户信息（需 Bearer token）。demo 模式下返回 demo 用户。"""
    return _user_to_response(user)
