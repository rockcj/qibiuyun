"""JD 服务单元测试 – 参数校验与解析流程。"""

import pytest

from services.job_service import parse_job


class TestJobService:
    """JD 解析服务测试。"""

    @pytest.mark.asyncio
    async def test_parse_job_success(self, sample_jd_payload):
        """合法 JD 应返回岗位画像。"""
        profile = await parse_job(
            sample_jd_payload["title"],
            sample_jd_payload["company"],
            sample_jd_payload["jdText"],
        )
        assert "requiredSkills" in profile
        assert "competencies" in profile
        assert "difficultyLevel" in profile

    @pytest.mark.asyncio
    async def test_parse_job_empty_jd_raises(self):
        """空 JD 文本应抛出 ValueError。"""
        with pytest.raises(ValueError, match="JD 文本不能为空"):
            await parse_job("Engineer", "Co", "   ")

    @pytest.mark.asyncio
    async def test_parse_job_empty_title_raises(self):
        """空岗位名称应抛出 ValueError。"""
        with pytest.raises(ValueError, match="岗位名称不能为空"):
            await parse_job("", "Co", "Valid JD text here for testing")
