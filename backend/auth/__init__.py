"""认证模块 — JWT 签发/验证、密码哈希、依赖注入。"""

from auth.passwords import hash_password, verify_password
from auth.jwt import create_access_token, create_refresh_token, decode_token
from auth.schemas import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from auth.dependencies import get_current_user

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "RegisterRequest",
    "LoginRequest",
    "RefreshRequest",
    "TokenResponse",
    "UserResponse",
    "get_current_user",
]
