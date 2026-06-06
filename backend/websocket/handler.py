"""WebSocket handler – 实时语音对话管线。

完整链路：
  audio.input → VAD 检测 → 音频累积 → Turn 完成 →
  ASR 转录 → LLM 流式生成 → TTS 分句合成 → 前端播放
  text.input → 直接进入 LLM → TTS 管线（Demo 主路径）

消息协议符合 docs/agent-team/api-contract.md 定义。
"""

import asyncio
import json
import re
import time
import uuid
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from config import settings
from services.asr_service import EnergyVAD, asr_service
from services.cache_service import cache
from services.conversation_service import conversation_service
from services.realtime.asr_filter import asr_filter
from services.realtime.grammar_agent import grammar_agent
from services.realtime.pronunciation_agent import pronunciation_agent
from services.realtime import analysis_store
from services.tts_service import tts_service


# 句末标点分句（用于 LLM 流式输出时增量 TTS，仅整句切分避免重复朗读）
_TTS_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _extract_tts_chunks(buffer: str) -> tuple[list[str], str]:
    """从缓冲中提取已完成整句，返回 (句子列表, 剩余缓冲)。"""
    if not buffer.strip():
        return [], buffer

    result: list[str] = []
    remaining = buffer

    parts = _TTS_SENTENCE_SPLIT.split(remaining)
    if len(parts) > 1:
        for part in parts[:-1]:
            chunk = part.strip()
            if chunk:
                result.append(chunk)
        remaining = parts[-1]
    else:
        stripped = remaining.rstrip()
        if stripped and stripped[-1] in ".!?" and len(stripped) >= 4:
            result.append(stripped)
            remaining = ""

    return result, remaining


