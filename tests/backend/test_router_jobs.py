"""JD 路由 API 测试 – POST /api/jobs。"""

import pytest


class TestJobsRouter:
    """JD 创建接口测试。"""

    @pytest.mark.asyncio
    @pytest.mark.contract
    @pytest.mark.p0
    async def test_create_job_success(self, app_client, sample_jd_payload):
        """TC-P0-004：提交 JD 应返回 jobId 和 parsedProfile。"""
        resp = await app_client.post("/api/jobs", json=sample_jd_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "jobId" in data
        profile = data["parsedProfile"]
        assert "requiredSkills" in profile
        assert "competencies" in profile
        assert "difficultyLevel" in profile
        assert profile["difficultyLevel"] in ("junior", "middle", "senior")

    @pytest.mark.asyncio
    async def test_create_job_missing_title_validation_error(self, app_client):
        """缺少 title 应返回 VALIDATION_ERROR。"""
        resp = await app_client.post("/api/jobs", json={"title": "", "jdText": "valid jd text here"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["errorCode"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_create_job_short_jd_validation_error(self, app_client):
        """JD 过短应返回校验错误。"""
        resp = await app_client.post("/api/jobs", json={"title": "Engineer", "jdText": "short"})
        assert resp.status_code == 422
