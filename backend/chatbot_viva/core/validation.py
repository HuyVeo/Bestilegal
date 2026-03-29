"""Input validation for chat and auth endpoints."""

import re
from typing import List, Optional

from chatbot_viva.core import config

CONV_ID_PATTERN = re.compile(r"^\d{8}_\d{6}(_[a-f0-9]{6})?$")


def validate_chat_input(question: str, conv_id: Optional[str]) -> List[str]:
    """Validate chat endpoint input. Returns list of error messages."""
    errors = []

    if not question or not question.strip():
        errors.append("question is required")

    if len(question) > config.MAX_QUESTION_LENGTH:
        errors.append(
            f"question too long ({len(question)} chars, max {config.MAX_QUESTION_LENGTH})"
        )

    if conv_id is not None and conv_id:
        if not validate_conv_id(conv_id):
            errors.append(f"invalid conv_id format: {conv_id!r}")

    return errors


def validate_conv_id(conv_id: str) -> bool:
    """Validate conversation ID format (YYYYMMDD_HHMMSS or YYYYMMDD_HHMMSS_hexsuffix)."""
    if not conv_id:
        return True
    return bool(CONV_ID_PATTERN.match(conv_id))


def validate_registration(email: str, password: str, display_name: str = "") -> List[str]:
    """Validate registration input. Returns list of Vietnamese error messages."""
    errors = []

    # Email validation
    if not email or not email.strip():
        errors.append("Email là bắt buộc")
    else:
        try:
            from email_validator import validate_email, EmailNotValidError
            validate_email(email.strip(), check_deliverability=False)
        except (EmailNotValidError, ImportError):
            errors.append("Email không hợp lệ")

    # Password validation
    if not password:
        errors.append("Mật khẩu là bắt buộc")
    else:
        if len(password) < config.PASSWORD_MIN_LENGTH:
            errors.append(f"Mật khẩu phải có ít nhất {config.PASSWORD_MIN_LENGTH} ký tự")
        if not re.search(r"[A-Za-z]", password):
            errors.append("Mật khẩu phải có ít nhất một chữ cái")
        if not re.search(r"[0-9]", password):
            errors.append("Mật khẩu phải có ít nhất một chữ số")

    # Display name
    if display_name and len(display_name) > 100:
        errors.append("Tên hiển thị quá dài (tối đa 100 ký tự)")

    return errors


def validate_login(email: str, password: str) -> List[str]:
    """Validate login input."""
    errors = []
    if not email or not email.strip():
        errors.append("Email là bắt buộc")
    if not password:
        errors.append("Mật khẩu là bắt buộc")
    return errors


def validate_password_change(old_password: str, new_password: str) -> List[str]:
    """Validate password change input."""
    errors = []
    if not old_password:
        errors.append("Mật khẩu cũ là bắt buộc")
    if not new_password:
        errors.append("Mật khẩu mới là bắt buộc")
    elif len(new_password) < config.PASSWORD_MIN_LENGTH:
        errors.append(f"Mật khẩu mới phải có ít nhất {config.PASSWORD_MIN_LENGTH} ký tự")
    elif not re.search(r"[A-Za-z]", new_password):
        errors.append("Mật khẩu mới phải có ít nhất một chữ cái")
    elif not re.search(r"[0-9]", new_password):
        errors.append("Mật khẩu mới phải có ít nhất một chữ số")
    if old_password and new_password and old_password == new_password:
        errors.append("Mật khẩu mới phải khác mật khẩu cũ")
    return errors
