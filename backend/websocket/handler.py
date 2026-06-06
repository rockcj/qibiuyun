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
from services.storage_service import storage_service


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

        # VAD：短句 0.5s 静音结束；长发言动态放宽
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
        # 对话阶段：listening=可录音 user_turn=用户轮处理中 ai_speaking=AI 播报中
        self.turn_phase: str = "listening"

        # 不活动超时追踪
        self._inactivity_prompt_sent: bool = False  # 是否已发送 "Are you still there?"
        self._inactivity_prompt_at: float = 0.0  # 发送不活动提示的时间戳

        # 实时轻纠正开关（初值取 scene_config，已在上方归一化为 dict）
        self.realtime_correction_enabled: bool = self.scene_config.get(
            "realtimeLightCorrection", True
        )
        # 语气词累计计数
        self.filler_counts: dict[str, int] = {}
        # 会话 transcript（用于报告页回放）
        self.transcript_turns: list[dict] = []
        # 整场用户发言 PCM 拼接（用于完整回放上传 TOS）
        self.session_recording_pcm: bytearray = bytearray()
        self.full_audio_url: Optional[str] = None
        self.full_audio_storage_key: Optional[str] = None
        self.full_audio_storage_provider: Optional[str] = None
        # 当前轮次起始时间（毫秒，相对会话开始）
        self.current_turn_start_ms: Optional[int] = None
        # 轮次结束确认任务（防句中停顿误触发）
        self._turn_finalize_task: Optional[asyncio.Task] = None
        # 句末尾音采集截止时间（毫秒级短窗口，避免无限累积环境噪声）
        self._tail_capture_until: float = 0.0
        # 最近一次检测到语音能量的时间（用于区分「久未对话」与「正在重新开口」）
        self.last_audio_speech_time: float = 0.0
        # 静音检测延迟任务（debounce）
        self._silence_check_task: Optional[asyncio.Task] = None
        # 已达 max 上限时只打一次日志，避免刷屏
        self._max_split_logged: bool = False

    def effective_vad_silence_ms(self) -> int:
        """缓冲较长时放宽句中停顿判定，支持长段回答。"""
        buf_ms = len(self.audio_buffer) / 32
        if buf_ms >= settings.vad_long_utterance_threshold_ms:
            return settings.vad_long_utterance_silence_ms
        return settings.vad_silence_ms

    def accepts_user_audio(self) -> bool:
        """是否处于可接收用户语音的状态（严格轮流对话）。"""
        return (
            self.turn_phase == "listening"
            and not self.is_processing
            and not self.is_tts_active
        )

    def add_to_history(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        # 最多保留 6 轮 (12 条消息)，避免上下文过长
        if len(self.history) > 12:
            self.history = self.history[-12:]

    def append_transcript_turn(
        self,
        turn_id: str,
        role: str,
        text: str,
        *,
        audio_url: Optional[str] = None,
        audio_storage_key: Optional[str] = None,
        audio_storage_provider: Optional[str] = None,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> None:
        """记录一轮对话，含可选音频回放地址。"""
        if not text.strip() and not audio_url:
            return
        now_ms = int((time.time() - self.connected_at) * 1000)
        turn_start = start_ms if start_ms is not None else now_ms
        turn_end = end_ms if end_ms is not None else turn_start + max(1000, len(text.split()) * 250)
        entry = {
            "turnId": turn_id,
            "role": role,
            "text": text.strip(),
            "startMs": turn_start,
            "endMs": turn_end,
        }
        if audio_url:
            entry["audioUrl"] = audio_url
        if audio_storage_key:
            entry["audioStorageKey"] = audio_storage_key
        if audio_storage_provider:
            entry["audioStorageProvider"] = audio_storage_provider
        self.transcript_turns.append(entry)

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
        # 同一会话的新连接到来时，先关闭旧连接，避免多 handler 竞态
        old_ws = self._connections.get(session_id)
        if old_ws is not None and old_ws is not websocket:
            try:
                await old_ws.close(code=1000, reason="replaced by new connection")
            except Exception:
                pass

        await websocket.accept()

        # 重连时复用已有 SessionState（保留对话历史）；首次连接从 cache/DB 加载
        state = self._states.get(session_id)
        if state is None:
            scene_config = await self._load_session_config(session_id)
            if not scene_config:
                scene_config = await self._load_scene_config_from_db(session_id)
            state = SessionState(session_id, scene_config)
            if state.scene_config:
                state.system_prompt = conversation_service.build_system_prompt(state.scene_config)
                if scene_config:
                    print(f"[WS] Session config loaded: {session_id[:8]}")
        else:
            print(f"[WS] Session reconnected: {session_id[:8]}")
            # 重连时恢复 transcript
            try:
                raw = await cache.get(f"session:{session_id}")
                if raw:
                    saved = json.loads(raw)
                    state.transcript_turns = saved.get("transcriptTurns", state.transcript_turns)
            except Exception:
                pass

        self._connections[session_id] = websocket
        self._states[session_id] = state

        # 同步实时纠正开关到前端
        await self.send_message(session_id, {
            "type": "correction.state",
            "sessionId": session_id,
            "enabled": state.realtime_correction_enabled,
        })

        await self._set_turn_phase(session_id, state, "listening")

        print(f"[WS] Client connected: {session_id} (total: {self.active_connections})")

    async def disconnect(self, session_id: str, websocket: WebSocket | None = None) -> None:
        """断开连接，持久化会话状态。

        websocket 用于区分「已被新连接取代的旧 handler」，避免误删活跃连接。
        """
        current = self._connections.get(session_id)
        if websocket is not None and current is not websocket:
            return

        self._connections.pop(session_id, None)
        state = self._states.pop(session_id, None)

        if state:
            # 断开前上传整场录音（用户未点结束直接离开页面时）
            await self._upload_session_full_audio(state)
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

        elif msg_type == "audio.turn.end":
            return await self._handle_audio_turn_end(session_id, state, message)

        elif msg_type == "text.input":
            result = await self._handle_text_input(session_id, state, message)
            # 处理完文本输入后，检查是否有积压音频需要触发
            await self._maybe_trigger_turn(session_id, state)
            return result

        elif msg_type == "control.finish":
            return await self._handle_finish(session_id, state, message)

        elif msg_type == "control.correction":
            return await self._handle_correction_toggle(session_id, state, message)

        elif msg_type == "control.listening":
            # 前端 TTS 播完后的确认，恢复可录音状态
            if not state.is_processing and not state.is_tts_active:
                await self._set_turn_phase(session_id, state, "listening")
            return {"ack": "listening"}

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
    async def _set_turn_phase(
        self, session_id: str, state: SessionState, phase: str
    ) -> None:
        """同步对话阶段到前端，控制何时可录音。"""
        if state.turn_phase == phase:
            return
        state.turn_phase = phase
        await self.send_message(session_id, {
            "type": "turn.phase",
            "sessionId": session_id,
            "phase": phase,
        })
        print(f"[WS] Phase → {phase} {session_id[:8]}")

    async def _handle_audio_turn_end(
        self, session_id: str, state: SessionState, message: dict
    ) -> dict:
        """客户端检测到 0.5s 静音：立即冲刷当前缓冲进入 ASR。"""
        if not state.accepts_user_audio():
            return {"ack": "audio.ignored", "phase": state.turn_phase}
        if len(state.audio_buffer) == 0:
            return {"ack": "audio.empty"}
        self._flush_audio_turn(session_id, state, reason="client_end")
        return {"ack": "turn.end"}

    async def _handle_audio_input(
        self, session_id: str, state: SessionState, message: dict
    ) -> dict:
        """处理 audio.input：累积音频 → 停顿检测 → 触发 ASR。"""
        # AI 处理/播报期间拒收音频，保证轮流对话
        if not state.accepts_user_audio():
            return {"ack": "audio.ignored", "phase": state.turn_phase}

        payload = message.get("payload", "")
        seq = message.get("sequenceId", 0)

        if seq % 10 == 1:
            print(f"[WS] audio.input #{seq} from {session_id[:8]} (payload={len(payload)}b)")

        if not payload:
            return {"error": "Empty audio payload"}

        pcm_bytes = asr_service.decode_base64_pcm(payload)
        if not pcm_bytes:
            return {"error": "Invalid audio payload"}

        # 长发言时动态放宽 VAD 静音阈值（短句仍 0.5s）
        effective_silence_ms = state.effective_vad_silence_ms()
        if state.vad.silence_threshold_ms != effective_silence_ms:
            state.vad.set_silence_threshold_ms(effective_silence_ms)

        # VAD 处理
        is_speech, turn_complete = state.vad.process(pcm_bytes)

        state.last_activity = time.time()
        now = time.time()

        # 用户重新开口 → 取消进行中的结束确认，继续累积本轮
        if is_speech and state._turn_finalize_task and not state._turn_finalize_task.done():
            state._turn_finalize_task.cancel()
            state._tail_capture_until = 0.0

        # 轮次进行中：只采集语音帧 + 句末短尾音
        capturing = (
            is_speech
            or state.vad.speech_started
            or now < state._tail_capture_until
        )
        if capturing:
            if is_speech and state.current_turn_start_ms is None:
                state.current_turn_start_ms = int((time.time() - state.connected_at) * 1000)
            state.audio_buffer.extend(pcm_bytes)
            if is_speech:
                state.last_audio_speech_time = time.time()

        buf_ms = len(state.audio_buffer) / 32
        if seq % 10 == 1:
            print(
                f"[WS] buffering #{seq} buf={buf_ms:.0f}ms "
                f"vad={effective_silence_ms}ms {session_id[:8]}"
            )

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

        # VAD 句末静音 → 极短确认后触发 ASR
        if turn_complete and len(state.audio_buffer) > 0 and not state.is_processing:
            tail_sec = max(settings.vad_turn_confirm_ms / 1000.0, 0.12)
            state._tail_capture_until = time.time() + tail_sec
            self._schedule_turn_finalize(session_id, state, reason="vad_silence")

        # 连续说话超过上限 → 立即切分（同步触发，避免每帧 cancel 任务）
        elif (
            buf_ms >= settings.vad_max_turn_seconds * 1000
            and not state.is_processing
            and len(state.audio_buffer) > 0
        ):
            if not state._max_split_logged:
                print(
                    f"[WS] TURN MAX {session_id[:8]}: {buf_ms/1000:.1f}s — force split"
                )
                state._max_split_logged = True
            self._flush_audio_turn(session_id, state, reason="max_duration")

        return {"ack": "audio.received"}

    def _flush_audio_turn(
        self, session_id: str, state: SessionState, reason: str
    ) -> bool:
        """从当前缓冲立即切出一轮并异步 ASR（不可被重复 cancel）。"""
        if state.is_processing or len(state.audio_buffer) == 0:
            return False

        if state._turn_finalize_task and not state._turn_finalize_task.done():
            state._turn_finalize_task.cancel()
            state._turn_finalize_task = None

        dur_sec = len(state.audio_buffer) / 32000
        if dur_sec < settings.vad_min_turn_seconds:
            return False

        print(f"[WS] TURN {session_id[:8]}: {dur_sec:.1f}s ({reason})")
        audio_data = bytes(state.audio_buffer)
        state.audio_buffer = bytearray()
        state.vad.reset()
        state._tail_capture_until = 0.0
        state._max_split_logged = False
        state.current_turn_start_ms = None
        asyncio.create_task(self._set_turn_phase(session_id, state, "user_turn"))
        asyncio.create_task(self._process_audio_turn(session_id, state, audio_data))
        return True

    def _schedule_turn_finalize(
        self,
        session_id: str,
        state: SessionState,
        reason: str = "silence",
        delay_sec: Optional[float] = None,
        force: bool = False,
    ) -> None:
        """延迟确认用户已说完，再触发 ASR。"""
        if state.is_processing or len(state.audio_buffer) == 0:
            return

        if delay_sec is None:
            delay_sec = settings.vad_turn_confirm_ms / 1000.0

        # 已有确认任务时不再重复调度（修复：每帧 reset 导致永远不触发）
        if (
            not force
            and state._turn_finalize_task
            and not state._turn_finalize_task.done()
        ):
            return

        if force and state._turn_finalize_task and not state._turn_finalize_task.done():
            state._turn_finalize_task.cancel()

        async def _confirm_and_trigger() -> None:
            try:
                if delay_sec > 0:
                    await asyncio.sleep(delay_sec)
                if state.is_processing or len(state.audio_buffer) == 0:
                    return
                # 确认窗口内用户又开口 → 放弃本次触发
                if state.vad.is_speaking or state.vad.speech_started:
                    return
                dur_sec = len(state.audio_buffer) / 32000
                if dur_sec < settings.vad_min_turn_seconds:
                    state.audio_buffer = bytearray()
                    state.vad.reset()
                    state._tail_capture_until = 0.0
                    return
                print(f"[WS] TURN {session_id[:8]}: {dur_sec:.1f}s ({reason}, confirmed)")
                audio_data = bytes(state.audio_buffer)
                state.audio_buffer = bytearray()
                state.vad.reset()
                state._tail_capture_until = 0.0
                state._max_split_logged = False
                state.current_turn_start_ms = None
                asyncio.create_task(self._set_turn_phase(session_id, state, "user_turn"))
                asyncio.create_task(self._process_audio_turn(session_id, state, audio_data))
            except asyncio.CancelledError:
                pass

        state._turn_finalize_task = asyncio.create_task(_confirm_and_trigger())

    async def _delayed_silence_check(self, session_id: str, state: SessionState) -> None:
        """兼容旧逻辑：延迟检查静音并调度确认。"""
        await asyncio.sleep(settings.vad_silence_ms / 1000.0)
        self._schedule_turn_finalize(session_id, state, reason="delayed_check")

    async def _process_audio_turn(
        self, session_id: str, state: SessionState, audio_data: bytes
    ) -> None:
        """音频 Turn 管线：ASR → LLM → TTS（录音上传并行，不阻塞识别）。"""
        if state.is_processing:
            print(f"[WS] Turn skipped (still processing): {session_id}")
            return

        state.is_processing = True
        state.turn_count += 1
        turn_id = f"turn_{state.turn_count:03d}"

        turn_start_ms = state.current_turn_start_ms
        if turn_start_ms is None:
            turn_start_ms = max(0, int((time.time() - state.connected_at) * 1000) - int(len(audio_data) / 32))
        turn_end_ms = turn_start_ms + int(len(audio_data) / 32)
        state.current_turn_start_ms = None

        # 累积整场录音；WAV 上传与 ASR 并行，避免拖慢响应
        state.session_recording_pcm.extend(audio_data)
        upload_task = asyncio.create_task(
            storage_service.upload_turn_audio(session_id, turn_id, audio_data)
        )
        turn_reached_ai = False

        try:
            # 1. ASR 转录（优先，不等待上传完成）
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
                return

            # 记录本轮用户文本（用于下轮去重 + 重置不活动计时器）
            state.last_user_text = user_text
            state.last_user_text_time = time.time()
            state.last_interaction_time = time.time()
            state._inactivity_prompt_sent = False
            state._inactivity_prompt_at = 0.0

            # 发送最终识别结果（实时模式：直接发 final，不做人工延迟）
            await self.send_message(session_id, {
                "type": "asr.final",
                "sessionId": session_id,
                "turnId": turn_id,
                "finalTranscript": user_text,
                "confidence": confidence,
            })

            # 等待录音上传完成（通常 ASR 期间已并行完成）
            audio_meta: dict = {}
            try:
                audio_meta = await upload_task
            except Exception as upload_exc:
                print(f"[WS] Audio upload failed {session_id[:8]}: {upload_exc}")
                audio_meta = {
                    "replayUrl": storage_service.replay_api_path(session_id, turn_id),
                }

            # 2. LLM + TTS 管线（附带本轮录音元数据供 transcript 回放）
            turn_reached_ai = True
            await self._run_conversation_pipeline(
                session_id,
                state,
                user_text,
                turn_id,
                user_audio_meta=audio_meta,
                user_turn_start_ms=turn_start_ms,
                user_turn_end_ms=turn_end_ms,
            )

            # 3. 异步语法 + 发音分析（不阻塞主链路）
            asyncio.create_task(
                self._run_async_analysis(
                    session_id, state, user_text, turn_id,
                    audio_data=audio_data, confidence=confidence,
                )
            )

        except Exception as exc:
            print(f"[WS] Audio turn error: {exc}")
            if not upload_task.done():
                upload_task.cancel()
            await self.send_message(session_id, {
                "type": "error",
                "sessionId": session_id,
                "message": f"处理失败: {str(exc)}",
            })
        finally:
            state.is_processing = False
            await self._finish_user_turn_phase(session_id, state, turn_reached_ai)

    async def _finish_user_turn_phase(
        self, session_id: str, state: SessionState, ai_reached: bool
    ) -> None:
        """一轮用户输入处理结束，切换对话阶段。"""
        if not ai_reached:
            await self._set_turn_phase(session_id, state, "listening")
            return
        if settings.enable_server_tts:
            if not state.is_tts_active:
                await self._set_turn_phase(session_id, state, "listening")
        else:
            await self._set_turn_phase(session_id, state, "ai_speaking")

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
        await self._set_turn_phase(session_id, state, "user_turn")

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
        self,
        session_id: str,
        state: SessionState,
        user_text: str,
        turn_id: str,
        *,
        user_audio_meta: Optional[dict] = None,
        user_turn_start_ms: Optional[int] = None,
        user_turn_end_ms: Optional[int] = None,
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
            state.append_transcript_turn(
                turn_id,
                "user",
                user_text,
                audio_url=(user_audio_meta or {}).get("replayUrl"),
                audio_storage_key=(user_audio_meta or {}).get("storageKey"),
                audio_storage_provider=(user_audio_meta or {}).get("storageProvider"),
                start_ms=user_turn_start_ms,
                end_ms=user_turn_end_ms,
            )
            state.append_transcript_turn(turn_id, "assistant", full_response)

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
            await self._set_turn_phase(session_id, state, "listening")

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

                    # 同时写入 TimelineEvent 到数据库（不阻塞主链路）
                    asyncio.create_task(_save_grammar_timeline_event(
                        session_id, turn_id, grammar_result, transcript
                    ))

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

            # ---- Pronunciation Agent ----
            if audio_data:
                pron_result = await pronunciation_agent.analyze(
                    session_id, audio_data, transcript, confidence, turn_id,
                )
            else:
                # 文本输入：用词数估算 WPM / 停顿
                pron_result = await pronunciation_agent.analyze_text(
                    transcript, turn_id, confidence,
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
        # 结束前先处理剩余音频缓冲
        if len(state.audio_buffer) > 0 and not state.is_processing:
            dur_sec = len(state.audio_buffer) / 32000
            if dur_sec >= settings.vad_min_turn_seconds:
                self._flush_audio_turn(session_id, state, reason="finish")
            else:
                state.audio_buffer = bytearray()
                state.vad.reset()

        await self._upload_session_full_audio(state)

        await self.send_message(session_id, {
            "type": "control.finish",
            "sessionId": session_id,
            "reason": "userFinished",
            "reportStatus": "generating",
        })
        # 保存最终状态
        await self._save_session_state(state)
        # 刷入数据库供报告页读取
        from services.session_persist_service import flush_session_data
        asyncio.create_task(flush_session_data(session_id))
        return {"status": "finishing"}

    # ------------------------------------------------------------------
    # 消息发送
    # ------------------------------------------------------------------
    async def _maybe_trigger_turn(self, session_id: str, state: SessionState) -> None:
        """心跳时检查积压音频：停说超过 0.5s 则调度确认触发。"""
        if (
            not state.is_processing
            and len(state.audio_buffer) > 0
            and not state.vad.is_speaking
            and time.time() - state.last_activity >= (settings.vad_silence_ms / 1000.0)
        ):
            self._schedule_turn_finalize(session_id, state, reason="ping_idle")

    async def send_message(self, session_id: str, message: dict) -> bool:
        """发送 JSON 消息到客户端。"""
        ws = self._connections.get(session_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception:
            await self.disconnect(session_id, ws)
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
            await self._upload_session_full_audio(state)
            await self._save_session_state(state)
            await self.disconnect(session_id, self._connections.get(session_id))
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
    async def _upload_session_full_audio(self, state: SessionState) -> None:
        """上传整场用户发言 PCM 至 TOS / 本地（幂等，已上传则跳过）。"""
        if state.full_audio_url or len(state.session_recording_pcm) == 0:
            return
        full_meta = await storage_service.upload_full_session_audio(
            state.session_id, bytes(state.session_recording_pcm)
        )
        if full_meta:
            state.full_audio_url = full_meta.get("replayUrl")
            state.full_audio_storage_key = full_meta.get("storageKey")
            state.full_audio_storage_provider = full_meta.get("storageProvider")

    async def _save_session_state(self, state: SessionState) -> None:
        """将会话状态保存到 Redis（用于重连恢复）。"""
        try:
            key = f"session:{state.session_id}"
            data = json.dumps({
                "sessionId": state.session_id,
                "sceneConfig": state.scene_config,
                "turnCount": state.turn_count,
                "history": state.history[-10:],  # 只保存最近 5 轮
                "transcriptTurns": state.transcript_turns,
                "fullAudioUrl": state.full_audio_url,
                "fullAudioStorageKey": state.full_audio_storage_key,
                "fullAudioStorageProvider": state.full_audio_storage_provider,
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


async def _save_grammar_timeline_event(session_id: str, turn_id: str, grammar_result, transcript: str) -> None:
    """写入语法错误时间轴事件到数据库（后台任务）。"""
    from database import async_session_factory
    from models.base import TimelineEvent
    import uuid as _uuid

    try:
        interview_uuid = _uuid.UUID(session_id)
    except ValueError:
        return

    try:
        async with async_session_factory() as db:
            turn_num = 0
            if turn_id and turn_id.startswith("turn_"):
                try:
                    turn_num = int(turn_id.split("_")[-1])
                except (ValueError, IndexError):
                    pass
            estimated_start_ms = max(0, turn_num * 30000 + 5000)
            estimated_end_ms = estimated_start_ms + 15000

            db.add(TimelineEvent(
                interview_id=interview_uuid, turn_id=turn_id,
                event_type="grammar_error",
                severity=grammar_result.severity if grammar_result.severity != "none" else "minor",
                title=f"语法：{grammar_result.original[:40]}",
                description=(
                    f"原句「{grammar_result.original}」建议改为「{grammar_result.corrected}」"
                ),
                start_ms=estimated_start_ms, end_ms=estimated_end_ms,
                transcript_snippet=transcript[:200] if transcript else "",
                evidence={"original": grammar_result.original, "corrected": grammar_result.corrected, "tip": grammar_result.spoken_tip},
                suggestion=grammar_result.spoken_tip or f"建议使用：{grammar_result.corrected}",
                display_priority=10 if grammar_result.severity == "serious" else 5,
            ))
            await db.commit()
    except Exception as exc:
        print(f"[WS] Failed to save timeline event: {exc}")


# 全局单例
ws_manager = ConnectionManager()
