"""WebSocket 处理器单元测试 – 消息路由、连接管理。"""

import base64
import json

import pytest

from websocket.handler import ConnectionManager, SessionState


def _setup_session(manager: ConnectionManager, session_id: str = "test-session") -> SessionState:
    """注入测试用 SessionState。"""
    state = SessionState(session_id, {"realtimeLightCorrection": True})
    manager._states[session_id] = state
    return state


class TestConnectionManager:
    """WebSocket 连接管理器测试。"""

    def test_initial_active_connections_zero(self):
        """初始连接数应为 0。"""
        manager = ConnectionManager()
        assert manager.active_connections == 0

    @pytest.mark.asyncio
    async def test_handle_audio_input_message(self):
        """audio.input 消息应返回 ack。"""
        manager = ConnectionManager()
        _setup_session(manager)
        # 最小有效 PCM payload（960 bytes = 30ms @ 16kHz）
        pcm_payload = base64.b64encode(b"\x00" * 960).decode()
        raw = json.dumps({
            "type": "audio.input",
            "sessionId": "test-session",
            "sequenceId": 1,
            "payload": pcm_payload,
        })
        result = await manager.handle_message("test-session", raw)
        assert result.get("ack") == "audio.received"

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self):
        """非法 JSON 应返回错误。"""
        manager = ConnectionManager()
        result = await manager.handle_message("test-session", "not-json")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_handle_unknown_message_type(self):
        """未知消息类型应返回错误。"""
        manager = ConnectionManager()
        _setup_session(manager)
        raw = json.dumps({"type": "unknown.type", "sessionId": "test"})
        result = await manager.handle_message("test-session", raw)
        assert "error" in result
        assert "Unknown message type" in result["error"]

    @pytest.mark.asyncio
    async def test_send_message_without_connection_returns_false(self):
        """无活跃连接时 send_message 应返回 False。"""
        manager = ConnectionManager()
        result = await manager.send_message("nonexistent", {"type": "test"})
        assert result is False

    @pytest.mark.asyncio
    async def test_correction_toggle(self):
        """control.correction 消息应切换实时轻纠正开关。"""
        manager = ConnectionManager()
        session_id = "test-correction-toggle"
        state = _setup_session(manager, session_id)

        assert state.realtime_correction_enabled is True

        raw = json.dumps({"type": "control.correction", "enabled": False})
        result = await manager.handle_message(session_id, raw)
        assert result.get("ack") == "correction.updated"
        assert state.realtime_correction_enabled is False

        raw2 = json.dumps({"type": "control.correction", "enabled": True})
        result2 = await manager.handle_message(session_id, raw2)
        assert state.realtime_correction_enabled is True
