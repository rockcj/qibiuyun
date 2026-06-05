"""WebSocket 处理器单元测试 – 消息路由、连接管理。"""

import json

import pytest

from websocket.handler import ConnectionManager


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
        raw = json.dumps({
            "type": "audio.input",
            "sessionId": "test-session",
            "sequenceId": 1,
            "payload": "base64chunk",
        })
        result = await manager.handle_message("test-session", raw)
        assert result.get("ack") == "audio.received"
        assert result.get("sequenceId") == 1

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
