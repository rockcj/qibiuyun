"""跨模块集成测试 – 简历 → JD → 会话完整链路。"""

import io

import pytest


@pytest.mark.integration
@pytest.mark.p0
class TestInterviewFullFlow:
    """P0 面试场景端到端 API 链路测试。"""

    @pytest.mark.asyncio
    async def test_resume_to_job_to_session_flow(
        self, app_client, sample_resume_text, sample_jd_payload
    ):
        """
        完整链路：
        上传简历 → 创建 JD → 创建面试会话 → 查询详情 → 结束会话 → 获取报告占位。
        """
        # Step 1: 上传简历
        resume_resp = await app_client.post(
            "/api/resumes",
            files={"file": ("resume.txt", io.BytesIO(sample_resume_text.encode()), "text/plain")},
        )
        assert resume_resp.status_code == 200
        resume_id = resume_resp.json()["resumeId"]

        # Step 2: 创建 JD
        job_resp = await app_client.post("/api/jobs", json=sample_jd_payload)
        assert job_resp.status_code == 200
        job_id = job_resp.json()["jobId"]

        # Step 3: 创建会话
        session_resp = await app_client.post(
            "/api/interviews",
            json={
                "scene": "interview",
                "topic": "behavioral",
                "roleMode": "founder",
                "resumeId": resume_id,
                "jobId": job_id,
                "personaMode": "founder",
                "durationMinutes": 15,
                "difficultyLevel": "senior",
                "realtimeLightCorrection": True,
            },
        )
        assert session_resp.status_code == 200
        session_data = session_resp.json()
        session_id = session_data["sessionId"]

        # Step 4: 查询会话
        detail_resp = await app_client.get(f"/api/interviews/{session_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["status"] == "created"

        # Step 5: 获取 VAR 事件（当前为空列表）
        events_resp = await app_client.get(f"/api/interviews/{session_id}/events")
        assert events_resp.status_code == 200
        assert events_resp.json()["events"] == []

        # Step 6: 结束会话
        finish_resp = await app_client.post(f"/api/interviews/{session_id}/finish")
        assert finish_resp.status_code == 200
        assert finish_resp.json()["status"] == "completed"

        # Step 7: 获取报告占位
        report_resp = await app_client.get(f"/api/interviews/{session_id}/report")
        assert report_resp.status_code == 200
        report = report_resp.json()
        assert report["sessionId"] == session_id
        assert report["scene"] == "interview"

    @pytest.mark.asyncio
    async def test_health_endpoint(self, app_client):
        """健康检查端点应返回 ok。"""
        resp = await app_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
