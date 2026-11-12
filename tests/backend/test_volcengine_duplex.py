"""火山引擎云端语音（Seeduplex 全双工）单元测试。

覆盖：session.create 报文构造、下行事件桥接、客户端快速失败、
WebSocket handler 的引擎切换与音频中继降级。
"""

import pytest

from config import settings
from services.volcengine import (
    DuplexError,
    DuplexEventBridge,
    VolcengineDuplexSession,
    build_session_object,
)
from services.volcengine.duplex_client import (
    build_session_create_event,
    extract_error,
)
from websocket.handler import ConnectionManager, SessionState


# ---------------------------------------------------------------------------
# session.create 报文
# ---------------------------------------------------------------------------
class TestSessionPayload:
    def test_default_payload_uses_16k_input_and_24k_output(self):
        session = build_session_object(voice="en_test_voice")
        assert session["model"] == settings.volcengine_speech_model
        assert session["audio"]["input"]["format"] == {"type": "pcm", "rate": 16000}
        assert session["audio"]["output"]["format"] == {
            "type": "pcm_s16le",
            "rate": 24000,
        }
        assert session["audio"]["output"]["voice"] == "en_test_voice"

    def test_no_voice_or_speed_omitted(self):
        session = build_session_object(voice="", speed=0)
        assert "voice" not in session["audio"]["output"]
        assert "speed" not in session["audio"]["output"]

    def test_instructions_and_speed(self):
        session = build_session_object(
            voice="v", speed=20, instructions="be a strict interviewer"
        )
        assert session["instructions"] == "be a strict interviewer"
        assert session["audio"]["output"]["speed"] == 20

    def test_overrides_deep_merge(self):
        session = build_session_object(
            voice="v",
            overrides={"extension": {"tts": {"speaker": "custom"}}},
        )
        assert session["extension"]["tts"]["speaker"] == "custom"
        # 覆盖不应丢失默认字段
        assert session["audio"]["input"]["format"]["rate"] == 16000

    def test_session_create_event_wraps_session(self):
        event = build_session_create_event(voice="v", instructions="hi")
        assert event["type"] == "session.create"
        assert event["session"]["instructions"] == "hi"


class TestExtractError:
    def test_dict_error(self):
        code, message = extract_error({"type": "error", "error": {"code": 40000001, "message": "bad key"}})
        assert code == 40000001
        assert message == "bad key"

    def test_flat_error(self):
        code, message = extract_error({"type": "error", "code": 52000042, "message": "idle timeout"})
        assert code == 52000042
        assert message == "idle timeout"

    def test_non_error(self):
        assert extract_error({"type": "session.created"}) == (None, "")


