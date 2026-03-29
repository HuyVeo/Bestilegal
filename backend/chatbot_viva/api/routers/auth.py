"""Authentication endpoints — register, login, refresh, logout, profile."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from chatbot_viva.core import config
from chatbot_viva.core.dependencies import get_current_user, check_auth_rate_limit, AuthUser
from chatbot_viva.core.validation import (
    validate_registration,
    validate_login,
    validate_password_change,
)
from chatbot_viva.core.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
)
from chatbot_viva.services.user_service import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    verify_password,
    update_user_profile,
    change_password,
)
from chatbot_viva.services.token_service import (
    create_access_token,
    create_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
    revoke_user_tokens,
)

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/api/auth/register", dependencies=[Depends(check_auth_rate_limit)], status_code=201)
async def register(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    display_name = (body.get("display_name") or "").strip()

    errors = validate_registration(email, password, display_name)
    if errors:
        raise HTTPException(status_code=400, detail={"error": errors[0], "errors": errors})

    try:
        user = create_user(email, password, display_name)
        log.info("User registered: %s", email)
        return {"message": "Đăng ký thành công", "user": user}
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        log.error("Registration failed: %s", e)
        raise HTTPException(status_code=500, detail="Đăng ký thất bại")


@router.post("/api/auth/login", dependencies=[Depends(check_auth_rate_limit)])
async def login(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""

    errors = validate_login(email, password)
    if errors:
        raise HTTPException(status_code=400, detail=errors[0])

    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa")

    user_id = user["id"]
    access_token = create_access_token(user_id, user["email"], user.get("role", "user"))
    refresh_token = create_refresh_token(user_id)

    user.pop("password_hash", None)

    log.info("User logged in: %s", email)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": config.JWT_ACCESS_TOKEN_EXPIRES,
        "user": user,
    }


@router.post("/api/auth/refresh", dependencies=[Depends(check_auth_rate_limit)])
async def refresh(request: Request):
    body = await request.json()
    refresh_token_val = body.get("refresh_token") or ""

    if not refresh_token_val:
        raise HTTPException(status_code=400, detail="refresh_token là bắt buộc")

    result = rotate_refresh_token(refresh_token_val)
    if result is None:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")

    new_access, new_refresh = result
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "Bearer",
        "expires_in": config.JWT_ACCESS_TOKEN_EXPIRES,
    }


@router.post("/api/auth/logout")
async def logout(request: Request, user: AuthUser = Depends(get_current_user)):
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    refresh_token_val = body.get("refresh_token")
    revoke_all = body.get("revoke_all", False)

    if revoke_all:
        revoke_user_tokens(user.id)
        return {"message": "Đã đăng xuất khỏi tất cả thiết bị"}

    if refresh_token_val:
        revoke_refresh_token(refresh_token_val)

    return {"message": "Đã đăng xuất"}


@router.get("/api/auth/me")
async def get_profile(user: AuthUser = Depends(get_current_user)):
    user_data = get_user_by_id(user.id)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    return user_data


@router.patch("/api/auth/me")
async def update_profile(request: Request, user: AuthUser = Depends(get_current_user)):
    body = await request.json()
    display_name = body.get("display_name")

    if display_name is None:
        raise HTTPException(status_code=400, detail="display_name là bắt buộc")
    if len(display_name) > 100:
        raise HTTPException(status_code=400, detail="Tên hiển thị quá dài (tối đa 100 ký tự)")

    update_user_profile(user.id, display_name)
    return get_user_by_id(user.id)


@router.post("/api/auth/change-password")
async def change_password_endpoint(request: Request, user: AuthUser = Depends(get_current_user)):
    body = await request.json()
    old_password = body.get("old_password") or ""
    new_password = body.get("new_password") or ""

    errors = validate_password_change(old_password, new_password)
    if errors:
        raise HTTPException(status_code=400, detail={"error": errors[0], "errors": errors})

    try:
        change_password(user.id, old_password, new_password)
        revoke_user_tokens(user.id)
        return {"message": "Đổi mật khẩu thành công. Vui lòng đăng nhập lại."}
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Password change failed: %s", e)
        raise HTTPException(status_code=500, detail="Đổi mật khẩu thất bại")
