"""火山引擎全双工语音事件 → OfferGPT WebSocket 协议桥接。

云端模型同时下发「用户转写文本」「AI 回复文本」「AI 语音」，而前端既有的
消息协议是按「一轮」组织的（``asr.final`` 开一轮 → ``agent.text.delta`` →
``tts.audio.delta``）。本模块负责：

1. 用 ``conversation.item.input_audio_transcription.completed`` 开启一轮；
2. 若模型先于转写结果开始说话（低延迟场景），先把文本/音频**缓存在这一轮内**，
   等 ``asr.final`` 发出后再按序补发，避免前端丢弃早到的消息；
3. 把音频统一标记为 ``pcm16 / 24000Hz``，与前端的 MP3 通道区分。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from services.volcengine.duplex_client import extract_error

# 与前端约定的下行音频参数
AUDIO_CODEC = "pcm16"
AUDIO_SAMPLE_RATE = 24000


@dataclass
class BridgeResult:
    """一次事件处理的结果。"""

    messages: list[dict] = field(default_factory=list)
    # 本轮用户最终文本（仅在 asr.final 发出时有值）
    transcript_final: Optional[str] = None
    # 当前轮次 id
    turn_id: Optional[str] = None
    # AI 完整回复文本（响应文本结束时给出）
    response_text: Optional[str] = None
    # 服务端错误信息
    error: Optional[str] = None
    # 会话被服务端关闭
    closed: bool = False


class DuplexEventBridge:
    """把火山引擎下行事件翻译为前端可消费的消息列表。"""

    def __init__(
        self,
        session_id: str,
        new_turn_id: Callable[[], str],
        *,
        pending_limit: int = 400,
    ) -> None:
        self.session_id = session_id
        self._new_turn_id = new_turn_id
        self._pending_limit = pending_limit

        self.turn_id: Optional[str] = None
        self._text_parts: list[str] = []
        self._text_open = False
        # 当前轮是否已经向客户端输出过文本（用于识别「主动播报」这类无轮次内容）
        self._turn_has_output = False
        self._pending_text: list[str] = []
        self._pending_audio: list[str] = []
        self._partial_transcript = ""
        self._last_partial = ""

    # ------------------------------------------------------------------
    # 对外入口
    # ------------------------------------------------------------------
    def handle(self, event: dict) -> BridgeResult:
        """处理一条下行事件，返回需要下发的消息。"""
        result = BridgeResult(turn_id=self.turn_id)
        etype = str(event.get("type") or "")

        if etype == "session.created":
            return result

        if etype == "conversation.item.input_audio_transcription.started":
            self._partial_transcript = ""
            return result

        if etype == "conversation.item.input_audio_transcription.delta":
            text = self._accumulate_partial(event)
            if text and text != self._last_partial:
                self._last_partial = text
                result.messages.append({
                    "type": "asr.partial",
                    "sessionId": self.session_id,
                    "turnId": self.turn_id or "pending",
                    "partialTranscript": text,
                })
            return result

        if etype == "conversation.item.input_audio_transcription.completed":
            transcript = str(event.get("transcript") or self._accumulate_partial(event)).strip()
            self._partial_transcript = ""
            self._last_partial = ""
            if not transcript:
                result.messages.append({
                    "type": "asr.no_result",
                    "sessionId": self.session_id,
                    "message": "未检测到有效语音，请重试",
                })
                return result
            result.messages.extend(self._begin_turn(transcript))
            result.transcript_final = transcript
            result.turn_id = self.turn_id
            return result

        if etype == "conversation.item.input_audio_transcription.failed":
            self._partial_transcript = ""
            self._last_partial = ""
            result.messages.append({
                "type": "asr.no_result",
                "sessionId": self.session_id,
                "message": "语音识别失败，请重试",
                "reason": "asr_failed",
            })
            return result

        if etype == "response.output_text.delta":
            delta = str(event.get("delta") or "")
            if not delta:
                return result
            if self.turn_id is None:
                self._buffer_text(delta)
            else:
                self._text_parts.append(delta)
                self._text_open = True
                self._turn_has_output = True
                result.messages.append(self._text_delta(delta))
            return result

        if etype == "response.output_text.done":
            text = str(event.get("text") or "")
            if self.turn_id is None or not self._turn_has_output:
                # 无用户转写轮次 / 本轮没有向客户端输出文本（如主动播报）：
                # 不结束轮次、不污染对话历史；音频在下行 delta 时已直接下发
                self._pending_text.clear()
                result.response_text = None
                return result
            if not self._text_parts and text:
                self._text_parts.append(text)
            if self._text_open:
                self._text_open = False
                result.messages.append(self._text_done())
            # 本轮文本输出结束：后续主动播报不再归入这一轮
            self._turn_has_output = False
            result.response_text = "".join(self._text_parts).strip()
            return result

        if etype == "response.output_audio.delta":
            payload = str(event.get("delta") or event.get("audio") or "")
            if not payload:
                return result
            if self.turn_id is None:
                self._buffer_audio(payload)
            else:
                result.messages.append(self._audio_delta(payload))
            return result

        if etype == "response.output_audio.done":
            if self.turn_id is None:
                self._pending_audio.clear()
            return result

        if etype == "response.canceled":
            if self.turn_id is not None and self._text_open:
                self._text_open = False
                result.messages.append(self._text_done())
            return result

        if etype in ("session.closed", "session.finished"):
            result.closed = True
            return result

        if etype == "error":
            code, message = extract_error(event)
            result.error = f"{code}: {message}" if code else (message or "云端语音错误")
            return result

        return result

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _accumulate_partial(self, event: dict) -> str:
        transcript = str(event.get("transcript") or "")
        delta = str(event.get("delta") or "")
        if transcript:
            self._partial_transcript = transcript
        elif delta:
            self._partial_transcript += delta
        return self._partial_transcript

    def _begin_turn(self, transcript: str) -> list[dict]:
        self.turn_id = self._new_turn_id()
        self._text_parts = []
        self._text_open = False
        self._turn_has_output = False
        self._last_partial = ""

        messages: list[dict] = [{
            "type": "asr.final",
            "sessionId": self.session_id,
            "turnId": self.turn_id,
            "finalTranscript": transcript,
            "confidence": 1.0,
        }]

        # 补发在转写结果之前到达的模型输出
        for delta in self._pending_text:
            self._text_parts.append(delta)
            self._text_open = True
            self._turn_has_output = True
            messages.append(self._text_delta(delta))
        self._pending_text.clear()

        for payload in self._pending_audio:
            messages.append(self._audio_delta(payload))
        self._pending_audio.clear()

        return messages

    def _buffer_text(self, delta: str) -> None:
        if len(self._pending_text) >= self._pending_limit:
            self._pending_text.pop(0)
        self._pending_text.append(delta)

    def _buffer_audio(self, payload: str) -> None:
        if len(self._pending_audio) >= self._pending_limit:
            self._pending_audio.pop(0)
        self._pending_audio.append(payload)

    def _text_delta(self, delta: str) -> dict:
        return {
            "type": "agent.text.delta",
            "sessionId": self.session_id,
            "turnId": self.turn_id,
            "delta": delta,
        }

    def _text_done(self) -> dict:
        return {
            "type": "agent.text.done",
            "sessionId": self.session_id,
            "turnId": self.turn_id,
        }

    def _audio_delta(self, payload: str) -> dict:
        return {
            "type": "tts.audio.delta",
            "sessionId": self.session_id,
            "turnId": self.turn_id,
            "codec": AUDIO_CODEC,
            "sampleRate": AUDIO_SAMPLE_RATE,
            "payload": payload,
        }
