"""LLM 解析服务单元测试 – 正则兜底、难度推断、画像结构。"""

import pytest

from services.llm_service import (
    extract_competencies_by_regex,
    extract_projects_by_regex,
    extract_risk_signals_by_regex,
    extract_skills_by_regex,
    infer_difficulty_level,
    parse_job_profile,
    parse_resume_profile,
)


class TestRegexExtraction:
    """正则提取函数测试。"""

    def test_extract_skills_from_resume(self, sample_resume_text):
        """应从简历文本中提取已知技能关键词。"""
        skills = extract_skills_by_regex(sample_resume_text)
        assert "Python" in skills
        assert "FastAPI" in skills
        assert "LLM" in skills
        assert len(skills) <= 15

    def test_extract_skills_empty_text(self):
        """空文本应返回空技能列表。"""
        assert extract_skills_by_regex("") == []

    def test_extract_projects_with_keyword(self):
        """应识别 Project 关键词后的项目名。"""
        text = "Project: AI Interview System\nOther content"
        projects = extract_projects_by_regex(text)
        assert len(projects) >= 1
        assert projects[0]["name"]
        assert "role" in projects[0]
        assert "impact" in projects[0]

    def test_extract_risk_signals_short_resume(self):
        """过短简历应标记风险信号。"""
        risks = extract_risk_signals_by_regex("Short resume")
        assert "Resume content is too short for deep analysis" in risks

    def test_extract_risk_signals_no_quantified_outcomes(self):
        """缺少量化指标时应标记风险。"""
        text = "I worked on many projects without numbers"
        risks = extract_risk_signals_by_regex(text)
        assert "Few quantified business outcomes" in risks

    def test_extract_competencies_from_jd(self, sample_jd_payload):
        """应从 JD 中提取能力项。"""
        competencies = extract_competencies_by_regex(sample_jd_payload["jdText"])
        assert "systemDesign" in competencies
        assert "problemSolving" in competencies

    def test_extract_competencies_fallback(self):
        """无匹配关键词时应返回默认能力项。"""
        competencies = extract_competencies_by_regex("Hello world only")
        assert competencies == ["problemSolving", "communication"]

    def test_infer_difficulty_senior(self):
        """含 senior 关键词应推断为 senior。"""
        assert infer_difficulty_level("Senior engineer with 5+ years") == "senior"

    def test_infer_difficulty_junior(self):
        """含 junior 关键词应推断为 junior。"""
        assert infer_difficulty_level("Junior developer entry level") == "junior"

    def test_infer_difficulty_middle_default(self):
        """无明确级别关键词时默认为 middle。"""
        assert infer_difficulty_level("Software engineer position") == "middle"


class TestAsyncProfileParsing:
    """异步画像解析测试（无 API Key 时走正则兜底）。"""

    @pytest.mark.asyncio
    async def test_parse_resume_profile_structure(self, sample_resume_text):
        """简历解析结果应包含契约要求的三个字段。"""
        profile = await parse_resume_profile(sample_resume_text)
        assert "skills" in profile
        assert "projects" in profile
        assert "riskSignals" in profile
        assert isinstance(profile["skills"], list)
        assert len(profile["skills"]) > 0

    @pytest.mark.asyncio
    async def test_parse_job_profile_structure(self, sample_jd_payload):
        """JD 解析结果应包含契约要求的三个字段。"""
        profile = await parse_job_profile(
            sample_jd_payload["title"],
            sample_jd_payload["company"],
            sample_jd_payload["jdText"],
        )
        assert "requiredSkills" in profile
        assert "competencies" in profile
        assert "difficultyLevel" in profile
        assert profile["difficultyLevel"] in ("junior", "middle", "senior")

    @pytest.mark.asyncio
    async def test_parse_job_profile_senior_jd(self, sample_jd_payload):
        """含 senior 关键词的 JD 应推断 senior 难度。"""
        profile = await parse_job_profile(
            "Senior AI Engineer",
            "Demo",
            sample_jd_payload["jdText"],
        )
        assert profile["difficultyLevel"] == "senior"
