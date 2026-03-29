"""
FastAPI Dependencies — Authentication, rate limiting, and request context.

Replaces Flask's g object, @require_auth decorator, @rate_limit decorator.
Uses FastAPI's Depends() for clean dependency injection.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request

from chatbot_viva.core import config
from chatbot_viva.core.rate_limit import RateLimiter

logger = logging.getLogger(__name__)


# ── User model returned by auth dependencies ──

@dataclass
class AuthUser:
    """Authenticated user info — injected via Depends()."""
    id: str
    email: str
    role: str = "user"


# ── Rate limiters (reuse existing RateLimiter class) ──

_rate_limiter = RateLimiter(
    max_requests=config.RATE_LIMIT_MAX,
    window_seconds=config.RATE_LIMIT_WINDOW,
)

_auth_rate_limiter = RateLimiter(
    max_requests=config.AUTH_RATE_LIMIT_MAX,
    window_seconds=config.AUTH_RATE_LIMIT_WINDOW,
)


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, supporting X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _extract_bearer_token(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def _verify_jwt_token(token: str) -> Optional[dict]:
    """Verify JWT token and return payload."""
    from chatbot_viva.services.token_service import verify_access_token
    payload = verify_access_token(token)
    if payload and payload.get("type") == "access":
        return payload
    return None


# ══════════════════════════════════════════════════════════════
# Rate Limit Dependencies
# ══════════════════════════════════════════════════════════════

async def check_rate_limit(request: Request) -> None:
    """
    General rate limit dependency.
    Usage: @app.post("/api/chat", dependencies=[Depends(check_rate_limit)])
    """
    client_ip = _get_client_ip(request)
    if not _rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
        )


async def check_auth_rate_limit(request: Request) -> None:
    """
    Stricter rate limit for auth endpoints.
    Usage: @app.post("/api/auth/login", dependencies=[Depends(check_auth_rate_limit)])
    """
    client_ip = _get_client_ip(request)
    if not _auth_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Quá nhiều yêu cầu. Vui lòng thử lại sau.",
        )


# ══════════════════════════════════════════════════════════════
# Auth Dependencies
# ══════════════════════════════════════════════════════════════

async def get_optional_user(request: Request) -> Optional[AuthUser]:
    """
    Dual-mode auth: JWT token OR API key. Returns None if auth disabled.
    Equivalent to Flask's @require_auth.

    Usage: user = Depends(get_optional_user)
    """
    token = _extract_bearer_token(request)

    # Mode 1: API key (backward compatible, admin/service access)
    if config.API_KEY and token and token == config.API_KEY:
        return None

    # Mode 2: JWT token
    if config.JWT_SECRET_KEY and token:
        payload = _verify_jwt_token(token)
        if payload:
            return AuthUser(
                id=payload["sub"],
                email=payload["email"],
                role=payload.get("role", "user"),
            )

    # Mode 3: Auth disabled
    if not config.API_KEY and not config.JWT_SECRET_KEY:
        return None

    raise HTTPException(status_code=401, detail="Unauthorized")


async def get_current_user(request: Request) -> AuthUser:
    """
    Require JWT user authentication (no API key fallback).
    Equivalent to Flask's @require_user_auth.

    Usage: user = Depends(get_current_user)
    """
    if not config.JWT_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Authentication not configured")

    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload = _verify_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")

    return AuthUser(
        id=payload["sub"],
        email=payload["email"],
        role=payload.get("role", "user"),
    )


async def get_admin_user(request: Request) -> AuthUser:
    """
    Require admin role via JWT.
    Equivalent to Flask's @require_admin.

    Usage: user = Depends(get_admin_user)
    """
    user = await get_current_user(request)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    return user