# ---------------------------------------------------------------------------
# 会话不活动超时（默认值，可被 settings 覆盖）
# ---------------------------------------------------------------------------
class SessionState:
    """单个 WebSocket 会话的运行时状态。"""

    def __init__(self, session_id: str, scene_config: Optional[dict] = None):
        self.session_id = session_id
        self.scene_config = scene_config or {}
        self.connected_at = time.time()

        # VAD：默认 700ms 静音判定 turn 结束，更快响应
        self.vad = EnergyVAD(
            silence_threshold_ms=settings.vad_silence_ms,
            speech_start_frames=settings.vad_speech_start_frames,
        )
        self.audio_buffer: bytearray = bytearray()

        # 对话：最多保留最近 6 轮 (12 条消息)
        self.history: list[dict] = []  # [{"role": "user", "content": "..."}, ...]
        self.system_prompt: str = ""
        self.turn_count: int = 0

        # 处理状态
        self.is_processing: bool = False  # 是否正在处理一轮对话
        self.pending_text: Optional[str] = None  # 排队中的文本输入

        # 指标
        self.message_count: int = 0
        self.last_activity: float = time.time()
        self.last_user_text: Optional[str] = None  # 上一次用户发言，用于去重
        self.last_user_text_time: float = 0  # 上次有效发言时间戳
        # 最后一次有效交互（用户发言或 AI 播报完成），用于不活动超时
        self.last_interaction_time: float = self.connected_at
        self.is_tts_active: bool = False  # 是否正在下发 TTS 音频

        # 不活动超时追踪
        self._inactivity_prompt_sent: bool = False  # 是否已发送 "Are you still there?"
        self._inactivity_prompt_at: float = 0.0  # 发送不活动提示的时间戳

        # 实时轻纠正开关（初值取 scene_config，已在上方归一化为 dict）
        self.realtime_correction_enabled: bool = self.scene_config.get(
            "realtimeLightCorrection", True
        )
        # 语气词累计计数
        self.filler_counts: dict[str, int] = {}
        # 最近一次检测到语音能量的时间（用于区分「久未对话」与「正在重新开口」）
        self.last_audio_speech_time: float = 0.0
        # 静音检测延迟任务（debounce）
        self._silence_check_task: Optional[asyncio.Task] = None

    def add_to_history(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        # 最多保留 6 轮 (12 条消息)，避免上下文过长
        if len(self.history) > 12:
            self.history = self.history[-12:]

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

        # 优先从 Redis 恢复；首次连接时 cache 为空，回落到数据库
        scene_config = await self._load_session_config(session_id)
        if not scene_config:
            scene_config = await self._load_scene_config_from_db(session_id)

        state = SessionState(session_id, scene_config)
        if state.scene_config:
            state.system_prompt = conversation_service.build_system_prompt(state.scene_config)
            if scene_config:
                print(f"[WS] Session config loaded: {session_id[:8]}")

        self._connections[session_id] = websocket
        self._states[session_id] = state

        # 同步实时纠正开关到前端
        await self.send_message(session_id, {
            "type": "correction.state",
            "sessionId": session_id,
            "enabled": state.realtime_correction_enabled,
        })

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

        elif msg_type == "control.correction":
            return await self._handle_correction_toggle(session_id, state, message)

        elif msg_type == "ping":
            # 心跳时检查积压音频 + 不活动超时
            await self._maybe_trigger_turn(session_id, state)
            await self.check_inactivity(session_id)
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

        # VAD 处理
        is_speech, turn_complete = state.vad.process(pcm_bytes)

        state.last_activity = time.time()

        # 只有语音帧才缓冲（过滤静音噪音）
        if is_speech:
            state.audio_buffer.extend(pcm_bytes)
            state.last_audio_speech_time = time.time()

        buf_ms = len(state.audio_buffer) / 32
        if seq % 10 == 1:
            print(f"[WS] buffering #{seq} total={buf_ms:.0f}ms {session_id[:8]}")

        # 静音超时重置：距上次有效 turn 超过 30s 且近期无语音能量 → 清空噪声缓冲
        # 注意：用户重新开口时 last_audio_speech_time 会更新，避免误清正在累积的音频
        idle_since_last_turn = time.time() - state.last_user_text_time
        idle_since_speech = (
            time.time() - state.last_audio_speech_time
            if state.last_audio_speech_time > 0
            else idle_since_last_turn
        )
        if (
            state.last_user_text_time > 0
            and idle_since_last_turn > 30
            and idle_since_speech > 3
            and not is_speech
            and not state.vad.is_speaking
        ):
            if len(state.audio_buffer) > 0:
                print(f"[WS] Silence timeout ({idle_since_last_turn:.0f}s), flushing buffer {session_id[:8]}")
                state.audio_buffer = bytearray()
                state.vad.reset()

        # VAD 静音检测：静音 500ms → turn_complete=True → 立即触发
        # 最大 5 秒强制触发（防止一直说话不触发）
        if turn_complete and len(state.audio_buffer) > 0 and not state.is_processing:
            dur_sec = len(state.audio_buffer) / 32000
            # 至少 1.2 秒有效语音才触发（过滤短语气词如 "Yes" 和瞬间噪音）
            if dur_sec >= 1.0:
                print(f"[WS] TURN {session_id[:8]}: {dur_sec:.1f}s (silence detected)")
                audio_data = bytes(state.audio_buffer)
                state.audio_buffer = bytearray()
                state.vad.reset()
                asyncio.create_task(self._process_audio_turn(session_id, state, audio_data))
            else:
                # 太短，清空丢弃
                state.audio_buffer = bytearray()
                state.vad.reset()

        elif buf_ms > 6000 and not state.is_processing:
            # 连续说话超过 6 秒，强制触发（兜底）
            dur_sec = len(state.audio_buffer) / 32000
            print(f"[WS] TURN MAX {session_id[:8]}: {dur_sec:.1f}s")
            audio_data = bytes(state.audio_buffer)
            state.audio_buffer = bytearray()
            state.vad.reset()
            asyncio.create_task(self._process_audio_turn(session_id, state, audio_data))

        # 有音频缓冲时，延迟检查静音并触发 turn（补充 VAD turn_complete）
        if len(state.audio_buffer) > 0 and not state.is_processing:
            if state._silence_check_task and not state._silence_check_task.done():
                state._silence_check_task.cancel()
            state._silence_check_task = asyncio.create_task(
                self._delayed_silence_check(session_id, state)
            )

        return {"ack": "audio.received"}

    async def _delayed_silence_check(self, session_id: str, state: SessionState) -> None:
        """延迟 700ms 检查是否静音，触发 turn。"""
        await asyncio.sleep(0.5)
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
            user_text, confidence = await asr_service.transcribe(audio_data)

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
                    reason = f"confidence={confidence:.2f}" if confidence > 0 else "no text"
                    print(f"[WS] ASR no text {session_id[:8]} — {reason}")
                    await self.send_message(session_id, {
                        "type": "asr.no_result",
                        "sessionId": session_id,
                        "message": "未检测到有效语音，请重试",
                    })
                state.is_processing = False
                return

            print(f"[WS] ASR result {session_id[:8]}: \"{user_text[:80]}\" conf={confidence:.2f}")

            # ASR 置信度 + 多层文本有效性校验（防误唤醒）
            valid, reason = asr_filter.check(
                user_text,
                confidence=confidence,
                last_text=state.last_user_text,
                last_text_time=state.last_user_text_time,
            )
            if not valid:
                print(f"[WS] ASR filtered {session_id[:8]} ({reason}): \"{user_text[:80]}\"")
                hint = (
                    "请使用英语发言（English only please）"
                    if reason == "non_english"
                    else "未检测到有效语音，请重试"
                )
                await self.send_message(session_id, {
                    "type": "asr.no_result",
                    "sessionId": session_id,
                    "message": hint,
                    "reason": reason,
                })
                state.is_processing = False
                return

            # 记录本轮用户文本（用于下轮去重 + 重置不活动计时器）
            state.last_user_text = user_text
            state.last_user_text_time = time.time()
            state.last_interaction_time = time.time()
            state._inactivity_prompt_sent = False
            state._inactivity_prompt_at = 0.0

            # 发送最终识别结果（实时模式：直接发 final，不做人工延迟）
            state.turn_count += 1
            turn_id = f"turn_{state.turn_count:03d}"

            await self.send_message(session_id, {
                "type": "asr.final",
                "sessionId": session_id,
                "turnId": turn_id,
                "finalTranscript": user_text,
                "confidence": confidence,
            })

            # 2. LLM + TTS 管线
            await self._run_conversation_pipeline(session_id, state, user_text, turn_id)

            # 3. 异步语法 + 发音分析（不阻塞主链路）
            asyncio.create_task(
                self._run_async_analysis(
                    session_id, state, user_text, turn_id,
                    audio_data=audio_data, confidence=confidence,
                )
            )

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

        # 文本有效性校验（文本输入置信度=1.0，跳过置信度检查）
        valid, reason = asr_filter.check(
            user_text,
            confidence=1.0,
            last_text=state.last_user_text,
            last_text_time=state.last_user_text_time,
        )
        if not valid:
            print(f"[WS] Text filtered {session_id[:8]} ({reason}): \"{user_text}\"")
            hint = (
                "请使用英语发言（English only please）"
                if reason == "non_english"
                else "无效输入，请重试"
            )
            await self.send_message(session_id, {
                "type": "asr.no_result",
                "sessionId": session_id,
                "message": hint,
                "reason": reason,
            })
            return {"ack": "text.skipped", "message": hint}

        # 更新有效发言时间（重置不活动计时器）
        state.last_user_text = user_text
        state.last_user_text_time = time.time()
        state.last_interaction_time = time.time()
        state._inactivity_prompt_sent = False
        state._inactivity_prompt_at = 0.0

        if state.is_processing:
            # 排队等待：上一轮完成后自动处理
            state.pending_text = user_text
            return {"ack": "text.queued", "message": "上一轮处理中，消息已排队"}

        state.is_processing = True
        state.turn_count += 1
        turn_id = f"turn_{state.turn_count:03d}"

        # 发送确认（模拟 ASR final，文本输入置信度=1.0）
        await self.send_message(session_id, {
            "type": "asr.final",
            "sessionId": session_id,
            "turnId": turn_id,
            "finalTranscript": user_text,
            "confidence": 1.0,
        })

        # 进入管线（异步，不阻塞接收循环）
        asyncio.create_task(
            self._run_conversation_pipeline(session_id, state, user_text, turn_id)
        )

        # 异步语法分析（文本输入无音频，跳过发音分析）
        asyncio.create_task(
            self._run_async_analysis(
                session_id, state, user_text, turn_id,
                audio_data=None, confidence=1.0,
            )
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

            # 1. 流式 LLM + 分句朗读（浏览器模式即时推送，服务端模式异步队列）
            full_response = ""
            tts_buffer = ""
            any_tts_sent = False
            use_server_tts = settings.enable_server_tts
            tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
            tts_task: Optional[asyncio.Task] = None

            async def enqueue_speech(sentence: str) -> None:
                nonlocal any_tts_sent
                if not sentence.strip():
                    return
                if use_server_tts:
                    await tts_queue.put(sentence)
                elif await self._emit_turn_speech(
                    session_id, state, sentence, turn_id
                ):
                    any_tts_sent = True

            async def tts_worker() -> None:
                nonlocal any_tts_sent
                while True:
                    chunk_text = await tts_queue.get()
                    try:
                        if chunk_text is None:
                            break
                        if await self._send_tts_sentence(
                            session_id, state, chunk_text, turn_id
                        ):
                            any_tts_sent = True
                    finally:
                        tts_queue.task_done()

            if use_server_tts:
                tts_task = asyncio.create_task(tts_worker())

            pipeline_failed = False

            try:
                async for chunk in conversation_service.stream_chat(
                    system_prompt=state.system_prompt,
                    user_message=user_text,
                    history=state.history,
                ):
                    if chunk["type"] == "text":
                        token = chunk["content"]
                        full_response += token
                        tts_buffer += token
                        await self.send_message(session_id, {
                            "type": "agent.text.delta",
                            "sessionId": session_id,
                            "turnId": turn_id,
                            "delta": token,
                        })

                        sentences, tts_buffer = _extract_tts_chunks(tts_buffer)
                        for sentence in sentences:
                            await enqueue_speech(sentence)

                    elif chunk["type"] == "error":
                        pipeline_failed = True
                        await self.send_message(session_id, {
                            "type": "error",
                            "sessionId": session_id,
                            "message": chunk["message"],
                        })
                        fallback_text = (
                            "I'm sorry, could you repeat that? "
                            "I didn't quite catch what you said."
                        )
                        await self.send_message(session_id, {
                            "type": "agent.text.delta",
                            "sessionId": session_id,
                            "turnId": turn_id,
                            "delta": fallback_text,
                        })
                        await self.send_message(session_id, {
                            "type": "agent.text.done",
                            "sessionId": session_id,
                            "turnId": turn_id,
                        })
                        await self._stream_tts(
                            session_id, state, fallback_text, turn_id
                        )
                        state.is_processing = False
                        return
            finally:
                if not pipeline_failed and tts_buffer.strip():
                    await enqueue_speech(tts_buffer.strip())
                if use_server_tts and tts_task:
                    await tts_queue.put(None)
                    await tts_task

            # LLM 无正文时使用兜底回复
            if not full_response.strip() and not pipeline_failed:
                print(f"[WS] LLM empty response {session_id[:8]} {turn_id}, using fallback")
                full_response = (
                    "Hi! Thanks for that. Could you tell me a bit more about your experience?"
                )
                await self.send_message(session_id, {
                    "type": "agent.text.delta",
                    "sessionId": session_id,
                    "turnId": turn_id,
                    "delta": full_response,
                })
                if await self._emit_turn_speech(
                    session_id, state, full_response, turn_id
                ):
                    any_tts_sent = True

            # 发送文本完成标记
            await self.send_message(session_id, {
                "type": "agent.text.done",
                "sessionId": session_id,
                "turnId": turn_id,
            })

            # 更新对话历史
            state.add_to_history("user", user_text)
            state.add_to_history("assistant", full_response)

            if full_response.strip() and not any_tts_sent:
                await self._emit_turn_speech(
                    session_id, state, full_response.strip(), turn_id
                )
            state.last_interaction_time = time.time()

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
                    "confidence": 1.0,
                })
                await self._run_conversation_pipeline(
                    session_id, state, pending, new_turn_id
                )
            else:
                state.is_processing = False

        except Exception as exc:
            print(f"[WS] Pipeline error: {exc}")
            # LLM 失败兜底：发送友好的回落回复
            fallback_text = "I'm sorry, could you repeat that? I didn't quite catch what you said."
            await self.send_message(session_id, {
                "type": "agent.text.delta",
                "sessionId": session_id,
                "turnId": turn_id,
                "delta": fallback_text,
            })
            await self.send_message(session_id, {
                "type": "agent.text.done",
                "sessionId": session_id,
                "turnId": turn_id,
            })
            await self._stream_tts(session_id, state, fallback_text, turn_id)
            # 仍然更新历史，保持上下文连续性
            state.add_to_history("user", user_text)
            state.add_to_history("assistant", fallback_text)
            # 处理排队中的文本
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
                    "confidence": 1.0,
                })
                await self._run_conversation_pipeline(
                    session_id, state, pending, new_turn_id
                )
            else:
                state.is_processing = False

    async def _emit_turn_speech(
        self, session_id: str, state: SessionState, text: str, turn_id: str
    ) -> bool:
        """下发朗读：服务端 TTS 或浏览器 speechSynthesis 信号（tts.unavailable）。"""
        if not text.strip():
            return False
        if settings.enable_server_tts:
            return await self._send_tts_sentence(
                session_id, state, text.strip(), turn_id
            )
        await self.send_message(session_id, {
            "type": "tts.unavailable",
            "sessionId": session_id,
            "turnId": turn_id,
            "text": text.strip(),
        })
        return True

    async def _send_tts_sentence(
        self, session_id: str, state: SessionState, sentence: str, turn_id: str
    ) -> bool:
        """合成并下发单句 TTS，返回是否成功发送音频。"""
        if not sentence.strip():
            return False

        state.is_tts_active = True
        sent = False
        try:
            async for _, audio_b64 in tts_service.synthesize_stream(sentence):
                if audio_b64:
                    sent = True
                    await self.send_message(session_id, {
                        "type": "tts.audio.delta",
                        "sessionId": session_id,
                        "turnId": turn_id,
                        "codec": "mp3",
                        "payload": audio_b64,
                        "text": sentence,
                    })
        finally:
            state.is_tts_active = False
        return sent

    async def _stream_tts(
        self, session_id: str, state: SessionState, text: str, turn_id: str
    ) -> None:
        """流式朗读：浏览器模式按句推送；服务端模式走 EdgeTTS。"""
        if not text.strip():
            return

        if not settings.enable_server_tts:
            sentences, remainder = _extract_tts_chunks(text.strip() + " ")
            chunks = sentences[:]
            if remainder.strip():
                chunks.append(remainder.strip())
            if not chunks:
                chunks = [text.strip()]
            for chunk in chunks:
                await self._emit_turn_speech(session_id, state, chunk, turn_id)
            state.last_interaction_time = time.time()
            state._inactivity_prompt_at = 0.0
            return

        state.is_tts_active = True
        sent_any = False
        try:
            async for sentence, audio_b64 in tts_service.synthesize_stream(text):
                if audio_b64:
                    sent_any = True
                    await self.send_message(session_id, {
                        "type": "tts.audio.delta",
                        "sessionId": session_id,
                        "turnId": turn_id,
                        "codec": "mp3",
                        "payload": audio_b64,
                        "text": sentence,
                    })

            if not sent_any:
                print(f"[TTS] No audio generated, fallback signal sent {session_id[:8]}")
                await self.send_message(session_id, {
                    "type": "tts.unavailable",
                    "sessionId": session_id,
                    "turnId": turn_id,
                    "text": text.strip(),
                })
        finally:
            state.is_tts_active = False
            state.last_interaction_time = time.time()
            state._inactivity_prompt_at = 0.0

    # ------------------------------------------------------------------
    # 异步语法 + 发音分析（不阻塞主链路）
    # ------------------------------------------------------------------
    async def _run_async_analysis(
        self,
        session_id: str,
        state: SessionState,
        transcript: str,
        turn_id: str,
        *,
        audio_data: Optional[bytes] = None,
        confidence: float = 1.0,
    ) -> None:
        """异步触发 Grammar Agent + Pronunciation Agent，结果写入 cache 并下发 WS 消息。"""
        try:
            correction_policy = state.scene_config.get("correctionPolicy", {})

            # 开关关闭时不做语法纠正，保留用户原句
            if not state.realtime_correction_enabled:
                filler_counts = grammar_agent.count_fillers(transcript)
                if filler_counts:
                    for word, count in filler_counts.items():
                        state.filler_counts[word] = state.filler_counts.get(word, 0) + count
                        await analysis_store.incr_filler(session_id, word, count)
                    await self.send_message(session_id, {
                        "type": "analysis.counter",
                        "sessionId": session_id,
                        "fillerCounts": state.filler_counts,
                        "totalFillers": sum(state.filler_counts.values()),
                    })
            else:
                # ---- Grammar Agent（分析用 pro 模型） ----
                grammar_result = await grammar_agent.analyze(
                    transcript,
                    realtime_enabled=True,
                    correction_policy=correction_policy,
                )

                if grammar_result.severity != "none":
                    await analysis_store.append_correction(session_id, {
                        "turnId": turn_id,
                        "original": grammar_result.original,
                        "corrected": grammar_result.corrected,
                        "severity": grammar_result.severity,
                        "transcript": transcript,
                    })

                if grammar_result.spoken_tip:
                    await self.send_message(session_id, {
                        "type": "correction.light",
                        "sessionId": session_id,
                        "turnId": turn_id,
                        "severity": "high" if grammar_result.severity == "serious" else "medium",
                        "originalText": grammar_result.original,
                        "correctedText": grammar_result.corrected,
                        "spokenTip": grammar_result.spoken_tip,
                    })

                if grammar_result.filler_counts:
                    for word, count in grammar_result.filler_counts.items():
                        state.filler_counts[word] = state.filler_counts.get(word, 0) + count
                        await analysis_store.incr_filler(session_id, word, count)
                    await self.send_message(session_id, {
                        "type": "analysis.counter",
                        "sessionId": session_id,
                        "fillerCounts": state.filler_counts,
                        "totalFillers": sum(state.filler_counts.values()),
                    })

            # ---- Pronunciation Agent（仅音频轮） ----
            if audio_data:
                pron_result = await pronunciation_agent.analyze(
                    session_id, audio_data, transcript, confidence, turn_id,
                )
                await analysis_store.append_pronunciation(session_id, {
                    "turnId": pron_result.turn_id,
                    "wordsPerMinute": pron_result.words_per_minute,
                    "pauseCount": pron_result.pause_count,
                    "lowConfidenceWords": pron_result.low_confidence_words,
                    "durationSeconds": pron_result.duration_seconds,
                    "wordCount": pron_result.word_count,
                    "overallConfidence": pron_result.overall_confidence,
                })

        except Exception as exc:
            print(f"[WS] Async analysis error: {exc}")

    async def _handle_correction_toggle(
        self, session_id: str, state: SessionState, message: dict
    ) -> dict:
        """处理 control.correction 消息：运行时开关实时轻纠正。"""
        enabled = message.get("enabled", True)
        state.realtime_correction_enabled = bool(enabled)
        print(f"[WS] Correction toggle {session_id[:8]}: {enabled}")
        await self.send_message(session_id, {
            "type": "correction.state",
            "sessionId": session_id,
            "enabled": state.realtime_correction_enabled,
        })
        return {"ack": "correction.updated", "enabled": state.realtime_correction_enabled}

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
                time.time() - state.last_activity > 0.45):
            dur_sec = len(state.audio_buffer) / 32000
            if dur_sec > 0.8:
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
    # 会话不活动超时 — 自动检测并提示/结束
    # ------------------------------------------------------------------
    async def check_inactivity(self, session_id: str) -> None:
        """检查会话是否长时间无有效输入。

        规则：
        - 默认 90 秒无有效交互 → 发送 "Are you still there?"（仅一次）
        - 提示后再过 30 秒仍无响应 → 自动结束会话
        """
        state = self._states.get(session_id)
        if state is None or state.is_processing or state.is_tts_active:
            return

        idle_sec = time.time() - state.last_interaction_time
        close_after_prompt = settings.inactivity_close_after_prompt_sec

        if (
            state._inactivity_prompt_sent
            and state._inactivity_prompt_at > 0
            and time.time() - state._inactivity_prompt_at >= close_after_prompt
        ):
            # 已发送提示但用户仍未响应 → 结束会话
            print(f"[WS] Session auto-end after inactivity prompt: {session_id[:8]}")
            await self.send_message(session_id, {
                "type": "control.finish",
                "sessionId": session_id,
                "reason": "inactivity",
                "reportStatus": "generating",
            })
            await self._save_session_state(state)
            await self.disconnect(session_id)
            return

        if idle_sec >= settings.inactivity_prompt_sec and not state._inactivity_prompt_sent:
            # 长时间无交互 → 发送提醒
            print(f"[WS] Sending inactivity prompt after {idle_sec:.0f}s: {session_id[:8]}")
            state._inactivity_prompt_sent = True
            state._inactivity_prompt_at = time.time()
            prompt_text = "Are you still there? I haven't heard from you for a while."
            await self.send_message(session_id, {
                "type": "agent.text.delta",
                "sessionId": session_id,
                "turnId": "inactivity_prompt",
                "delta": f" {prompt_text}",
            })
            await self.send_message(session_id, {
                "type": "agent.text.done",
                "sessionId": session_id,
                "turnId": "inactivity_prompt",
            })
            await self._stream_tts(session_id, state, prompt_text, "inactivity_prompt")

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

    async def _load_scene_config_from_db(self, session_id: str) -> Optional[dict]:
        """首次 WebSocket 连接时从 interviews 表加载 scene_config。"""
        try:
            from database import async_session_factory
            from models.base import Interview

            sid = uuid.UUID(session_id)
            async with async_session_factory() as db:
                interview = await db.get(Interview, sid)
                if interview and interview.scene_config:
                    print(f"[WS] Scene config from DB: {session_id[:8]}")
                    return interview.scene_config
        except Exception as exc:
            print(f"[WS] Failed to load scene config from DB: {exc}")
        return None

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @property
    def active_connections(self) -> int:
        return len(self._connections)


# 全局单例
ws_manager = ConnectionManager()