# ---------------------------------------------------------------------------
# 下行事件桥接
# ---------------------------------------------------------------------------
class TestDuplexEventBridge:
    def _bridge(self) -> DuplexEventBridge:
        counter = {"n": 0}

        def new_turn_id() -> str:
            counter["n"] += 1
            return f"turn_{counter['n']:03d}"

        return DuplexEventBridge("sess-1", new_turn_id)

    def test_happy_path_maps_to_existing_protocol(self):
        bridge = self._bridge()

        partial = bridge.handle({
            "type": "conversation.item.input_audio_transcription.delta",
            "delta": "I have",
        })
        assert partial.messages[0]["type"] == "asr.partial"
        assert partial.messages[0]["partialTranscript"] == "I have"

        final = bridge.handle({
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "I have five years of experience.",
        })
        assert final.messages[0]["type"] == "asr.final"
        assert final.messages[0]["turnId"] == "turn_001"
        assert final.transcript_final == "I have five years of experience."
        assert final.turn_id == "turn_001"

        text = bridge.handle({"type": "response.output_text.delta", "delta": "Great,"})
        assert text.messages[0]["type"] == "agent.text.delta"
        assert text.messages[0]["turnId"] == "turn_001"

        audio = bridge.handle({"type": "response.output_audio.delta", "delta": "UklGRg=="})
        assert audio.messages[0]["type"] == "tts.audio.delta"
        assert audio.messages[0]["codec"] == "pcm16"
        assert audio.messages[0]["sampleRate"] == 24000
        assert audio.messages[0]["payload"] == "UklGRg=="

        done = bridge.handle({"type": "response.output_text.done", "text": "Great, tell me more."})
        assert done.messages[0]["type"] == "agent.text.done"
        assert done.response_text == "Great, tell me more."

    def test_content_before_transcript_is_buffered_then_flushed(self):
        bridge = self._bridge()

        # 模型先于转写结果开始输出
        early_text = bridge.handle({"type": "response.output_text.delta", "delta": "Hello"})
        assert early_text.messages == []
        early_audio = bridge.handle({"type": "response.output_audio.delta", "delta": "AAAA"})
        assert early_audio.messages == []

        final = bridge.handle({
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "Hi there",
        })
        types = [m["type"] for m in final.messages]
        assert types == ["asr.final", "agent.text.delta", "tts.audio.delta"]
        assert all(m["turnId"] == "turn_001" for m in final.messages)

    def test_empty_transcript_yields_no_result(self):
        bridge = self._bridge()
        result = bridge.handle({
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "   ",
        })
        assert result.messages[0]["type"] == "asr.no_result"
        assert result.transcript_final is None

    def test_text_done_without_turn_drops_buffer(self):
        bridge = self._bridge()
        bridge.handle({"type": "response.output_text.delta", "delta": "intro"})
        result = bridge.handle({"type": "response.output_text.done", "text": "intro"})
        assert result.messages == []
        # 缓冲已清空，下一轮不会串话
        final = bridge.handle({
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "ok",
        })
        assert [m["type"] for m in final.messages] == ["asr.final"]

    def test_audio_field_variant(self):
        bridge = self._bridge()
        bridge.handle({
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "hello",
        })
        result = bridge.handle({"type": "response.output_audio.delta", "audio": "QUJD"})
        assert result.messages[0]["payload"] == "QUJD"

    def test_proactive_speech_does_not_pollute_previous_turn(self):
        """主动播报（如不活动提醒）：音频沿用上一轮 turnId，但不重复结束轮次/污染历史。"""
        bridge = self._bridge()
        bridge.handle({
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "hello",
        })
        bridge.handle({"type": "response.output_text.delta", "delta": "hi"})
        first_done = bridge.handle({"type": "response.output_text.done", "text": "hi"})
        assert [m["type"] for m in first_done.messages] == ["agent.text.done"]
        assert first_done.response_text == "hi"

        audio = bridge.handle({"type": "response.output_audio.delta", "delta": "QUJD"})
        assert audio.messages[0]["turnId"] == "turn_001"

        second_done = bridge.handle({
            "type": "response.output_text.done",
            "text": "Are you still there?",
        })
        assert second_done.messages == []
        assert second_done.response_text is None

    def test_error_event(self):
        bridge = self._bridge()
        result = bridge.handle({
            "type": "error",
            "error": {"code": 52000042, "message": "DialogAudioIdleTimeoutError"},
        })
        assert "52000042" in result.error
        assert "IdleTimeout" in result.error

    def test_session_closed(self):
        bridge = self._bridge()
        assert bridge.handle({"type": "session.closed"}).closed is True


# ---------------------------------------------------------------------------
# 客户端
# ---------------------------------------------------------------------------
class TestDuplexClient:
    @pytest.mark.asyncio
    async def test_connect_without_api_key_fails_fast(self):
        session = VolcengineDuplexSession(api_key="")
        with pytest.raises(DuplexError):
            await session.connect()

    def test_headers_include_api_key_and_optional_fields(self):
        session = VolcengineDuplexSession(
            api_key="k", app_id="app", resource_id="res"
        )
        headers = session._headers()
        assert headers["X-Api-Key"] == "k"
        assert headers["X-Api-App-Id"] == "app"
        assert headers["X-Api-Resource-Id"] == "res"
        assert headers["X-Api-Connect-Id"]

    def test_decode_ignores_non_json(self):
        assert VolcengineDuplexSession._decode("not-json") is None
        assert VolcengineDuplexSession._decode(b'{"type":"session.created"}') == {
            "type": "session.created"
        }

    @pytest.mark.asyncio
    async def test_handshake_and_uplink_against_local_server(self):
        """用本地 WebSocket 服务端模拟火山引擎，验证握手/上行/下行全链路。"""
        import json

        import websockets

        received: list[tuple] = []

        async def handler(ws):
            try:
                async for raw in ws:
                    event = json.loads(raw)
                    received.append((event["type"], event))
                    if event["type"] == "session.create":
                        await ws.send(json.dumps({
                            "type": "session.created",
                            "session": {"id": "dlg-test"},
                        }))
                    elif event["type"] == "input_audio_buffer.append":
                        await ws.send(json.dumps({
                            "type": "response.output_text.delta", "delta": "Hi",
                        }))
            except Exception:
                pass

        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            session = VolcengineDuplexSession(
                api_key="test-key",
                ws_url=f"ws://127.0.0.1:{port}",
                voice="en_test_voice",
                connect_timeout=5,
            )
            await session.connect()
            assert session.session_id == "dlg-test"

            await session.send_audio(b"\x00" * 640)
            events: list[str] = []
            async for event in session.events():
                events.append(event["type"])
                if event["type"] == "response.output_text.delta":
                    break
            await session.close()

        kinds = [item[0] for item in received]
        assert kinds[:2] == ["session.create", "input_audio_buffer.append"]
        create_event = received[0][1]
        assert create_event["session"]["model"] == "1.2.6.1"
        assert create_event["session"]["audio"]["output"]["voice"] == "en_test_voice"
        assert events == ["response.output_text.delta"]


