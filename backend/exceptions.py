"""统一 API 异常与错误响应格式。"""

import uuid
from typing import Any, Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def new_request_id() -> str:
    """生成请求追踪 ID。"""
    return f"req_{uuid.uuid4().hex[:12]}"


class ApiError(Exception):
    """业务异常，携带 errorCode 和中文 message。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 400,
        request_id: Optional[str] = None,
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id or new_request_id()
        super().__init__(message)


def error_response(
    error_code: str,
    message: str,
    request_id: Optional[str] = None,
    status_code: int = 400,
) -> JSONResponse:
    """构造符合 api-contract 的错误响应。"""
    return JSONResponse(
        status_code=status_code,
        content={
            "errorCode": error_code,
            "message": message,
            "requestId": request_id or new_request_id(),
        },
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """处理自定义业务异常。"""
    return error_response(
        exc.error_code,
        exc.message,
        exc.request_id,
        exc.status_code,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """将 FastAPI HTTPException 转为统一错误格式。"""
    request_id = new_request_id()
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "errorCode": detail.get("errorCode", "HTTP_ERROR"),
                "message": detail.get("message", str(detail)),
                "requestId": detail.get("requestId", request_id),
            },
        )
    # 映射常见状态码到 errorCode
    code_map = {
        404: "NOT_FOUND",
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        500: "INTERNAL_ERROR",
    }
    return error_response(
        code_map.get(exc.status_code, "HTTP_ERROR"),
        str(detail) if detail else "请求处理失败",
        request_id,
        exc.status_code,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理请求参数校验错误。"""
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(loc) for loc in first.get("loc", []))
    msg = first.get("msg", "参数校验失败")
    return error_response(
        "VALIDATION_ERROR",
        f"参数校验失败: {field} {msg}",
        new_request_id(),
        422,
    )
