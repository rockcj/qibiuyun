"""TTS 服务 – EdgeTTS 主路径 + Mock 降级。

负责：
- 按标点分句后流式合成语音
- EdgeTTS 免费在线 TTS
- Mock 模式只返回空音频，前端展示文本
"""

import asyncio
import base64
import io
import re
from typing import AsyncGenerator, Optional

from config import settings


# 英文分句正则（按 .!? 断句，保留缩写）
_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# 过滤 emoji 和非语音字符（EdgeTTS 无法正确合成）
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # 表情符号
    "\U0001F300-\U0001F5FF"  # 杂项符号
    "\U0001F680-\U0001F6FF"  # 交通和地图
    "\U0001F1E0-\U0001F1FF"  # 国旗
    "\U00002702-\U000027B0"  # 装饰符号
    "\U000024C2-\U0001F251"  # 其他
    "\U0001F900-\U0001F9FF"  # 补充符号
    "\U0001FA00-\U0001FA6F"  # 象棋符号
    "\U0001FA70-\U0001FAFF"  # 扩展A
    "\U00002600-\U000026FF"  # 杂项
    "\U0000FE00-\U0000FE0F"  # 变体选择器
    "\U0000200D"              # 零宽连接符
    "]+",
    flags=re.UNICODE,
)


class TTSService:
    """语音合成服务 – EdgeTTS 或 Mock 降级。"""

    def __init__(self):
        self._voice: str = settings.tts_voice
        self._use_mock: bool = settings.enable_mock_tts
        self._provider: str = settings.tts_provider

        if self._provider == "edgeTts" and not self._use_mock:
            print(f"[TTS] EdgeTTS ready, voice: {self._voice}")
        else:
            print(f"[TTS] Running in mock mode — text display only")
            self._use_mock = True

    async def synthesize_stream(
        self, text: str
    ) -> AsyncGenerator[tuple[str, Optional[str]], None]:
        """按句子流式合成语音。

        Yields:
            (sentence_text, base64_audio_chunk)
            音频为 base64 编码的 MP3 片段，mock 模式下为 None
        """
        sentences = self._split_sentences(text)
        if not sentences:
            return

        for sentence in sentences:
            if not sentence.strip():
                continue

            # 过滤 emoji，避免 TTS 合成出乱码杂音
            sentence = _EMOJI_PATTERN.sub("", sentence).strip()
            if not sentence:
                continue

            if self._use_mock:
                # Mock 模式：只返回文本，不生成音频
                yield (sentence, None)
                await asyncio.sleep(0.05)  # 模拟流式延迟
                continue

            try:
                audio_chunk = await self._synthesize_sentence(sentence)
                yield (sentence, audio_chunk)
            except Exception as exc:
                print(f"[TTS] Synthesis failed for '{sentence[:40]}...': {exc}")
                # 降级：返回文本但没有音频
                yield (sentence, None)

    async def _synthesize_sentence(self, text: str) -> Optional[str]:
        """调用 EdgeTTS 合成单句，返回 base64 MP3。"""
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text, self._voice)
            audio_chunks: list[bytes] = []

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])

            if audio_chunks:
                combined = b"".join(audio_chunks)
                return base64.b64encode(combined).decode("utf-8")
            return None
        except ImportError:
            print("[TTS] edge-tts not installed, using mock")
            self._use_mock = True
            return None
        except Exception:
            raise

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """按标点符号分句，保留每句的标点。"""
        # 先处理简单情况：按 . ! ? 分割
        parts = _SENTENCE_PATTERN.split(text)
        if len(parts) == 1:
            # 没有明显的句边界，尝试按其他标点分
            # 按逗号、分号分成短句
            sub_parts = re.split(r"(?<=[,;])\s+", text)
            if len(sub_parts) > 1:
                return [p.strip() for p in sub_parts if p.strip()]
            return [text.strip()]

        # 重新拼接（re.split 会丢失分隔符）
        result: list[str] = []
        # 用 finditer 代替 split 以保留标点
        last_end = 0
        for match in _SENTENCE_PATTERN.finditer(text):
            sentence = text[last_end : match.start()].strip()
            if sentence:
                result.append(sentence)
            last_end = match.start() + 1  # 跳过空格
        final = text[last_end:].strip()
        if final:
            result.append(final)
        return result if result else [text.strip()]


# 全局单例
tts_service = TTSService()