# ---------------------------------------------------------------------------
# WebSocket handler 集成
# ---------------------------------------------------------------------------
class TestVoiceEngineRouting:
    def _manager_with_state(self, session_id: str = "sess-cloud") -> tuple[ConnectionManager, SessionState]:
        manager = ConnectionManager()
        state = SessionState(session_id, {"realtimeLightCorrection": True})
        manager._states[session_id] = state
        return manager, state

    @pytest.mark.asyncio
    async def test_voice_engine_unavailable_falls_back_to_local(self, monkeypatch):
        monkeypatch.setattr(settings, "volcengine_speech_api_key", "")
        manager, state = self._manager_with_state()

        result = await manager.handle_message(
            "sess-cloud",
            '{"type": "control.voice_engine", "voiceEngine": "volcengine"}',
        )
        assert result["ack"] == "voice.engine.unavailable"
        assert state.voice_engine == "local"

    @pytest.mark.asyncio
    async def test_audio_dropped_when_cloud_unavailable(self, monkeypatch):
        import base64
        import json

        monkeypatch.setattr(settings, "volcengine_speech_api_key", "")
        manager, state = self._manager_with_state()
        state.voice_engine = "volcengine"

        raw = json.dumps({
            "type": "audio.input",
            "sessionId": "sess-cloud",
            "sequenceId": 1,
            "payload": base64.b64encode(b"\x00" * 960).decode(),
        })
        result = await manager.handle_message("sess-cloud", raw)
        assert result["ack"] == "audio.dropped"
        # 失败后应回落本地引擎
        assert state.voice_engine == "local"

    @pytest.mark.asyncio
    async def test_listening_message_is_noop_without_duplex(self):
        manager, _ = self._manager_with_state()
        result = await manager.handle_message(
            "sess-cloud", '{"type": "control.listening", "listening": false}'
        )
        assert result["ack"] == "listening.updated"

    def test_engine_resolution_prefers_scene_config(self, monkeypatch):
        monkeypatch.setattr(settings, "volcengine_speech_api_key", "test-key")
        state = SessionState("s1", {"voiceEngine": "volcengine"})
        assert state.voice_engine == "volcengine"

    def test_engine_resolution_falls_back_when_not_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "volcengine_speech_api_key", "")
        state = SessionState("s1", {"voiceEngine": "volcengine"})
        assert state.voice_engine == "local"


# ---------------------------------------------------------------------------
# REST：可用语音引擎列表
# ---------------------------------------------------------------------------
class TestVoiceRouter:
    @pytest.mark.asyncio
    async def test_voices_endpoint_lists_both_engines(self, app_client):
        response = await app_client.get("/api/voices")
        assert response.status_code == 200
        body = response.json()
        ids = [item["id"] for item in body["voiceEngines"]]
        assert ids == ["local", "volcengine"]
        local = body["voiceEngines"][0]
        assert local["available"] is True

    @pytest.mark.asyncio
    async def test_cloud_engine_reports_reason_when_unconfigured(self, app_client, monkeypatch):
        monkeypatch.setattr(settings, "volcengine_speech_api_key", "")
        response = await app_client.get("/api/voices")
        cloud = response.json()["voiceEngines"][1]
        assert cloud["available"] is False
        assert "VOLCENGINE_SPEECH_API_KEY" in cloud["reason"]
