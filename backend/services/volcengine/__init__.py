"""火山引擎 · 豆包云端语音能力接入。

当前包含：
- `duplex_client`：端到端实时语音（Seeduplex 全双工）WebSocket 客户端
- `bridge`：把火山引擎下行事件桥接为 OfferGPT 既有的 WebSocket 协议
"""

from services.volcengine.bridge import BridgeResult, DuplexEventBridge
from services.volcengine.duplex_client import (
    DuplexError,
    VolcengineDuplexSession,
    build_session_object,
)

__all__ = [
    "BridgeResult",
    "DuplexError",
    "DuplexEventBridge",
    "VolcengineDuplexSession",
    "build_session_object",
]
