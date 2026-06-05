"""统一异常与错误响应格式测试。"""

import pytest
from fastapi import Request
from starlette.exceptions import HTTPException

from exceptions import (
    ApiError,
    api_error_handler,
    error_response,
    http_exception_handler,
    new_request_id,
    validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError


class TestApiError:
    """ApiError 业务异常测试。"""

    def test_api_error_fields(self):
        """应携带 errorCode、message、statusCode、requestId。"""
        err = ApiError("TEST_CODE", "测试错误消息", status_code=400)
        assert err.error_code == "TEST_CODE"
        assert err.message == "测试错误消息"
        assert err.status_code == 400
        assert err.request_id.startswith("req_")

    def test_new_request_id_format(self):
        """requestId 应符合 req_ 前缀格式。"""
        rid = new_request_id()
        assert rid.startswith("req_")
        assert len(rid) == 16  # req_ + 12 hex chars


class TestErrorResponse:
    """错误响应构造测试。"""

    def test_error_response_contract_fields(self):
        """响应体应包含 errorCode、message、requestId。"""
        resp = error_response("BAD_REQUEST", "参数错误", "req_test123", 400)
        body = resp.body.decode("utf-8")
        assert "errorCode" in body
        assert "message" in body
        assert "requestId" in body
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_api_error_handler(self):
        """api_error_handler 应返回统一格式。"""
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
        exc = ApiError("RESUME_REQUIRED", "面试场景需要提供简历 resumeId")
        response = await api_error_handler(request, exc)
        assert response.status_code == 400
        import json
        body = json.loads(response.body)
        assert body["errorCode"] == "RESUME_REQUIRED"
        assert "简历" in body["message"]

    @pytest.mark.asyncio
    async def test_http_exception_handler_404(self):
        """HTTP 404 应映射为 NOT_FOUND。"""
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
        exc = HTTPException(status_code=404, detail="会话不存在或已过期")
        response = await http_exception_handler(request, exc)
        import json
        body = json.loads(response.body)
        assert body["errorCode"] == "NOT_FOUND"
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_validation_exception_handler(self):
        """参数校验失败应返回 VALIDATION_ERROR。"""
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
        exc = RequestValidationError(errors=[{"loc": ("body", "title"), "msg": "field required", "type": "missing"}])
        response = await validation_exception_handler(request, exc)
        import json
        body = json.loads(response.body)
        assert body["errorCode"] == "VALIDATION_ERROR"
        assert response.status_code == 422
