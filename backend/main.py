"""OfferGPT Backend – FastAPI application entry point."""

import os
import sys
# Windows GBK 编码修复（必须放在最顶部，在所有 print 之前生效）
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from database import init_db
from exceptions import ApiError, api_error_handler, http_exception_handler, validation_exception_handler
from routers import scenes, interviews, resumes, jobs, auth
from services.asr_service import asr_service
from services.cache_service import cache
from websocket.handler import ws_manager


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"[OfferGPT] Starting server in {settings.env} mode...")
    await cache.connect()
    print(f"[OfferGPT] Cache ping: {await cache.ping()}")
    await init_db()
    print("[OfferGPT] Database initialized")
    if not settings.enable_mock_asr:
        await asr_service.preload()
        if asr_service._use_mock:
            print("[OfferGPT] WARNING: ASR unavailable — voice input will not work until Whisper loads")
        else:
            print(f"[OfferGPT] ASR ready: whisper-{asr_service._model_name}")
    yield
    # Shutdown
    await cache.disconnect()
    print("[OfferGPT] Server stopped")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SpeakUp AI",
    version="1.0.0",
    description="AI Real-Scene English Speaking Coach",
    lifespan=lifespan,
)

# CORS – allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一错误处理
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# REST routers
app.include_router(scenes.router)
app.include_router(resumes.router)
app.include_router(jobs.router)
app.include_router(interviews.router)
app.include_router(auth.router)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/interviews/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: str = ""):
    """
    Real-time voice conversation WebSocket.

    Receives audio.input frames, returns ASR partial/final,
    AI text/audio deltas, and correction/timeline events.

    Query params:
        token: JWT access token（demo 模式下可选，生产模式必须）
    """
    # token 验证：demo 模式放行无 token；生产模式须先 accept 再 close，避免未握手就关闭
    if not settings.demo_mode_enabled:
        if not token:
            await websocket.accept()
            await websocket.close(code=4001, reason="请先登录")
            return
        from auth.jwt import decode_token
        payload = decode_token(token)
        if payload is None or payload.get("type") != "access":
            await websocket.accept()
            await websocket.close(code=4001, reason="登录已过期")
            return

    await ws_manager.connect(websocket, session_id)
    try:
        while True:
            raw = await websocket.receive_text()
            response = await ws_manager.handle_message(session_id, raw)
            if response.get("error"):
                await ws_manager.send_message(session_id, {
                    "type": "error",
                    "sessionId": session_id,
                    "message": response["error"],
                })
    except WebSocketDisconnect:
        pass
    except RuntimeError as exc:
        # 客户端在 accept 后立刻断开时，Starlette 可能抛此异常而非 WebSocketDisconnect
        if "WebSocket is not connected" not in str(exc):
            raise
    finally:
        await ws_manager.disconnect(session_id, websocket)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "env": settings.env,
        "cache": await cache.ping(),
        "wsConnections": ws_manager.active_connections,
    }


# ---------------------------------------------------------------------------
# Entry point – 支持 python main.py 和 uvicorn main:app 两种启动方式
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
    )
