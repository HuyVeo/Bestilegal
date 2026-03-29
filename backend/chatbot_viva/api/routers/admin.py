"""Admin endpoints — user management and system-wide conversation access."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from chatbot_viva.core.dependencies import get_admin_user, AuthUser
from chatbot_viva.services.user_service import list_users, set_user_role, deactivate_user
from chatbot_viva.services.conversation_service import list_conversations

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/api/admin/users")
async def get_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _admin: AuthUser = Depends(get_admin_user),
):
    try:
        return list_users(page=page, per_page=per_page)
    except Exception as e:
        log.error("Failed to list users: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list users")


@router.patch("/api/admin/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    request: Request,
    _admin: AuthUser = Depends(get_admin_user),
):
    body = await request.json()
    role = (body.get("role") or "").strip()
    if role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role phải là 'user' hoặc 'admin'")
    if not set_user_role(user_id, role):
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "role": role}


@router.delete("/api/admin/users/{user_id}")
async def delete_user(user_id: str, _admin: AuthUser = Depends(get_admin_user)):
    if not deactivate_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@router.get("/api/admin/conversations")
async def get_all_conversations(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _admin: AuthUser = Depends(get_admin_user),
):
    try:
        return list_conversations(page=page, per_page=per_page, user_id=None)
    except Exception as e:
        log.error("Failed to list conversations: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list conversations")
