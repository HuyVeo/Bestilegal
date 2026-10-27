"""Security facade — re-exports for backward compatibility.

Auth and rate limiting are now in core/dependencies.py (FastAPI Depends).
This module re-exports validation utilities.
"""
from __future__ import annotations

from chatbot_viva.core.validation import validate_chat_input, validate_conv_id
from chatbot_viva.core.rate_limit import RateLimiter

__all__ = [
    "validate_chat_input",
    "validate_conv_id",
    "RateLimiter",
]
