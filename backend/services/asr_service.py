"""ASR 服务 – 本地 Whisper（免费） + 能量VAD。

- 使用 OpenAI whisper 库本地运行，tiny 模型约 39MB，首次自动下载
- 无需 API Key，不依赖 ffmpeg（直接 numpy 数组输入）
- 转录在后台线程执行，不阻塞事件循环
"""

import asyncio
import base64
from typing import Optional

import numpy as np

from config import settings


# ---------------------------------------------------------------------------
# 纯 Python 能量检测 VAD
# ---------------------------------------------------------------------------
class EnergyVAD:
    """基于短时能量的语音活动检测器。"""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 30,
        silence_threshold_ms: int = 700,
        speech_start_frames: int = 3,
    ):
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * frame_ms / 1000)
        self.silence_frames = int(silence_threshold_ms / frame_ms)
        self.speech_start_frames = speech_start_frames

        self._energy_history: list[float] = []
        self._noise_floor: float = 0.5  # 极低初始值，自适应学习真实噪声底
        self._speech_threshold_ratio: float = 2.0  # 超过噪声底2倍即为语音
        self._debug_count: int = 0  # 诊断计数器

        self._silence_count: int = 0
        self._speech_count: int = 0
        self._is_speaking: bool = False
        self._speech_started: bool = False

    def _rms(self, samples: np.ndarray) -> float:
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))

    def process(self, pcm_bytes: bytes) -> tuple[bool, bool]:
        try:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float64)
        except Exception:
            return False, False

        if len(samples) < self.frame_size:
            return False, False

        samples = samples[:self.frame_size]
        energy = self._rms(samples)
        self._energy_history.append(energy)
        if len(self._energy_history) > 100:
            self._energy_history = self._energy_history[-100:]

        # 前 5 帧打印具体能量值，方便诊断音量
        self._debug_count += 1
        if self._debug_count <= 5:
            print(f"[VAD] frame#{self._debug_count} energy={energy:.1f} noise_floor={self._noise_floor:.1f}")

        if energy < self._noise_floor * 1.5:
            self._noise_floor = 0.95 * self._noise_floor + 0.05 * energy

        # 动态阈值：至少大于噪声底2倍，但不低于5（远低于正常语音）
        threshold = max(self._noise_floor * self._speech_threshold_ratio, 5.0)
        is_speech = energy > threshold

        turn_complete = False

        if is_speech:
            self._silence_count = 0
            self._speech_count += 1
            if self._speech_count >= self.speech_start_frames:
                self._is_speaking = True
                self._speech_started = True
        else:
            self._speech_count = 0
            if self._is_speaking:
                self._silence_count += 1
                if self._silence_count >= self.silence_frames:
                    self._is_speaking = False
                    self._silence_count = 0
                    if self._speech_started:
                        turn_complete = True
                        self._speech_started = False

        return is_speech, turn_complete

    def reset(self) -> None:
        self._silence_count = 0
        self._speech_count = 0
        self._is_speaking = False
        self._speech_started = False

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking


# ---------------------------------------------------------------------------
# ASR 服务 – 本地 Whisper（免费）
# ---------------------------------------------------------------------------
class ASRService:
    """本地 Whisper 语音识别 — 免费，无需 API Key，无需 ffmpeg。"""

    def __init__(self):
        self._model = None
        self._model_name: str = getattr(settings, "asr_model", "tiny") or "tiny"
        # 优先使用 tiny，也支持 tiny.en（纯英文更快）
        if self._model_name in ("whisper-1", "whisper"):
            self._model_name = "tiny"
        self._loaded: bool = False
        self._use_mock: bool = settings.enable_mock_asr

    def _ensure_model(self):
        """同步加载 Whisper 模型（首次调用时，约 2-3 秒）。"""
        if self._loaded:
            return
        try:
            import whisper
            print(f"[ASR] Loading local Whisper model: {self._model_name} (free, ~72MB)...")
            self._model = whisper.load_model(self._model_name)
            self._loaded = True
            print(f"[ASR] Whisper model loaded successfully: {self._model_name}")
        except Exception as exc:
            print(f"[ASR] Failed to load Whisper model: {exc}")
            print(f"[ASR] Falling back to mock mode — use text.input")
            self._use_mock = True

    async def transcribe(self, pcm_bytes: bytes, sample_rate: int = 16000) -> Optional[str]:
        """将 PCM 音频转录为文本（后台线程执行，不阻塞事件循环）。

        Args:
            pcm_bytes: 16-bit PCM 单声道数据
            sample_rate: 采样率

        Returns:
            识别文本，失败时返回 None
        """
        if self._use_mock:
            return None

        if not pcm_bytes or len(pcm_bytes) < sample_rate * 0.3 * 2:
            # 音频太短（< 0.3 秒），可能是噪音
            return None

        self._ensure_model()
        if self._model is None:
            return None

        try:
            # 将 PCM bytes 转为 float32 numpy 数组（Whisper 期望的格式）
            audio_np = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            # 在线程池中运行（Whisper 推理是 CPU 密集操作）
            result = await asyncio.to_thread(
                self._model.transcribe,
                audio_np,
                language="en",
                fp16=False,
                verbose=False,
            )
            text = result.get("text", "").strip() if result else ""
            return text if text else None
        except Exception as exc:
            print(f"[ASR] Transcription failed: {exc}")
            return None

    def decode_base64_pcm(self, payload: str) -> bytes:
        try:
            return base64.b64decode(payload)
        except Exception:
            return b""

    @property
    def is_available(self) -> bool:
        """模型是否成功加载（非 mock 模式 且 模型已加载）。"""
        return not self._use_mock and self._loaded


# 全局单例
asr_service = ASRService()
