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
        speech_start_frames: int = 10,  # 10 帧 × 30ms = 300ms 最小语音，防瞬时噪音
    ):
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * frame_ms / 1000)
        self.silence_frames = int(silence_threshold_ms / frame_ms)
        self.speech_start_frames = speech_start_frames

        self._energy_history: list[float] = []
        self._noise_floor: float = 0.5  # 极低初始值，自适应学习真实噪声底
        self._speech_threshold_ratio: float = 3.0  # 超过噪声底 3 倍即为语音（提高防误触发）
        self._debug_count: int = 0  # 诊断计数器

        self._silence_count: int = 0
        self._speech_count: int = 0
        self._is_speaking: bool = False
        self._speech_started: bool = False

    def _rms(self, samples: np.ndarray) -> float:
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))

    @staticmethod
    def _rms_static(pcm_bytes: bytes) -> float:
        """从 PCM bytes 直接计算 RMS 能量，无需实例化。"""
        try:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float64)
            if len(samples) == 0:
                return 0.0
            return float(np.sqrt(np.mean(samples ** 2)))
        except Exception:
            return 0.0

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

        # 动态阈值：至少大于噪声底 3 倍，但不低于 12（防止静音环境能量误判）
        threshold = max(self._noise_floor * self._speech_threshold_ratio, 12.0)
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
        # tiny(39MB) < base(74MB) < small(244MB) < medium(775MB) < large(1.5GB)
        self._model_name: str = getattr(settings, "asr_model", "small") or "small"
        if self._model_name in ("whisper-1", "whisper", "tiny"):
            self._model_name = "small"
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

    async def transcribe(
        self, pcm_bytes: bytes, sample_rate: int = 16000
    ) -> tuple[Optional[str], float]:
        """将 PCM 音频转录为文本（后台线程执行，不阻塞事件循环）。

        Args:
            pcm_bytes: 16-bit PCM 单声道数据
            sample_rate: 采样率

        Returns:
            (识别文本, 置信度 0-1)，失败时返回 (None, 0.0)
        """
        if self._use_mock:
            return None, 0.0

        if not pcm_bytes or len(pcm_bytes) < sample_rate * 0.3 * 2:
            # 音频太短（< 0.3 秒），可能是噪音
            return None, 0.0

        self._ensure_model()
        if self._model is None:
            return None, 0.0

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

            # 从 segments 计算置信度
            confidence = self._compute_confidence(result) if result else 0.0

            return (text if text else None), confidence
        except Exception as exc:
            print(f"[ASR] Transcription failed: {exc}")
            return None, 0.0

    @staticmethod
    def _compute_confidence(result: dict) -> float:
        """从 Whisper 结果中计算置信度分数（0-1）。

        综合考虑三个指标：
        - no_speech_prob: 非语音概率（越低越好）
        - avg_logprob: 平均对数概率（越高越好）
        - compression_ratio: 压缩比（极端值表示幻觉）
        """
        segments = result.get("segments", [])
        if not segments:
            return 0.5  # 无分段信息，中性分数

        # 计算各段的平均指标
        no_speech_probs = []
        avg_logprobs = []
        compression_ratios = []

        for seg in segments:
            nsp = seg.get("no_speech_prob")
            alp = seg.get("avg_logprob")
            cr = seg.get("compression_ratio")

            if nsp is not None:
                no_speech_probs.append(nsp)
            if alp is not None:
                avg_logprobs.append(alp)
            if cr is not None:
                compression_ratios.append(cr)

        # 非语音概率：取最差（最大）的段
        max_nsp = max(no_speech_probs) if no_speech_probs else 0.5
        # 高 no_speech_prob → 低置信度
        speech_conf = 1.0 - max_nsp

        # 平均对数概率：取各段均值
        mean_alp = sum(avg_logprobs) / len(avg_logprobs) if avg_logprobs else -1.0
        # 映射 avg_logprob 到 0-1：-2.0 → 0，0.0 → 1
        logp_conf = max(0.0, min(1.0, (mean_alp + 2.0) / 2.0))

        # 压缩比：极端值（>5 或 <0.3）表示幻觉
        mean_cr = sum(compression_ratios) / len(compression_ratios) if compression_ratios else 1.0
        if mean_cr > 5.0:
            cr_conf = 0.0  # 极高压缩比 = 大概率幻觉
        elif mean_cr < 0.3:
            cr_conf = 0.3  # 极低压缩比 = 可能有问题
        else:
            cr_conf = 1.0

        # 综合置信度 = 加权平均（语音概率权重最高）
        confidence = speech_conf * 0.5 + logp_conf * 0.3 + cr_conf * 0.2
        return round(max(0.0, min(1.0, confidence)), 3)

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
