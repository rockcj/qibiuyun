"""报告服务单元测试 — 规则评分与 API 响应。"""

import pytest

from services.report_service import report_service
from services.realtime import analysis_store


class TestReportService:
    """课后报告生成测试。"""

    @pytest.mark.asyncio
    async def test_build_report_with_analysis_data(self):
        """有分析数据时应返回有效 Offer Score。"""
        session_id = "test-report-session-001"
        await analysis_store.append_pronunciation(session_id, {
            "turnId": "turn_001",
            "wordsPerMinute": 145,
            "pauseCount": 1,
            "lowConfidenceWords": [],
            "durationSeconds": 8.0,
            "wordCount": 20,
            "overallConfidence": 0.88,
        })
        await analysis_store.incr_filler(session_id, "um", +2)

        payload = await report_service.build_report_payload(session_id, "interview")
        api = report_service.payload_to_api_response(payload)

        assert api["sceneScore"] > 0
        assert api["finalRecommendation"] != "报告正在生成中，请稍后刷新。"
        assert "pronunciation" in api["dimensionScores"]
        assert len(api.get("highlights", [])) > 0

    @pytest.mark.asyncio
    async def test_build_report_without_data_uses_defaults(self):
        """无分析数据时仍返回基础报告。"""
        payload = await report_service.build_report_payload(
            "empty-session-999", "interview"
        )
        api = report_service.payload_to_api_response(payload)

        assert api["sceneScore"] >= 0
        assert "finalRecommendation" in api
        assert api["finalRecommendation"]
