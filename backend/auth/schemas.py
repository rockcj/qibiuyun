"""认证相关 Pydantic 请求/响应模型。"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册请求。"""

    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    """登录请求。"""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """刷新 token 请求。"""

    refreshToken: str


class UserResponse(BaseModel):
    """公开用户信息。"""

    id: str
    email: str
    name: Optional[str] = None
    avatarUrl: Optional[str] = None
    plan: str = "free"

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """认证成功响应。"""

    accessToken: str
    refreshToken: str
    tokenType: str = "bearer"
    user: UserResponse
