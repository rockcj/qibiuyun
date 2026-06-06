"""会话路由 API 测试 – POST/GET /api/interviews。"""

import io

import pytest


async def _create_resume_and_job(app_client, sample_resume_text, sample_jd_payload):
    """辅助：创建简历和 JD，返回 (resumeId, jobId)。"""
    files = {"file": ("resume.txt", io.BytesIO(sample_resume_text.encode("utf-8")), "text/plain")}
    resume_resp = await app_client.post("/api/resumes", files=files)
    job_resp = await app_client.post("/api/jobs", json=sample_jd_payload)
    return resume_resp.json()["resumeId"], job_resp.json()["jobId"]


class TestInterviewsRouter:
    """会话管理接口测试。"""

    @pytest.mark.asyncio
    @pytest.mark.contract
    @pytest.mark.p0
    async def test_create_interview_session_success(
        self, app_client, sample_resume_text, sample_jd_payload
    ):
        """TC-P0-005：面试会话应返回 sessionId、sessionToken、websocketUrl。"""
        resume_id, job_id = await _create_resume_and_job(
            app_client, sample_resume_text, sample_jd_payload
        )
        payload = {
            "scene": "interview",
            "topic": "behavioral",
            "roleMode": "founder",
            "resumeId": resume_id,
            "jobId": job_id,
            "personaMode": "founder",
            "durationMinutes": 15,
            "difficultyLevel": "senior",
            "realtimeLightCorrection": True,
        }
        resp = await app_client.post("/api/interviews", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "sessionId" in data
        assert "sessionToken" in data
        assert data["sessionToken"].startswith("tok_")
        assert "websocketUrl" in data
        assert "/ws/interviews/" in data["websocketUrl"]
        assert data["scene"] == "interview"
        assert data["status"] == "created"
        assert data["persona"]["mode"] == "founder"

    @pytest.mark.asyncio
    @pytest.mark.p0
    async def test_create_interview_without_resume_returns_error(self, app_client):
        """面试场景缺少 resumeId 应返回 RESUME_REQUIRED。"""
        resp = await app_client.post(
            "/api/interviews",
            json={"scene": "interview", "topic": "behavioral", "roleMode": "founder"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["errorCode"] == "RESUME_REQUIRED"
        assert "简历" in body["message"]

    @pytest.mark.asyncio
    async def test_create_interview_without_job_returns_error(self, app_client, sample_resume_text):
        """面试场景缺少 jobId 应返回 JOB_REQUIRED。"""
        files = {"file": ("resume.txt", io.BytesIO(sample_resume_text.encode("utf-8")), "text/plain")}
        resume_id = (await app_client.post("/api/resumes", files=files)).json()["resumeId"]
        resp = await app_client.post(
            "/api/interviews",
            json={
                "scene": "interview",
                "topic": "behavioral",
                "roleMode": "founder",
                "resumeId": resume_id,
            },
        )
        assert resp.status_code == 400
        assert resp.json()["errorCode"] == "JOB_REQUIRED"

    @pytest.mark.asyncio
    async def test_create_restaurant_session_without_resume(
        self, app_client
    ):
        """点餐场景无需 resumeId/jobId 即可创建会话。"""
        resp = await app_client.post(
            "/api/interviews",
            json={
                "scene": "restaurant",
                "topic": "ordering",
                "roleMode": "friendlyWaiter",
                "durationMinutes": 8,
                "difficultyLevel": "daily",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["scene"] == "restaurant"

    @pytest.mark.asyncio
    async def test_get_session_detail(self, app_client, sample_resume_text, sample_jd_payload):
        """GET /api/interviews/{id} 应返回会话详情。"""
        resume_id, job_id = await _create_resume_and_job(
            app_client, sample_resume_text, sample_jd_payload
        )
        create_resp = await app_client.post(
            "/api/interviews",
            json={
                "scene": "interview",
                "topic": "behavioral",
                "roleMode": "founder",
                "resumeId": resume_id,
                "jobId": job_id,
            },
        )
        session_id = create_resp.json()["sessionId"]
        resp = await app_client.get(f"/api/interviews/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessionId"] == session_id
        assert data["scene"] == "interview"
        assert data["status"] == "created"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_returns_404(self, app_client):
        """不存在的会话应返回 SESSION_NOT_FOUND。"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await app_client.get(f"/api/interviews/{fake_id}")
        assert resp.status_code == 404
        assert resp.json()["errorCode"] == "SESSION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_finish_session(self, app_client, sample_resume_text, sample_jd_payload):
        """结束会话应返回 completed 和 reportStatus。"""
        resume_id, job_id = await _create_resume_and_job(
            app_client, sample_resume_text, sample_jd_payload
        )
        session_id = (
            await app_client.post(
                "/api/interviews",
                json={
                    "scene": "interview",
                    "topic": "behavioral",
                    "roleMode": "founder",
                    "resumeId": resume_id,
                    "jobId": job_id,
                },
            )
        ).json()["sessionId"]

        resp = await app_client.post(f"/api/interviews/{session_id}/finish")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["reportStatus"] == "ready"
        assert "sceneScore" in data

    @pytest.mark.asyncio
    async def test_invalid_topic_returns_error(
        self, app_client, sample_resume_text, sample_jd_payload
    ):
        """无效子主题应返回 INVALID_TOPIC。"""
        resume_id, job_id = await _create_resume_and_job(
            app_client, sample_resume_text, sample_jd_payload
        )
        resp = await app_client.post(
            "/api/interviews",
            json={
                "scene": "interview",
                "topic": "nonexistent_topic",
                "roleMode": "founder",
                "resumeId": resume_id,
                "jobId": job_id,
            },
        )
        assert resp.status_code == 400
        assert resp.json()["errorCode"] == "INVALID_TOPIC"
