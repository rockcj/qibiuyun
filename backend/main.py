"""OfferGPT Backend – FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routers import scenes, interviews
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

# REST routers
app.include_router(scenes.router)
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
