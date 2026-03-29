"""Health and utility endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from chatbot_viva.core import config
from chatbot_viva.core.cache import get_response_cache
from chatbot_viva.core.constants import SUGGESTED_QUESTIONS
from chatbot_viva.core.dependencies import get_optional_user

router = APIRouter()


@router.get("/api/health")
async def health():
    from chatbot_viva.core.db import check_db_health
    db_ok = check_db_health()
    cache = get_response_cache()
    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "model": config.LLM_MODEL,
        "database": "connected" if db_ok else "disconnected",
        "cache": cache.stats.get("backend", "unknown"),
    }


@router.get("/api/suggestions/default")
async def default_suggestions():
    return SUGGESTED_QUESTIONS


@router.get("/api/cache/stats")
async def cache_stats(_user=Depends(get_optional_user)):
    cache = get_response_cache()
    return cache.stats


@router.post("/api/cache/clear")
async def cache_clear(_user=Depends(get_optional_user)):
    cache = get_response_cache()
    cache.clear_all()
    return {"ok": True, "message": "Cache cleared"}
