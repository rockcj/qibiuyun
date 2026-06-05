"""WebSocket handler – 实时语音对话管线。

完整链路：
  audio.input → VAD 检测 → 音频累积 → Turn 完成 →
  ASR 转录 → LLM 流式生成 → TTS 分句合成 → 前端播放
  text.input → 直接进入 LLM → TTS 管线（Demo 主路径）

消息协议符合 docs/agent-team/api-contract.md 定义。
"""

import asyncio
import json
import time
import uuid
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from config import settings
from services.asr_service import EnergyVAD, asr_service
from services.cache_service import cache
from services.conversation_service import conversation_service
from services.tts_service import tts_service


# ---------------------------------------------------------------------------
# 会话状态
# ---------------------------------------------------------------------------
class SessionState:
    """单个 WebSocket 会话的运行时状态。"""

    def __init__(self, session_id: str, scene_config: Optional[dict] = None):
        self.session_id = session_id
        self.scene_config = scene_config or {}
        self.connected_at = time.time()

        # VAD（500ms 静音判定 turn 结束，比 700ms 更灵敏）
        self.vad = EnergyVAD(silence_threshold_ms=500)
        self.audio_buffer: bytearray = bytearray()

        # 对话
        self.history: list[dict] = []  # [{"role": "user", "content": "..."}, ...]
        self.system_prompt: str = ""
        self.turn_count: int = 0

        # 处理状态
        self.is_processing: bool = False  # 是否正在处理一轮对话
        self.pending_text: Optional[str] = None  # 排队中的文本输入

        # 指标
        self.message_count: int = 0
        self.last_activity: float = time.time()

    def add_to_history(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        # 最多保留 10 轮 (20 条消息)
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def to_dict(self) -> dict:
        return {
            "sessionId": self.session_id,
            "turnCount": self.turn_count,
            "connectedAt": self.connected_at,
            "lastActivity": self.last_activity,
        }


# ---------------------------------------------------------------------------
# Connection Manager
# ---------------------------------------------------------------------------
class ConnectionManager:
    """WebSocket 连接管理 + 实时语音管线编排。"""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._states: dict[str, SessionState] = {}

    # ------------------------------------------------------------------
    # 连接生命周期
    # ------------------------------------------------------------------
    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()

        # 尝试从 Redis 恢复会话状态
        scene_config = await self._load_session_config(session_id)

        state = SessionState(session_id, scene_config)
        if scene_config:
            state.system_prompt = conversation_service.build_system_prompt(scene_config)
            print(f"[WS] Session restored from cache: {session_id}")

        self._connections[session_id] = websocket
        self._states[session_id] = state

        print(f"[WS] Client connected: {session_id} (total: {self.active_connections})")

    async def disconnect(self, session_id: str) -> None:
        """断开连接，持久化会话状态。"""
        self._connections.pop(session_id, None)
        state = self._states.pop(session_id, None)

        if state:
            # 保存会话状态到 Redis
            await self._save_session_state(state)
            duration = time.time() - state.connected_at
            print(
                f"[WS] Client disconnected: {session_id} "
                f"(turns: {state.turn_count}, duration: {duration:.0f}s)"
            )

    # ------------------------------------------------------------------
    # 消息路由
    # ------------------------------------------------------------------
    async def handle_message(self, session_id: str, raw: str) -> dict:
        """解析并路由 WebSocket 消息。"""
        state = self._states.get(session_id)
        if state is None:
            return {"error": "Session not found"}

        state.message_count += 1
        state.last_activity = time.time()

        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON"}

        msg_type = message.get("type")

        if msg_type == "audio.input":
            return await self._handle_audio_input(session_id, state, message)

        elif msg_type == "text.input":
            result = await self._handle_text_input(session_id, state, message)
            # 处理完文本输入后，检查是否有积压音频需要触发
            await self._maybe_trigger_turn(session_id, state)
            return result

        elif msg_type == "control.finish":
            return await self._handle_finish(session_id, state, message)

        elif msg_type == "ping":
            # 心跳时也检查积压音频
            await self._maybe_trigger_turn(session_id, state)
            await self.send_message(session_id, {"type": "pong", "sessionId": session_id})
            return {"status": "ok"}

        return {"error": f"Unknown message type: {msg_type}"}

    # ------------------------------------------------------------------
    # 音频输入处理
    # ------------------------------------------------------------------
    async def _handle_audio_input(
        self, session_id: str, state: SessionState, message: dict
    ) -> dict:
        """处理 audio.input：累积音频 → 停顿检测 → 触发 ASR。"""
        payload = message.get("payload", "")
        seq = message.get("sequenceId", 0)

        if seq % 10 == 1:
            print(f"[WS] audio.input #{seq} from {session_id[:8]} (payload={len(payload)}b)")

        if not payload:
            return {"error": "Empty audio payload"}

        pcm_bytes = asr_service.decode_base64_pcm(payload)
        if not pcm_bytes:
            return {"error": "Invalid audio payload"}

        # 全部缓存
        state.audio_buffer.extend(pcm_bytes)
        state.last_activity = time.time()

        buf_ms = len(state.audio_buffer) / 32
        if seq % 10 == 1:
            print(f"[WS] buffering #{seq} total={buf_ms:.0f}ms {session_id[:8]}")

        # 累积超过 1.5 秒自动触发（简化版，不依赖 VAD 能量检测）
        if buf_ms > 1500 and not state.is_processing:
            dur_sec = len(state.audio_buffer) / 32000
            print(f"[WS] TURN {session_id[:8]}: {dur_sec:.1f}s audio")
            audio_data = bytes(state.audio_buffer)
            state.audio_buffer = bytearray()
            asyncio.create_task(self._process_audio_turn(session_id, state, audio_data))

        return {"ack": "audio.received"}

    async def _delayed_silence_check(self, session_id: str, state: SessionState) -> None:
        """延迟 700ms 检查是否静音，触发 turn。"""
        await asyncio.sleep(0.7)
        buf_s = len(state.audio_buffer) / 32000
        idle_s = time.time() - state.last_activity
        print(f"[WS] delayed_check {session_id[:8]}: buf={buf_s:.1f}s idle={idle_s:.1f}s processing={state.is_processing}")
        await self._maybe_trigger_turn(session_id, state)

    async def _process_audio_turn(
        self, session_id: str, state: SessionState, audio_data: bytes
    ) -> None:
        """音频 Turn 管线：ASR → LLM → TTS。"""
        if state.is_processing:
            # 上一轮还在处理中，跳过
            print(f"[WS] Turn skipped (still processing): {session_id}")
            return

        state.is_processing = True

        try:
            # 1. ASR 转录
            print(f"[WS] ASR transcribing {len(audio_data)/32000:.1f}s audio {session_id[:8]}...")
            user_text = await asr_service.transcribe(audio_data)

            if user_text is None:
                if asr_service._use_mock:
                    print(f"[WS] ASR model not available {session_id[:8]}")
                    await self.send_message(session_id, {
                        "type": "asr.unavailable",
                        "sessionId": session_id,
                        "message": "语音识别暂不可用，请使用文本输入",
                    })
                else:
                    # 模型正常但没识别出文字（噪音/静音/非人声）
                    print(f"[WS] ASR no text {session_id[:8]} — model OK, audio may be silence")
                    await self.send_message(session_id, {
                        "type": "asr.no_result",
                        "sessionId": session_id,
                        "message": "未检测到有效语音，请重试",
                    })
                state.is_processing = False
                return

            print(f"[WS] ASR result {session_id[:8]}: \"{user_text[:80]}\"")

            # 发送最终识别结果
            state.turn_count += 1
            turn_id = f"turn_{state.turn_count:03d}"
            await self.send_message(session_id, {
                "type": "asr.final",
                "sessionId": session_id,
                "turnId": turn_id,
                "finalTranscript": user_text,
            })

            # 2. LLM + TTS 管线
            await self._run_conversation_pipeline(session_id, state, user_text, turn_id)

        except Exception as exc:
            print(f"[WS] Audio turn error: {exc}")
            await self.send_message(session_id, {
                "type": "error",
                "sessionId": session_id,
                "message": f"处理失败: {str(exc)}",
            })
        finally:
            state.is_processing = False

    # ------------------------------------------------------------------
    # 文本输入处理（Demo 主路径）
    # ------------------------------------------------------------------
    async def _handle_text_input(
        self, session_id: str, state: SessionState, message: dict
    ) -> dict:
        """处理 text.input 消息：直接进入 LLM → TTS 管线。"""
        user_text = message.get("text", "").strip()
        if not user_text:
            return {"error": "Empty text"}

        if state.is_processing:
            # 排队等待：上一轮完成后自动处理
            state.pending_text = user_text
            return {"ack": "text.queued", "message": "上一轮处理中，消息已排队"}

        state.is_processing = True
        state.turn_count += 1
        turn_id = f"turn_{state.turn_count:03d}"

        # 发送确认（模拟 ASR final）
        await self.send_message(session_id, {
            "type": "asr.final",
            "sessionId": session_id,
            "turnId": turn_id,
            "finalTranscript": user_text,
        })

        # 进入管线（异步，不阻塞接收循环）
        asyncio.create_task(
            self._run_conversation_pipeline(session_id, state, user_text, turn_id)
        )

        return {"ack": "text.received", "turnId": turn_id}

    # ------------------------------------------------------------------
    # 对话管线核心
    # ------------------------------------------------------------------
    async def _run_conversation_pipeline(
        self, session_id: str, state: SessionState, user_text: str, turn_id: str
    ) -> None:
        """核心对话管线：LLM 流式生成 → TTS 分句合成 → 消息下发。"""
        try:
            # 确保 System Prompt 已构建
            if not state.system_prompt and state.scene_config:
                state.system_prompt = conversation_service.build_system_prompt(
                    state.scene_config
                )
            if not state.system_prompt:
                state.system_prompt = (
                    "You are a helpful English conversation partner. "
                    "Keep responses natural, concise (2-4 sentences), and engaging."
                )

            # 1. 流式 LLM 生成
            full_response = ""
            correction_info = None

            async for chunk in conversation_service.stream_chat(
                system_prompt=state.system_prompt,
                user_message=user_text,
                history=state.history,
            ):
                if chunk["type"] == "text":
                    full_response += chunk["content"]
                    await self.send_message(session_id, {
                        "type": "agent.text.delta",
                        "sessionId": session_id,
                        "turnId": turn_id,
                        "delta": chunk["content"],
                    })

                elif chunk["type"] == "correction":
                    correction_info = chunk
                    # 使用清理后的文本作为展示文本
                    if "cleanText" in chunk:
                        full_response = chunk["cleanText"]
                    await self.send_message(session_id, {
                        "type": "correction.light",
                        "sessionId": session_id,
                        "turnId": turn_id,
                        "severity": "medium",
                        "originalText": chunk["original"],
                        "correctedText": chunk["corrected"],
                        "spokenTip": f"Just a quick tip: '{chunk['corrected']}' instead of '{chunk['original']}'.",
                    })

                elif chunk["type"] == "error":
                    await self.send_message(session_id, {
                        "type": "error",
                        "sessionId": session_id,
                        "message": chunk["message"],
                    })
                    state.is_processing = False
                    return

            # 发送文本完成标记
            await self.send_message(session_id, {
                "type": "agent.text.done",
                "sessionId": session_id,
                "turnId": turn_id,
            })

            # 更新对话历史
            state.add_to_history("user", user_text)
            state.add_to_history("assistant", full_response)

            # 2. TTS 流式合成
            if full_response.strip():
                await self._stream_tts(session_id, state, full_response, turn_id)

            # 3. 处理排队中的文本
            if state.pending_text:
                pending = state.pending_text
                state.pending_text = None
                state.turn_count += 1
                new_turn_id = f"turn_{state.turn_count:03d}"
                await self.send_message(session_id, {
                    "type": "asr.final",
                    "sessionId": session_id,
                    "turnId": new_turn_id,
                    "finalTranscript": pending,
                })
                await self._run_conversation_pipeline(
                    session_id, state, pending, new_turn_id
                )
            else:
                state.is_processing = False

        except Exception as exc:
            print(f"[WS] Pipeline error: {exc}")
            await self.send_message(session_id, {
                "type": "error",
                "sessionId": session_id,
                "message": f"对话处理失败: {str(exc)}",
            })
            state.is_processing = False

    async def _stream_tts(
        self, session_id: str, state: SessionState, text: str, turn_id: str
    ) -> None:
        """流式 TTS 合成并下发音频。"""
        async for sentence, audio_b64 in tts_service.synthesize_stream(text):
            if audio_b64:
                # 有音频：发送 tts.audio.delta
                await self.send_message(session_id, {
                    "type": "tts.audio.delta",
                    "sessionId": session_id,
                    "turnId": turn_id,
                    "codec": "mp3",
                    "payload": audio_b64,
                    "text": sentence,  # 对应的文本，方便前端字幕同步
                })
            else:
                # Mock 模式：文本已通过 agent.text.delta 发送，此处跳过音频
                pass

    # ------------------------------------------------------------------
    # 结束会话
    # ------------------------------------------------------------------
    async def _handle_finish(
        self, session_id: str, state: SessionState, message: dict
    ) -> dict:
        """处理 control.finish 消息。"""
        await self.send_message(session_id, {
            "type": "control.finish",
            "sessionId": session_id,
            "reason": "userFinished",
            "reportStatus": "generating",
        })
        # 保存最终状态
        await self._save_session_state(state)
        return {"status": "finishing"}

    # ------------------------------------------------------------------
    # 消息发送
    # ------------------------------------------------------------------
    async def _maybe_trigger_turn(self, session_id: str, state: SessionState) -> None:
        """检查是否有积压音频且已停顿足够久，触发 ASR 管线。"""
        if (not state.is_processing and len(state.audio_buffer) > 0 and
                time.time() - state.last_activity > 0.6):
            dur_sec = len(state.audio_buffer) / 32000
            if dur_sec > 0.3:
                print(f"[WS] TURN SILENCE {session_id[:8]}: {dur_sec:.1f}s audio")
                audio_data = bytes(state.audio_buffer)
                state.audio_buffer = bytearray()
                asyncio.create_task(self._process_audio_turn(session_id, state, audio_data))

    async def send_message(self, session_id: str, message: dict) -> bool:
        """发送 JSON 消息到客户端。"""
        ws = self._connections.get(session_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception:
            await self.disconnect(session_id)
            return False

    # ------------------------------------------------------------------
    # 状态持久化
    # ------------------------------------------------------------------
    async def _save_session_state(self, state: SessionState) -> None:
        """将会话状态保存到 Redis（用于重连恢复）。"""
        try:
            key = f"session:{state.session_id}"
            data = json.dumps({
                "sessionId": state.session_id,
                "sceneConfig": state.scene_config,
                "turnCount": state.turn_count,
                "history": state.history[-10:],  # 只保存最近 5 轮
                "lastActivity": state.last_activity,
            })
            await cache.set(key, data, ex=settings.session_ttl_seconds)
        except Exception as exc:
            print(f"[WS] Failed to save session state: {exc}")

    async def _load_session_config(self, session_id: str) -> Optional[dict]:
        """从 Redis 恢复会话配置。"""
        try:
            key = f"session:{session_id}"
            raw = await cache.get(key)
            if raw:
                data = json.loads(raw)
                return data.get("sceneConfig")
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @property
    def active_connections(self) -> int:
        return len(self._connections)


# 全局单例
ws_manager = ConnectionManager()
