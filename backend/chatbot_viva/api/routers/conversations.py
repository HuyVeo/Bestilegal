"""Conversation CRUD and sharing endpoints."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from chatbot_viva.core.dependencies import get_optional_user, get_current_user, AuthUser
from chatbot_viva.core.validation import validate_conv_id
from chatbot_viva.services.conversation_service import (
    list_conversations,
    get_conversation as get_conv,
    rename_conversation as rename_conv,
    delete_conversation as delete_conv,
)
from chatbot_viva.services.share_service import (
    create_share_link,
    get_shared_conversation,
    revoke_share_link,
    list_share_links,
)

router = APIRouter()
log = logging.getLogger(__name__)


def _user_id(user: Optional[AuthUser]) -> Optional[str]:
    return user.id if user else None


@router.get("/api/conversations")
async def get_conversations(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: Optional[AuthUser] = Depends(get_optional_user),
):
    try:
        return list_conversations(page=page, per_page=per_page, user_id=_user_id(user))
    except Exception as e:
        log.error("Failed to list conversations: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@router.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str, user: Optional[AuthUser] = Depends(get_optional_user)):
    if not validate_conv_id(conv_id):
        raise HTTPException(status_code=400, detail="invalid conv_id")
    data = get_conv(conv_id, user_id=_user_id(user))
    if data is None:
        raise HTTPException(status_code=404, detail="not found")
    return data


@router.patch("/api/conversations/{conv_id}")
async def rename_conversation(
    conv_id: str,
    request: Request,
    user: Optional[AuthUser] = Depends(get_optional_user),
):
    if not validate_conv_id(conv_id):
        raise HTTPException(status_code=400, detail="invalid conv_id")
    body = await request.json()
    new_title = (body.get("title") or "").strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="title required")
    if len(new_title) > 200:
        raise HTTPException(status_code=400, detail="title too long")
    if not rename_conv(conv_id, new_title, user_id=_user_id(user)):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str, user: Optional[AuthUser] = Depends(get_optional_user)):
    if not validate_conv_id(conv_id):
        raise HTTPException(status_code=400, detail="invalid conv_id")
    delete_conv(conv_id, user_id=_user_id(user))
    return {"ok": True}


# ── Sharing endpoints ──

@router.post("/api/conversations/{conv_id}/share", status_code=201)
async def share_conversation(
    conv_id: str,
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    if not validate_conv_id(conv_id):
        raise HTTPException(status_code=400, detail="invalid conv_id")

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    expires_hours = body.get("expires_hours")

    result = create_share_link(conv_id, user.id, expires_hours)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@router.delete("/api/conversations/{conv_id}/share/{share_id}")
async def delete_share_link(conv_id: str, share_id: str, user: AuthUser = Depends(get_current_user)):
    if not revoke_share_link(share_id, user.id):
        raise HTTPException(status_code=404, detail="Share link not found")
    return {"ok": True}


@router.get("/api/conversations/{conv_id}/shares")
async def get_share_links(conv_id: str, user: AuthUser = Depends(get_current_user)):
    if not validate_conv_id(conv_id):
        raise HTTPException(status_code=400, detail="invalid conv_id")
    return list_share_links(conv_id, user.id)


@router.get("/api/shared/{share_token}")
async def view_shared_conversation(share_token: str):
    data = get_shared_conversation(share_token)
    if data is None:
        raise HTTPException(status_code=404, detail="Link chia sẻ không hợp lệ hoặc đã hết hạn")
    return data
