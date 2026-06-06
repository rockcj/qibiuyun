"""Pronunciation Agent — 异步发音分析，不阻塞主链路。

从音频计算：
- 语速 WPM（词数 / 时长分钟）
- 停顿次数（静音连续段 > pause_silence_ms）
- 低置信度关键词标记
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from config import settings
from services.asr_service import EnergyVAD


@dataclass
class PronunciationResult:
    """单轮发音分析结果。"""
    turn_id: str = ""
    words_per_minute: float = 0.0
    pause_count: int = 0
    low_confidence_words: list = field(default_factory=list)
    duration_seconds: float = 0.0
    word_count: int = 0
    overall_confidence: float = 0.0


class PronunciationAgent:
    """异步发音分析 Agent。"""

    def __init__(self):
        self._sample_rate = 16000
        self._frame_ms = 30
        self._pause_threshold_ms = settings.pause_silence_ms
        self._low_conf_threshold = settings.pronunciation_low_confidence_threshold

    def _count_pauses(self, pcm_bytes: bytes) -> int:
        """检测音频中停顿次数（静音连续段超过阈值）。"""
        if not pcm_bytes:
            return 0

        try:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float64)
        except Exception:
            return 0

        frame_size = int(self._sample_rate * self._frame_ms / 1000)
        pause_frames_needed = int(self._pause_threshold_ms / self._frame_ms)

        # 自适应噪声底
        noise_floor = 5.0
        pause_count = 0
        silence_run = 0
        in_speech = False

        for i in range(0, len(samples) - frame_size, frame_size):
            frame = samples[i:i + frame_size]
            energy = float(np.sqrt(np.mean(frame ** 2)))

            if energy < noise_floor * 1.5:
                noise_floor = 0.95 * noise_floor + 0.05 * energy

            threshold = max(noise_floor * 3.0, 12.0)
            is_speech = energy > threshold

            if is_speech:
                if silence_run >= pause_frames_needed and in_speech:
                    pause_count += 1
                silence_run = 0
                in_speech = True
            else:
                silence_run += 1

        return pause_count

    def _extract_low_confidence_words(
        self, transcript: str, confidence: float
    ) -> list[str]:
        """当整体置信度低于阈值时，标记所有词为低置信度。"""
        if confidence >= self._low_conf_threshold:
            return []
        words = transcript.split()
        # 过滤掉语气词，只标记实义词
        from services.realtime.asr_filter import FILLER_WORDS
        return [w.strip(".,!?;:'\"") for w in words
                if w.strip(".,!?;:'\"").lower() not in FILLER_WORDS]

    async def analyze(
        self,
        session_id: str,
        audio_bytes: bytes,
        transcript: str,
        confidence: float,
        turn_id: str = "",
    ) -> PronunciationResult:
        """分析单轮发音数据。

        Args:
            session_id: 会话 ID
            audio_bytes: PCM 16-bit 单声道音频
            transcript: ASR 转录文本
            confidence: ASR 综合置信度
            turn_id: 轮次 ID

        Returns:
            PronunciationResult
        """
        # 计算音频时长（秒）
        duration_sec = len(audio_bytes) / (self._sample_rate * 2) if audio_bytes else 0.0
        word_count = len(transcript.split())

        # 语速 WPM
        wpm = (word_count / duration_sec * 60) if duration_sec > 0.5 else 0.0

        # 停顿次数
        pause_count = self._count_pauses(audio_bytes) if audio_bytes else 0

        # 低置信度词
        low_conf_words = self._extract_low_confidence_words(transcript, confidence)

        return PronunciationResult(
            turn_id=turn_id,
            words_per_minute=round(wpm, 1),
            pause_count=pause_count,
            low_confidence_words=low_conf_words,
            duration_seconds=round(duration_sec, 2),
            word_count=word_count,
            overall_confidence=confidence,
        )


# 全局单例
pronunciation_agent = PronunciationAgent()
