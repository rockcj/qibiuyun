"""WebSocket handler for real-time voice conversation."""

import json
import time
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from services.cache_service import cache


class ConnectionManager:
    """Manage active WebSocket connections."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._session_states: dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        self._connections[session_id] = websocket
        self._session_states[session_id] = {
            "connectedAt": time.time(),
            "messageCount": 0,
            "lastActivity": time.time(),
        }
        print(f"[WS] Client connected: {session_id}")

    async def disconnect(self, session_id: str) -> None:
        self._connections.pop(session_id, None)
        state = self._session_states.pop(session_id, None)
        if state:
            duration = time.time() - state["connectedAt"]
            print(f"[WS] Client disconnected: {session_id} (duration: {duration:.0f}s)")

    async def send_message(self, session_id: str, message: dict) -> bool:
        """Send a JSON message to the client."""
        ws = self._connections.get(session_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            self._session_states[session_id]["messageCount"] += 1
            self._session_states[session_id]["lastActivity"] = time.time()
            return True
        except Exception:
            await self.disconnect(session_id)
            return False

    async def handle_message(self, session_id: str, raw: str) -> dict:
        """Parse and route an incoming WebSocket message."""
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON"}

        msg_type = message.get("type")

        if msg_type == "audio.input":
            # Echo back a partial ASR simulation for early development
            return {"ack": "audio.received", "sequenceId": message.get("sequenceId")}

        elif msg_type == "control.finish":
            await self.send_message(session_id, {
                "type": "control.finish",
                "sessionId": session_id,
                "reason": "userFinished",
                "reportStatus": "generating",
            })
            return {"status": "finishing"}

        return {"error": f"Unknown message type: {msg_type}"}

    @property
    def active_connections(self) -> int:
        return len(self._connections)


# Global singleton
ws_manager = ConnectionManager()
