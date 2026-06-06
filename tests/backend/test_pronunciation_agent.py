"""Pronunciation Agent 单元测试 — WPM、停顿、低置信度词。"""

import numpy as np
import pytest

from services.realtime.pronunciation_agent import PronunciationAgent, pronunciation_agent
from services.realtime import analysis_store


class TestPronunciationAgent:
    """发音分析计算。"""

    @pytest.fixture
    def agent(self):
        return PronunciationAgent()

    def _make_pcm(self, duration_sec: float, sample_rate: int = 16000) -> bytes:
        """生成指定时长的静音 PCM 数据。"""
        num_samples = int(duration_sec * sample_rate)
        samples = np.zeros(num_samples, dtype=np.int16)
        return samples.tobytes()

    def _make_pcm_with_speech(self, duration_sec: float, sample_rate: int = 16000) -> bytes:
        """生成含语音能量的 PCM 数据（模拟说话）。"""
        num_samples = int(duration_sec * sample_rate)
        # 交替静音和高能量段模拟停顿
        samples = np.zeros(num_samples, dtype=np.int16)
        segment = num_samples // 4
        for i in range(4):
            start = i * segment
            end = start + segment // 2
            if i % 2 == 1:
                samples[start:end] = np.random.randint(1000, 5000, end - start, dtype=np.int16)
        return samples.tobytes()

    @pytest.mark.asyncio
    async def test_wpm_calculation(self, agent):
        """语速 WPM 应正确计算。"""
        # 2 秒音频，10 个词 → WPM = 10 / (2/60) = 300
        audio = self._make_pcm(2.0)
        result = await agent.analyze(
            "test-session", audio,
            "one two three four five six seven eight nine ten",
            confidence=0.9, turn_id="turn_001",
        )
        assert result.word_count == 10
        assert result.words_per_minute > 0
        assert result.duration_seconds == pytest.approx(2.0, abs=0.1)

    @pytest.mark.asyncio
    async def test_low_confidence_words(self, agent):
        """低置信度时标记实义词。"""
        audio = self._make_pcm(1.0)
        result = await agent.analyze(
            "test-session", audio,
            "I worked on the project",
            confidence=0.3, turn_id="turn_002",
        )
        assert len(result.low_confidence_words) > 0

    @pytest.mark.asyncio
    async def test_high_confidence_no_low_words(self, agent):
        """高置信度时不标记低置信度词。"""
        audio = self._make_pcm(1.0)
        result = await agent.analyze(
            "test-session", audio,
            "I worked on the project",
            confidence=0.95, turn_id="turn_003",
        )
        assert result.low_confidence_words == []

    @pytest.mark.asyncio
    async def test_empty_audio(self, agent):
        """无音频时返回零值。"""
        result = await agent.analyze(
            "test-session", b"",
            "hello world",
            confidence=0.8, turn_id="turn_004",
        )
        assert result.words_per_minute == 0.0
        assert result.pause_count == 0

    @pytest.mark.asyncio
    async def test_write_to_cache(self, agent):
        """发音分析结果应写入 cache。"""
        session_id = "test-pron-cache-001"
        audio = self._make_pcm(1.5)
        result = await agent.analyze(
            session_id, audio,
            "I have experience in Python",
            confidence=0.85, turn_id="turn_005",
        )
        await analysis_store.append_pronunciation(session_id, {
            "turnId": result.turn_id,
            "wordsPerMinute": result.words_per_minute,
            "pauseCount": result.pause_count,
            "lowConfidenceWords": result.low_confidence_words,
        })

        summary = await analysis_store.get_summary(session_id)
        assert summary is not None
        assert len(summary["pronunciation"]) == 1
        assert summary["pronunciation"][0]["turnId"] == "turn_005"

    @pytest.mark.asyncio
    async def test_singleton_available(self):
        """全局单例应可导入。"""
        assert pronunciation_agent is not None
