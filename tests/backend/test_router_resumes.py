"""简历路由 API 测试 – POST /api/resumes。"""

import io

import pytest


class TestResumesRouter:
    """简历上传接口测试。"""

    @pytest.mark.asyncio
    @pytest.mark.contract
    @pytest.mark.p0
    async def test_upload_txt_resume_success(self, app_client, sample_resume_text):
        """TC-P0-003：上传 TXT 简历应返回 resumeId 和 parsedProfile。"""
        files = {"file": ("resume.txt", io.BytesIO(sample_resume_text.encode("utf-8")), "text/plain")}
        resp = await app_client.post("/api/resumes", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert "resumeId" in data
        assert data["parseStatus"] == "success"
        profile = data["parsedProfile"]
        assert "skills" in profile
        assert "projects" in profile
        assert "riskSignals" in profile
        assert len(profile["skills"]) > 0

    @pytest.mark.asyncio
    async def test_upload_empty_file_returns_error(self, app_client):
        """空文件应返回统一错误格式。"""
        files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
        resp = await app_client.post("/api/resumes", files=files)
        assert resp.status_code == 400
        body = resp.json()
        assert "errorCode" in body
        assert "message" in body
        assert "requestId" in body

    @pytest.mark.asyncio
    async def test_upload_without_file_returns_error(self, app_client):
        """缺少文件应返回校验错误。"""
        resp = await app_client.post("/api/resumes")
        assert resp.status_code == 422
