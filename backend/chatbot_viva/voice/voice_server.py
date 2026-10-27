"""
Vietnamese Voice AI — Full-Duplex WebSocket Server

Tích hợp voice pipeline (VAD → STT → TTS) với hệ thống RAG chatbot_viva hiện tại.
Pipeline: Continuous Audio → VAD Turn Detection → STT → chatbot_viva RAG → LLM → TTS → Audio

Tối ưu so với bản trước:
  - Pipeline voice/text hợp nhất (_run_pipeline) — không duplicate code
  - TTS chạy song song với LLM qua tts_queue — giảm latency đáng kể
  - Edge-TTS streaming chunks — giảm Time-To-First-Byte
  - Sentence splitting cải thiện cho tiếng Việt
  - VAD per-session state — không còn shared buffer bug
"""
import asyncio
import base64
import json
import os
import re
import sys
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ── Resolve project root (only needed for standalone mode) ──
project_root = Path(__file__).parent.parent.parent.parent.resolve()
if str(project_root / "src") not in sys.path:
    os.chdir(str(project_root))
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / "src"))
    load_dotenv(project_root / ".env", override=True)

# ── Voice services (self-contained, async) ──
from chatbot_viva.voice.vad_service import VADService, TurnDetector, VADSession
from chatbot_viva.voice.stt_service import STTService
from chatbot_viva.voice.tts_service import TTSService

# ── chatbot_viva RAG pipeline (sync — gọi qua asyncio.to_thread) ──
from chatbot_viva.core import config
from chatbot_viva.core.config import validate_config
from chatbot_viva.retrieval.vector_store import get_retriever
from chatbot_viva.services.rag_service import rag_search, build_rag_context
from chatbot_viva.services.chat_service import stream_llm_response_plain
from chatbot_viva.services.engine import initialize_chatbot_flask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Voice service singletons ──
vad_service: Optional[VADService] = None
stt_service: Optional[STTService] = None
tts_service: Optional[TTSService] = None

# ── Flag: chatbot_viva RAG initialized ──
_rag_ready = threading.Event()

# ── Sentence splitting regex (tiếng Việt) ──
# Cắt tại: . ! ? ; và ... (ellipsis) — giữ dấu câu gắn với câu trước
_SENTENCE_SPLIT_RE = re.compile(r'(\.{2,3}|[.!?;])\s+')

# Ngưỡng barge-in
_BARGE_IN_ENERGY = float(os.getenv("BARGE_IN_ENERGY", "0.08"))


def _warmup_rag():
    """Initialize chatbot_viva RAG (Qdrant + BM25) in background thread."""
    try:
        logger.info("Warming up chatbot_viva RAG pipeline...")
        initialize_chatbot_flask()
        _rag_ready.set()
        logger.info("chatbot_viva RAG pipeline ready")
    except Exception as e:
        logger.error("RAG warmup failed: %s", e)
        _rag_ready.set()  # unblock callers even on failure


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize voice services + chatbot_viva RAG on startup."""
    global vad_service, stt_service, tts_service

    logger.info("Starting Vietnamese Voice AI (Full-Duplex) + chatbot_viva RAG...")

    # Voice services (fast init)
    vad_service = VADService()
    stt_service = STTService()
    tts_service = TTSService()

    # chatbot_viva RAG (slow init — background thread)
    threading.Thread(target=_warmup_rag, daemon=True).start()

    logger.info("Voice services ready — RAG warming up in background")
    yield
    logger.info("Shutting down voice server...")


# ── FastAPI App ──
app = FastAPI(title="Vietnamese Voice AI + chatbot_viva RAG", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# Session Management
# ══════════════════════════════════════════════════════════════════════════════

class ConversationSession:
    """Quản lý 1 phiên hội thoại full-duplex giữa client và AI."""

    def __init__(self):
        self.conversation_history: list[dict] = []
        self.voice = os.getenv("DEFAULT_VOICE", "female")
        self.is_ai_speaking = False
        self.cancelled = False
        self.is_conversation_active = False
        self.max_history = int(os.getenv("MAX_CONVERSATION_HISTORY", "20"))
        self.turn_detector: Optional[TurnDetector] = None
        self.barge_in_vad: Optional[VADSession] = None
        self.pipeline_task: Optional[asyncio.Task] = None
        self.pipeline_lock = asyncio.Lock()

    def add_message(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]


# ══════════════════════════════════════════════════════════════════════════════
# REST Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "message": "Voice AI + chatbot_viva RAG",
        "rag_ready": _rag_ready.is_set(),
    }


@app.get("/api/voices")
async def get_voices():
    return {
        "voices": [
            {"id": "female", "name": "Hoài My (Nữ)", "code": "vi-VN-HoaiMyNeural"},
            {"id": "male", "name": "Nam Minh (Nam)", "code": "vi-VN-NamMinhNeural"},
        ]
    }


# ══════════════════════════════════════════════════════════════════════════════
# WebSocket Voice Endpoint
# ══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    session = ConversationSession()
    logger.info("Client connected to voice WebSocket")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "config":
                session.voice = msg.get("voice", session.voice)
                await websocket.send_json({
                    "type": "config_ok",
                    "voice": session.voice,
                    "mode": "full_duplex",
                })

            elif msg_type == "start_conversation":
                await start_conversation(websocket, session)

            elif msg_type == "stop_conversation":
                await stop_conversation(websocket, session)

            elif msg_type == "audio_chunk":
                if session.is_conversation_active and session.turn_detector:
                    chunk = base64.b64decode(msg["data"])
                    await handle_audio_chunk(websocket, session, chunk)

            elif msg_type == "chat_message":
                text = msg.get("text", "")
                if text:
                    session.cancelled = False
                    await websocket.send_json({"type": "transcript_user", "text": text})
                    session.add_message("user", text)
                    await _run_pipeline(websocket, session, text)

            elif msg_type == "interrupt":
                await handle_barge_in(websocket, session)

            elif msg_type == "start_recording":
                session.cancelled = False
                await websocket.send_json({"type": "recording_started"})

            elif msg_type == "stop_recording":
                if "audio" in msg:
                    audio_bytes = base64.b64decode(msg["audio"])
                else:
                    audio_bytes = None
                if audio_bytes and len(audio_bytes) > 1600:
                    await _run_voice_pipeline(websocket, session, audio_bytes)

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if session.pipeline_task and not session.pipeline_task.done():
            session.pipeline_task.cancel()
        session.is_conversation_active = False


# ══════════════════════════════════════════════════════════════════════════════
# Conversation Control
# ══════════════════════════════════════════════════════════════════════════════

async def start_conversation(websocket: WebSocket, session: ConversationSession):
    session.is_conversation_active = True
    session.cancelled = False
    session.turn_detector = TurnDetector(vad_service)
    session.barge_in_vad = vad_service.create_session()
    session.turn_detector.start_listening()
    await websocket.send_json({
        "type": "conversation_started",
        "message": "Full-duplex mode active",
    })
    logger.info("Full-duplex conversation started")


async def stop_conversation(websocket: WebSocket, session: ConversationSession):
    session.is_conversation_active = False
    session.cancelled = True
    if session.pipeline_task and not session.pipeline_task.done():
        session.pipeline_task.cancel()
    if session.turn_detector:
        session.turn_detector.reset()
        session.turn_detector = None
    session.barge_in_vad = None
    session.is_ai_speaking = False
    await websocket.send_json({
        "type": "conversation_stopped",
        "message": "Conversation ended",
    })
    logger.info("Full-duplex conversation stopped")


# ══════════════════════════════════════════════════════════════════════════════
# Audio Processing (VAD + Barge-in)
# ══════════════════════════════════════════════════════════════════════════════

async def handle_audio_chunk(websocket: WebSocket, session: ConversationSession, chunk: bytes):
    if not session.turn_detector:
        return

    # Barge-in detection khi AI đang nói — dùng VADSession riêng
    if session.is_ai_speaking:
        audio_np = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        energy = float(np.sqrt(np.mean(audio_np ** 2)))
        if energy > _BARGE_IN_ENERGY and session.barge_in_vad and session.barge_in_vad.is_speech(audio_np):
            logger.info("Barge-in detected (energy=%.3f)", energy)
            await handle_barge_in(websocket, session)
        return

    # Turn detection khi đang lắng nghe
    result = session.turn_detector.process_audio(chunk)

    await websocket.send_json({
        "type": "vad_status",
        "speaking": result["is_speech"],
        "state": session.turn_detector.state.value,
    })

    if result["event"] == "speech_start":
        logger.info("Speech detected - user started talking")
        await websocket.send_json({"type": "turn_start"})

    elif result["event"] == "speech_end":
        logger.info("User finished speaking - processing turn")
        await websocket.send_json({"type": "turn_end"})

        audio_bytes = result["audio"]
        if audio_bytes and len(audio_bytes) > 1600:
            if session.pipeline_task and not session.pipeline_task.done():
                session.pipeline_task.cancel()
                try:
                    await session.pipeline_task
                except (asyncio.CancelledError, Exception):
                    pass
            session.cancelled = False
            session.pipeline_task = asyncio.create_task(
                _run_voice_pipeline(websocket, session, audio_bytes)
            )


async def handle_barge_in(websocket: WebSocket, session: ConversationSession):
    if session.is_ai_speaking:
        logger.info("Barge-in: user interrupted AI")
        session.cancelled = True
        session.is_ai_speaking = False
        if session.pipeline_task and not session.pipeline_task.done():
            session.pipeline_task.cancel()
            try:
                await session.pipeline_task
            except (asyncio.CancelledError, Exception):
                pass
        await websocket.send_json({"type": "interrupted"})
        if session.turn_detector and session.is_conversation_active:
            session.turn_detector.start_listening()


# ══════════════════════════════════════════════════════════════════════════════
# RAG Bridge — gọi sync chatbot_viva pipeline từ async context
# ══════════════════════════════════════════════════════════════════════════════

def _sync_rag_search(query: str) -> tuple:
    """
    Gọi chatbot_viva RAG pipeline (sync).
    Returns: (context_str, sources_info_list)
    """
    if not _rag_ready.is_set():
        _rag_ready.wait(timeout=60)

    try:
        retriever = get_retriever()
        legal_articles = rag_search(retriever, query)
        if not legal_articles:
            return "", []

        rag_response = build_rag_context(legal_articles)
        context = rag_response.rag_context

        sources_info = []
        for art in legal_articles[:5]:
            sources_info.append({
                "document_name": art.document_name,
                "article": art.article,
                "snippet": art.snippet,
                "score": art.score,
                "source_url": art.source_url,
            })

        return context, sources_info

    except Exception as e:
        logger.error("RAG search error: %s", e)
        return "", []


# ══════════════════════════════════════════════════════════════════════════════
# Unified Pipeline (STT → RAG → LLM streaming → TTS streaming)
# ══════════════════════════════════════════════════════════════════════════════

async def _run_voice_pipeline(
    websocket: WebSocket,
    session: ConversationSession,
    audio_bytes: bytes,
):
    """Voice pipeline: Audio → STT → _run_pipeline (RAG → LLM → TTS)."""
    async with session.pipeline_lock:
        try:
            session.is_ai_speaking = True

            # ── STT ──
            await websocket.send_json({
                "type": "status", "stage": "stt",
                "message": "Đang nhận dạng giọng nói...",
            })
            logger.info("STT: nhận %d bytes audio (%.2fs)", len(audio_bytes), len(audio_bytes) / 32000)

            try:
                user_text = await stt_service.transcribe(audio_bytes)
            except Exception as stt_err:
                logger.error("STT exception: %s", stt_err)
                user_text = ""

            if not user_text or not user_text.strip():
                session.is_ai_speaking = False
                logger.info("STT: không nhận ra text, skip pipeline")
                await websocket.send_json({
                    "type": "error",
                    "message": "Không nghe rõ, vui lòng nói lại",
                })
                await websocket.send_json({"type": "audio_done"})
                if session.turn_detector and session.is_conversation_active:
                    session.turn_detector.start_listening()
                return

            await websocket.send_json({"type": "transcript_user", "text": user_text})
            session.add_message("user", user_text)
            logger.info("User: %s", user_text)

            # ── RAG → LLM → TTS (shared pipeline) ──
            await _run_pipeline_inner(websocket, session, user_text)

        except asyncio.CancelledError:
            logger.info("Voice pipeline cancelled (barge-in)")
            session.is_ai_speaking = False
        except Exception as e:
            logger.error("Voice pipeline error: %s", e)
            await websocket.send_json({"type": "error", "message": f"Lỗi xử lý: {str(e)}"})
            session.is_ai_speaking = False
            if session.turn_detector and session.is_conversation_active:
                session.turn_detector.start_listening()


async def _run_pipeline(
    websocket: WebSocket,
    session: ConversationSession,
    text: str,
):
    """Text pipeline: RAG → LLM → TTS (skip STT)."""
    async with session.pipeline_lock:
        try:
            session.is_ai_speaking = True
            await _run_pipeline_inner(websocket, session, text)
        except Exception as e:
            logger.error("Text pipeline error: %s", e)
            session.is_ai_speaking = False
            if session.turn_detector and session.is_conversation_active:
                session.turn_detector.start_listening()


async def _run_pipeline_inner(
    websocket: WebSocket,
    session: ConversationSession,
    user_text: str,
):
    """
    Core pipeline: RAG → LLM streaming → TTS streaming → Audio out.

    Tối ưu chính:
      - LLM chunks được xử lý liên tục, không bị block bởi TTS
      - TTS chạy song song qua tts_queue (ordered)
      - Edge-TTS stream chunks ngay khi có — giảm TTFB
    """
    # ── BƯỚC 1: RAG ──
    await websocket.send_json({
        "type": "status", "stage": "rag",
        "message": "Đang tìm kiếm thông tin...",
    })

    context, sources_info = await asyncio.to_thread(_sync_rag_search, user_text)
    if context:
        logger.info("RAG: inject context (%d ký tự, %d nguồn)", len(context), len(sources_info))

    if session.cancelled:
        return

    # ── BƯỚC 2: LLM streaming + TTS song song ──
    await websocket.send_json({
        "type": "status", "stage": "llm",
        "message": "Đang suy nghĩ...",
    })

    session.is_ai_speaking = True
    session.cancelled = False

    full_response = ""
    sentence_buffer = ""

    # Queue cho TTS: LLM push câu hoàn chỉnh, TTS worker xử lý song song
    tts_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

    async def _tts_worker():
        """Xử lý TTS theo thứ tự — chạy song song với LLM consumption."""
        while True:
            text = await tts_queue.get()
            if text is None:  # sentinel
                break
            if session.cancelled:
                continue
            await _stream_tts_audio(websocket, session, text)

    tts_task = asyncio.create_task(_tts_worker())

    # LLM stream qua thread + queue
    chunk_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

    def _llm_worker():
        try:
            for chunk in stream_llm_response_plain(
                question=user_text,
                context=context,
                sources_info=sources_info,
                conversation_messages=session.conversation_history,
                response_style="general",
            ):
                chunk_queue.put_nowait(chunk)
        except Exception as e:
            logger.error("LLM stream error: %s", e)
        finally:
            chunk_queue.put_nowait(None)  # sentinel

    llm_thread = threading.Thread(target=_llm_worker, daemon=True)
    llm_thread.start()

    # Consume LLM chunks, split sentences, push to TTS queue
    while True:
        try:
            chunk_text = await asyncio.wait_for(chunk_queue.get(), timeout=120)
        except asyncio.TimeoutError:
            logger.error("LLM stream timeout (120s)")
            break
        if chunk_text is None:
            break
        if session.cancelled:
            break

        full_response += chunk_text
        sentence_buffer += chunk_text

        await websocket.send_json({
            "type": "transcript_ai_partial",
            "text": chunk_text,
            "full_text": full_response,
        })

        # Split thành câu hoàn chỉnh → push to TTS queue (non-blocking)
        sentences = split_sentences(sentence_buffer)
        if len(sentences) > 1:
            for sent in sentences[:-1]:
                if sent.strip() and not session.cancelled:
                    await tts_queue.put(sent.strip())
            sentence_buffer = sentences[-1]

    # Câu cuối cùng
    if sentence_buffer.strip() and not session.cancelled:
        await tts_queue.put(sentence_buffer.strip())

    # Signal TTS worker to finish
    await tts_queue.put(None)
    await tts_task  # Wait for all TTS to complete

    if not session.cancelled:
        session.add_message("assistant", full_response)
        await websocket.send_json({
            "type": "transcript_ai",
            "text": full_response,
            "done": True,
        })
        logger.info("AI: %s...", full_response[:80])

    await websocket.send_json({"type": "audio_done"})
    session.is_ai_speaking = False

    if session.turn_detector and session.is_conversation_active:
        session.turn_detector.start_listening()


# ══════════════════════════════════════════════════════════════════════════════
# TTS Audio Streaming
# ══════════════════════════════════════════════════════════════════════════════

async def _stream_tts_audio(
    websocket: WebSocket,
    session: ConversationSession,
    text: str,
):
    """
    Stream TTS audio cho 1 câu qua WebSocket.
    Edge-TTS: stream chunks ngay khi nhận (giảm TTFB).
    Other engines: synthesize full rồi gửi 8KB chunks.
    """
    try:
        logger.info("TTS generating: %s...", text[:50])
        is_first = True
        total_bytes = 0

        async for chunk in tts_service.synthesize_stream(text, voice=session.voice):
            if session.cancelled:
                break
            # Gửi từng chunk TTS ngay khi nhận (thường 4-32KB mỗi chunk)
            total_bytes += len(chunk)
            await websocket.send_json({
                "type": "audio_chunk",
                "data": base64.b64encode(chunk).decode("utf-8"),
                "format": "mp3",
                "text": text if is_first else None,
            })
            is_first = False
            await asyncio.sleep(0)  # yield to event loop

        logger.info("TTS done: %d bytes", total_bytes)
    except Exception as e:
        logger.error("TTS error: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# Text Utilities
# ══════════════════════════════════════════════════════════════════════════════

def split_sentences(text: str) -> list[str]:
    """
    Cắt text thành câu cho streaming TTS.
    Hỗ trợ: . ! ? ; ... và xuống dòng.
    Giữ dấu câu gắn liền câu trước.
    """
    # Split tại các dấu câu theo sau bởi khoảng trắng
    parts = _SENTENCE_SPLIT_RE.split(text)
    sentences = []
    current = ""
    for i, part in enumerate(parts):
        current += part
        # Nếu part là dấu câu (matched group), kết thúc câu
        if _SENTENCE_SPLIT_RE.match(part + " "):
            sentences.append(current)
            current = ""
        elif part.rstrip() in (".", "!", "?", ";", "...", "..."):
            sentences.append(current)
            current = ""

    if current:
        sentences.append(current)

    # Fallback: nếu câu quá dài (>200 ký tự) mà không có dấu câu,
    # cắt tại dấu phẩy hoặc dấu hai chấm gần nhất
    result = []
    for sent in sentences:
        if len(sent) > 200:
            sub_parts = re.split(r'([,:]\s+)', sent)
            sub_current = ""
            for sp in sub_parts:
                sub_current += sp
                if len(sub_current) > 120 and sp.strip() in (",", ":"):
                    result.append(sub_current)
                    sub_current = ""
            if sub_current:
                result.append(sub_current)
        else:
            result.append(sent)

    return result if result else [text]


# ══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("VOICE_SERVER_PORT", "8000"))
    logger.info("Starting Voice Server on port %d", port)
    uvicorn.run("chatbot_viva.voice.voice_server:app", host="0.0.0.0", port=port, reload=True)
