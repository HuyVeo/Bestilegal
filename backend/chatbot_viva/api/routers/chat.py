"""Chat endpoint — streaming SSE via FastAPI."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from chatbot_viva.core import config
from chatbot_viva.core.dependencies import get_optional_user, check_rate_limit, AuthUser
from chatbot_viva.core.validation import validate_chat_input
from chatbot_viva.services.engine import initialize_chatbot_flask
from chatbot_viva.services.chat_orchestrator import run_chat_pipeline

router = APIRouter()
log = logging.getLogger(__name__)


def _warmup_chatbot():
    """Warm up the chatbot initialization (thread-safe, called exactly once)."""
    return initialize_chatbot_flask()


@router.post(
    "/api/chat",
    dependencies=[Depends(check_rate_limit)],
)
async def chat(request: Request, user: Optional[AuthUser] = Depends(get_optional_user)):
    body = await request.json()
    question: str = (body.get("question") or "").strip()
    messages: List[Dict] = body.get("messages", [])
    conv_id: Optional[str] = body.get("conv_id")

    errors = validate_chat_input(question, conv_id)
    if errors:
        raise HTTPException(status_code=400, detail=errors[0])

    if len(messages) > config.MAX_MESSAGES_COUNT:
        raise HTTPException(status_code=400, detail="Too many messages in history")

    user_id = user.id if user else None

    log.info("Chat request: %s (messages=%d, conv_id=%s, user=%s)",
             question[:60], len(messages), conv_id, user_id)

    try:
        _warmup_chatbot()
    except Exception as e:
        log.error("Chatbot initialization failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Chatbot khởi tạo thất bại: {e}. "
                   "Vui lòng kiểm tra MONGODB_URI, QDRANT_URL và OPENAI_API_KEY.",
        )

    return StreamingResponse(
        run_chat_pipeline(question, messages, conv_id, user_id=user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
