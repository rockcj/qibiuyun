"""火山引擎 · 豆包端到端实时语音（Seeduplex 全双工）客户端。

协议说明（官方文档：docs.volcengine.com/docs/doubao-voice/
end-to-end-real-time-voice-full-duplex-version）：

- 传输：WebSocket **纯 JSON 文本帧**，一帧一事件，事件类型由顶层 ``type`` 标识；
- 鉴权：请求头 ``X-Api-Key``（新版控制台 API Key），可选 ``X-Api-App-Id``、
  ``X-Api-Resource-Id``、``X-Api-Connect-Id``；
- 上行：``session.create`` / ``input_audio_buffer.append`` /
  ``input_audio_mute.commit`` / ``speech_text_buffer.commit`` /
  ``response.cancel`` / ``session.close``；
- 下行：``session.created`` / ``conversation.item.input_audio_transcription.*`` /
  ``response.output_text.*`` / ``response.output_audio.*`` / ``response.done`` /
  ``error``；
- 音频：上行 16kHz 单声道 int16 小端（建议 20ms/包），下行默认 24kHz
  ``pcm_s16le``，均以 base64 内嵌在 JSON 字段中。

本模块不依赖任何官方 Python SDK（官方仅提供 Android/iOS/Web/Windows 客户端 SDK
与示例工程，服务端 Python 需自行实现协议），因此直接对接原始 WebSocket 接口。
"""

from __future__ import annotations

import asyncio
import base64
import copy
import json
import uuid
from collections import deque
from typing import Any, AsyncIterator, Deque, Optional

from config import settings

# 输入音频固定 16kHz（服务端要求），输出固定 24kHz pcm_s16le
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000

DEFAULT_WS_URL = "wss://openspeech.bytedance.com/api/v3/duplex/realtime/dialogue"
DEFAULT_MODEL = "1.2.6.1"


