"""
FastAPI API for Vietnamese Real Estate Chatbot (Chatbot BĐS Viva)

Unified server — REST API + Voice WebSocket on single port.
Replaces the former Flask + separate FastAPI voice server.
"""
from __future__ import annotations

import sys
import os
import threading
import logging
import atexit
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# ── Resolve project root and change CWD so all relative paths work ──
project_root = Path(__file__).parent.parent.parent.parent.resolve()
os.chdir(str(project_root))
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))
load_dotenv(project_root / ".env", override=True)

from chatbot_viva.core import config
from chatbot_viva.core.config import validate_config
from chatbot_viva.core.logging_config import setup_logging, set_request_id
from chatbot_viva.core.tracing import get_langfuse_callback, flush_langfuse

# ── Patch config paths to absolute ──
config.BASE_DIR = project_root
config.VECTORSTORE_PATH = project_root / "qdrant_db"

# ── Setup logging ──
logger = setup_logging(level=config.LOG_LEVEL, json_output=config.LOG_JSON)
log = logging.getLogger(__name__)

# ── Validate configuration ──
_config_errors = validate_config()
for _err in _config_errors:
    if _err.startswith("CRITICAL"):
        log.critical(_err)
    else:
        log.warning(_err)


# ══════════════════════════════════════════════════════════════
# Background warmup
# ══════════════════════════════════════════════════════════════

_warmup_done = threading.Event()


def _warmup():
    """Pre-initialise chatbot so the first HTTP request is fast."""
    try:
        log.info("Warming up chatbot in background...")
        from chatbot_viva.services.engine import initialize_chatbot_flask
        initialize_chatbot_flask()
        log.info("Chatbot ready")
    except Exception as e:
        log.error("Warmup failed: %s", e)
    finally:
        _warmup_done.set()


# ══════════════════════════════════════════════════════════════
# Voice services initialization (optional)
# ══════════════════════════════════════════════════════════════

_voice_enabled = os.getenv("VOICE_ENABLED", "true").lower() == "true"


def _init_voice_services():
    """Initialize VAD, STT, TTS services if voice is enabled."""
    if not _voice_enabled:
        return None, None, None
    try:
        from chatbot_viva.voice.vad_service import VADService
        from chatbot_viva.voice.stt_service import STTService
        from chatbot_viva.voice.tts_service import TTSService

        vad = VADService()
        stt = STTService()
        tts = TTSService()
        log.info("Voice services initialized (VAD + STT + TTS)")
        return vad, stt, tts
    except ImportError as e:
        log.warning("Voice dependencies not installed: %s. Install with: pip install -e '.[voice]'", e)
        return None, None, None


# ══════════════════════════════════════════════════════════════
# FastAPI App with Lifespan
# ══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    log.info("Starting Chatbot BĐS Viva — FastAPI")

    # Database schema
    try:
        from chatbot_viva.core.db import ensure_schema
        ensure_schema()
    except Exception as e:
        log.error("Failed to initialize database schema: %s", e)

    # Background warmup (chatbot RAG pipeline)
    threading.Thread(target=_warmup, daemon=True).start()

    # Voice services
    if _voice_enabled:
        vad, stt, tts = _init_voice_services()
        if vad:
            # Make voice services accessible to voice_server module
            import chatbot_viva.voice.voice_server as vs
            vs.vad_service = vad
            vs.stt_service = stt
            vs.tts_service = tts
            vs._rag_ready = _warmup_done

    # Langfuse
    get_langfuse_callback()

    log.info("  Model   : %s", config.LLM_MODEL)
    log.info("  Provider: %s", config.LLM_PROVIDER)
    log.info("  Voice   : %s", "ON" if _voice_enabled else "OFF")

    yield

    log.info("Shutting down...")
    flush_langfuse()


app = FastAPI(
    title="Chatbot BĐS Viva",
    description="Vietnamese Real Estate Legal RAG Chatbot",
    lifespan=lifespan,
)

# ── CORS ──
cors_origins = config.CORS_ORIGINS.split(",") if config.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security headers middleware ──
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    set_request_id()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ══════════════════════════════════════════════════════════════
# Register API routers
# ══════════════════════════════════════════════════════════════

from chatbot_viva.api.routers import ALL_ROUTERS

for router in ALL_ROUTERS:
    app.include_router(router)


# ── Voice WebSocket (conditionally mounted) ──
if _voice_enabled:
    try:
        from chatbot_viva.voice.voice_server import app as voice_app

        # Mount voice endpoints directly — no separate server needed
        @app.websocket("/ws/voice")
        async def voice_ws_proxy(websocket):
            """Forward to voice server's WebSocket handler."""
            from chatbot_viva.voice.voice_server import voice_websocket
            await voice_websocket(websocket)

        @app.get("/api/voices")
        async def get_voices():
            return {
                "voices": [
                    {"id": "female", "name": "Hoài My (Nữ)", "code": "vi-VN-HoaiMyNeural"},
                    {"id": "male", "name": "Nam Minh (Nam)", "code": "vi-VN-NamMinhNeural"},
                ]
            }

        log.info("Voice WebSocket mounted at /ws/voice")
    except ImportError:
        log.info("Voice module not available — WebSocket disabled")


# ══════════════════════════════════════════════════════════════
# Static frontend (SPA)
# ══════════════════════════════════════════════════════════════

static_dir = project_root / "static"


@app.get("/")
async def index():
    return FileResponse(str(static_dir / "index.html"))


@app.get("/shared/{token}")
async def shared_view(token: str):
    """Serve SPA for shared conversation links."""
    return FileResponse(str(static_dir / "index.html"))


@app.get("/admin")
@app.get("/admin/{subpath:path}")
async def spa_admin(subpath: str = ""):
    """Serve SPA for admin routes."""
    return FileResponse(str(static_dir / "index.html"))


# Mount static files LAST (catch-all)
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


# ══════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "5000"))
    log.info("Starting on http://0.0.0.0:%d", port)

    atexit.register(flush_langfuse)

    uvicorn.run(
        "chatbot_viva.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )
