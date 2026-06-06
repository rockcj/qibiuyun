"""Grammar Agent 单元测试 — 规则检测、开关控制、语气词统计。"""

import pytest

from services.realtime.grammar_agent import GrammarAgent, grammar_agent


class TestGrammarAgentRules:
    """严重语法错误规则检测。"""

    @pytest.fixture
    def agent(self):
        return GrammarAgent()

    @pytest.mark.asyncio
    async def test_severe_have_did(self, agent):
        """'I have did a project' 应判为 serious。"""
        result = await agent.analyze(
            "I have did a project last year",
            realtime_enabled=True,
        )
        assert result.severity == "serious"
        assert "did" in result.original.lower()
        assert "done" in result.corrected.lower()
        assert result.spoken_tip != ""

    @pytest.mark.asyncio
    async def test_severe_i_has(self, agent):
        """'I has experience' 应判为 serious。"""
        result = await agent.analyze(
            "I has five years of experience",
            realtime_enabled=True,
        )
        assert result.severity == "serious"
        assert "has" in result.original.lower()
        assert "have" in result.corrected.lower()

    @pytest.mark.asyncio
    async def test_correct_sentence_no_error(self, agent):
        """正确句子不应触发纠正。"""
        result = await agent.analyze(
            "I have done several projects in Python and Java.",
            realtime_enabled=True,
        )
        assert result.severity == "none"
        assert result.spoken_tip == ""

    @pytest.mark.asyncio
    async def test_realtime_disabled_no_tip(self, agent):
        """关闭实时轻纠正时不发送 spokenTip。"""
        result = await agent.analyze(
            "I have did a project",
            realtime_enabled=False,
        )
        assert result.severity == "serious"
        assert result.spoken_tip == ""

    @pytest.mark.asyncio
    async def test_filler_word_counting(self, agent):
        """语气词 um/uh 应被统计。"""
        result = await agent.analyze(
            "Um, I think, uh, we should go there.",
            realtime_enabled=True,
        )
        assert result.filler_counts.get("um", 0) >= 1
        assert result.filler_counts.get("uh", 0) >= 1

    @pytest.mark.asyncio
    async def test_only_severe_policy_blocks_minor(self, agent):
        """onlyInterruptSevereErrors 策略下轻微错误不实时提示。"""
        result = await agent.analyze(
            "I have did a project",
            realtime_enabled=True,
            correction_policy={"onlyInterruptSevereErrors": True},
        )
        assert result.severity == "serious"
        assert result.spoken_tip != ""

    @pytest.mark.asyncio
    async def test_chinese_transcript_skipped(self, agent):
        """中文内容不应触发语法纠正。"""
        result = await agent.analyze(
            "你好我想练习英语",
            realtime_enabled=True,
        )
        assert result.severity == "none"
        assert result.spoken_tip == ""

    @pytest.mark.asyncio
    async def test_singleton_available(self):
        """全局单例应可导入。"""
        assert grammar_agent is not None
