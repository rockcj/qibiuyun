"""OfferGPT Backend – FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from database import init_db
from exceptions import ApiError, api_error_handler, http_exception_handler, validation_exception_handler
from routers import scenes, interviews, resumes, jobs
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
    yield
    # Shutdown
    await cache.disconnect()
    print("[OfferGPT] Server stopped")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="OfferGPT API",
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


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/interviews/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Real-time voice conversation WebSocket.

    Receives audio.input frames, returns ASR partial/final,
    AI text/audio deltas, and correction/timeline events.
    """
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
    finally:
        await ws_manager.disconnect(session_id)


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