class DuplexError(RuntimeError):
    """云端语音会话建立/通信失败。"""


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并字典，override 优先。"""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def build_session_object(
    *,
    model: str = DEFAULT_MODEL,
    voice: str = "",
    speed: Optional[int] = None,
    instructions: Optional[str] = None,
    overrides: Optional[dict] = None,
) -> dict:
    """构造 ``session.create`` 事件中的 ``session`` 对象。

    Args:
        model: 模型名，全双工版本固定 ``1.2.6.1``。
        voice: 音色名，空字符串时不下发（使用服务端默认音色）。
        speed: 语速 [-50, 100]，None/0 时不下发。
        instructions: 系统提示词（模型回复内容与语气）。
        overrides: 可选覆盖字段（深合并），用于透传 extension 等高级参数。
    """
    session: dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "audio": {
            "input": {"format": {"type": "pcm", "rate": INPUT_SAMPLE_RATE}},
            "output": {
                "format": {"type": "pcm_s16le", "rate": OUTPUT_SAMPLE_RATE},
            },
        },
    }
    if voice:
        session["audio"]["output"]["voice"] = voice
    if speed:
        session["audio"]["output"]["speed"] = int(speed)
    if instructions:
        session["instructions"] = instructions
    if overrides:
        session = _deep_merge(session, overrides)
    return session


def build_session_create_event(
    *,
    model: str = DEFAULT_MODEL,
    voice: str = "",
    speed: Optional[int] = None,
    instructions: Optional[str] = None,
    session_id: Optional[str] = None,
    overrides: Optional[dict] = None,
) -> dict:
    """构造完整的 ``session.create`` 事件。"""
    session = build_session_object(
        model=model,
        voice=voice,
        speed=speed,
        instructions=instructions,
        overrides=overrides,
    )
    if session_id:
        session["id"] = session_id
    return {"type": "session.create", "session": session}


def extract_error(event: dict) -> tuple[Optional[int], str]:
    """从下行事件中提取 (code, message)，非错误事件返回 (None, "")。"""
    error = event.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        message = error.get("message") or json.dumps(error, ensure_ascii=False)
        return (int(code) if isinstance(code, (int, str)) and str(code).isdigit() else None,
                str(message))
    if isinstance(error, str) and error:
        return None, error
    if event.get("type") == "error":
        code = event.get("code") or event.get("status_code")
        message = event.get("message") or "unknown error"
        try:
            code = int(code) if code is not None else None
        except (TypeError, ValueError):
            code = None
        return code, str(message)
    return None, ""


class VolcengineDuplexSession:
    """单个全双工语音会话（一次 WebSocket 连接 + 一个 session）。"""

    def __init__(
        self,
        *,
        api_key: str,
        ws_url: str = DEFAULT_WS_URL,
        app_id: str = "",
        resource_id: str = "",
        model: str = DEFAULT_MODEL,
        voice: str = "",
        speed: Optional[int] = None,
        instructions: Optional[str] = None,
        session_overrides: Optional[dict] = None,
        connect_timeout: float = 10.0,
        logger=print,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.ws_url = (ws_url or DEFAULT_WS_URL).strip()
        self.app_id = (app_id or "").strip()
        self.resource_id = (resource_id or "").strip()
        self.model = model or DEFAULT_MODEL
        self.voice = voice or ""
        self.speed = speed
        self.instructions = instructions
        self.session_overrides = session_overrides or {}
        self.connect_timeout = connect_timeout
        self._log = logger

        self.connect_id = str(uuid.uuid4())
        self.session_id: Optional[str] = None
        self.log_id: Optional[str] = None

        self._ws = None
        self._pending: Deque[dict] = deque()
        self._muted = False
        self._closed = False
        self._event_seq = 0

    # ------------------------------------------------------------------
    # 构造
    # ------------------------------------------------------------------
    @classmethod
    def from_settings(
        cls, *, instructions: Optional[str] = None, logger=print
    ) -> "VolcengineDuplexSession":
        """按后端配置创建实例。"""
        overrides: dict = {}
        raw = (settings.volcengine_speech_session_json or "").strip()
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    # 允许直接给 {"session": {...}} 或直接给 session 对象
                    overrides = parsed.get("session", parsed)
            except json.JSONDecodeError as exc:
                logger(f"[VOLC] VOLCENGINE_SPEECH_SESSION_JSON 解析失败: {exc}")

        return cls(
            api_key=settings.volcengine_speech_api_key,
            ws_url=settings.volcengine_speech_ws_url,
            app_id=settings.volcengine_speech_app_id,
            resource_id=settings.volcengine_speech_resource_id,
            model=settings.volcengine_speech_model,
            voice=settings.volcengine_speech_voice,
            speed=settings.volcengine_speech_speed,
            instructions=instructions,
            session_overrides=overrides,
            connect_timeout=settings.volcengine_speech_connect_timeout_sec,
            logger=logger,
        )

    # ------------------------------------------------------------------
    # 连接
    # ------------------------------------------------------------------
    def _headers(self) -> dict:
        headers = {
            "X-Api-Key": self.api_key,
            "X-Api-Connect-Id": self.connect_id,
        }
        if self.app_id:
            headers["X-Api-App-Id"] = self.app_id
        if self.resource_id:
            headers["X-Api-Resource-Id"] = self.resource_id
        return headers

    async def connect(self) -> dict:
        """建立 WebSocket 连接并完成 ``session.create`` 握手。

        Returns:
            握手成功后服务端返回的 ``session.created`` 事件体。
        """
        if not self.api_key:
            raise DuplexError("未配置 VOLCENGINE_SPEECH_API_KEY")

        try:
            import websockets
        except ImportError as exc:  # pragma: no cover - 依赖缺失时给出明确提示
            raise DuplexError("缺少 websockets 依赖，请 pip install websockets") from exc

        try:
            self._ws = await websockets.connect(
                self.ws_url,
                additional_headers=self._headers(),
                max_size=None,
                open_timeout=self.connect_timeout,
                ping_interval=20,
                ping_timeout=20,
            )
        except TypeError:
            # 兼容旧版 websockets（参数名为 extra_headers）
            self._ws = await websockets.connect(
                self.ws_url,
                extra_headers=self._headers(),
                max_size=None,
                open_timeout=self.connect_timeout,
            )
        except Exception as exc:
            raise DuplexError(f"连接火山引擎失败: {exc}") from exc

        self.log_id = self._read_log_id()
        event = build_session_create_event(
            model=self.model,
            voice=self.voice,
            speed=self.speed,
            instructions=self.instructions,
            overrides=self.session_overrides,
        )
        try:
            await self._ws.send(json.dumps(event, ensure_ascii=False))
        except Exception as exc:
            await self.close()
            raise DuplexError(f"发送 session.create 失败: {exc}") from exc

        return await self._await_session_created()

    def _read_log_id(self) -> Optional[str]:
        try:
            response = getattr(self._ws, "response", None)
            headers = getattr(response, "headers", None)
            if headers is not None:
                return headers.get("X-Tt-Logid") or headers.get("x-tt-logid")
        except Exception:
            pass
        return None

    async def _await_session_created(self) -> dict:
        """等待 session.created，期间缓存其它事件。"""
        deadline = asyncio.get_running_loop().time() + self.connect_timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                await self.close()
                raise DuplexError("等待 session.created 超时")
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
            except asyncio.TimeoutError as exc:
                await self.close()
                raise DuplexError("等待 session.created 超时") from exc
            except Exception as exc:
                await self.close()
                raise DuplexError(f"握手期间连接中断: {exc}") from exc

            event = self._decode(raw)
            if event is None:
                continue
            etype = event.get("type", "")
            if etype == "session.created":
                session = event.get("session") or {}
                self.session_id = session.get("id") or event.get("session_id") or event.get("id")
                self._log(
                    f"[VOLC] duplex session created: {self.session_id} "
                    f"(model={self.model}, logid={self.log_id})"
                )
                return event
            code, message = extract_error(event)
            if etype == "error" or code:
                await self.close()
                raise DuplexError(f"session.create 被拒绝: {code} {message}")
            # 其它事件（理论上握手阶段不会出现）缓存，交给 events() 消费
            self._pending.append(event)

    @staticmethod
    def _decode(raw: Any) -> Optional[dict]:
        if isinstance(raw, (bytes, bytearray)):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                return None
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    # ------------------------------------------------------------------
    # 上行
    # ------------------------------------------------------------------
    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._closed

    async def _send(self, event: dict) -> None:
        if not self.connected:
            raise DuplexError("云端语音会话未连接")
        self._event_seq += 1
        event.setdefault("event_id", f"{self.connect_id}-{self._event_seq}")
        await self._ws.send(json.dumps(event, ensure_ascii=False))

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """上行一包 16kHz int16 PCM 音频。"""
        if not pcm_bytes or not self.connected or self._muted:
            return
        await self._send({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(pcm_bytes).decode("ascii"),
        })

    async def say(self, text: str) -> None:
        """让模型直接朗读一段文本（用于开场白 / 不活动提醒）。"""
        text = (text or "").strip()
        if not text or not self.connected:
            return
        await self._send({"type": "speech_text_buffer.commit", "text": text})

    async def set_muted(self, muted: bool) -> None:
        """麦克风关闭/恢复：交替发送 mute/unmute，避免服务端音频流超时。"""
        if not self.connected or self._muted == muted:
            return
        self._muted = muted
        event_type = "input_audio_mute.commit" if muted else "input_audio_unmute.commit"
        try:
            await self._send({"type": event_type})
        except Exception as exc:
            self._log(f"[VOLC] 发送 {event_type} 失败: {exc}")

    async def cancel_response(self) -> None:
        """打断模型当前回复（用户插话）。"""
        if not self.connected:
            return
        try:
            await self._send({"type": "response.cancel"})
        except Exception as exc:
            self._log(f"[VOLC] 发送 response.cancel 失败: {exc}")

    # ------------------------------------------------------------------
    # 下行
    # ------------------------------------------------------------------
    async def events(self) -> AsyncIterator[dict]:
        """迭代下行事件；连接关闭时正常结束。"""
        while self._pending:
            yield self._pending.popleft()

        while self.connected:
            try:
                raw = await self._ws.recv()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # ConnectionClosed 等
                self._log(f"[VOLC] 下行连接结束: {type(exc).__name__}")
                return
            event = self._decode(raw)
            if event is not None:
                yield event

    async def close(self) -> None:
        """关闭会话并断开连接（幂等）。"""
        if self._closed:
            return
        self._closed = True
        ws = self._ws
        self._ws = None
        if ws is None:
            return
        try:
            if self.session_id:
                await asyncio.wait_for(
                    ws.send(json.dumps({"type": "session.close"}, ensure_ascii=False)),
                    timeout=2,
                )
        except Exception:
            pass
        try:
            await asyncio.wait_for(ws.close(), timeout=3)
        except Exception:
            pass
        self._log(f"[VOLC] duplex session closed: {self.session_id}")
