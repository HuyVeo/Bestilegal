"""Token service — JWT access tokens and refresh token lifecycle."""

import datetime
import hashlib
import logging
import uuid
from typing import Optional, Tuple

import jwt

from chatbot_viva.core import config
from chatbot_viva.core.db import get_db_pool
from chatbot_viva.core.exceptions import TokenError

logger = logging.getLogger(__name__)


def _hash_token(token: str) -> str:
    """SHA-256 hash of a refresh token for DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: str, email: str, role: str = "user") -> str:
    """Create a short-lived JWT access token."""
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + datetime.timedelta(seconds=config.JWT_ACCESS_TOKEN_EXPIRES),
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def verify_access_token(token: str) -> Optional[dict]:
    """Decode and verify JWT access token. Returns payload or None."""
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Access token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid access token: %s", e)
        return None


def create_refresh_token(user_id: str) -> str:
    """Create a refresh token, store hash in DB, return raw token."""
    raw_token = uuid.uuid4().hex + uuid.uuid4().hex  # 64-char hex
    token_hash = _hash_token(raw_token)
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=config.JWT_REFRESH_TOKEN_EXPIRES
    )

    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            conn.execute(
                """INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                   VALUES (%s::uuid, %s, %s)""",
                [user_id, token_hash, expires_at],
            )
            conn.commit()
        return raw_token
    except Exception as e:
        logger.error("Failed to create refresh token: %s", e)
        raise TokenError(f"Failed to create refresh token: {e}") from e


def rotate_refresh_token(old_token: str) -> Optional[Tuple[str, str]]:
    """Validate old refresh token, revoke it, issue new access + refresh pair.
    Returns (new_access_token, new_refresh_token) or None if invalid."""
    old_hash = _hash_token(old_token)
    now = datetime.datetime.now(datetime.timezone.utc)

    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            # Look up the refresh token
            cur = conn.execute(
                """SELECT rt.id, rt.user_id, rt.expires_at, rt.revoked,
                          u.email, u.role, u.is_active
                   FROM refresh_tokens rt
                   JOIN users u ON u.id = rt.user_id
                   WHERE rt.token_hash = %s""",
                [old_hash],
            )
            row = cur.fetchone()
            if row is None:
                logger.warning("Refresh token not found")
                return None

            rt_id, user_id, expires_at, revoked, email, role, is_active = row
            user_id = str(user_id)

            if revoked:
                logger.warning("Attempted reuse of revoked refresh token for user %s", user_id)
                # Potential token theft — revoke all tokens for this user
                conn.execute(
                    "UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = %s::uuid",
                    [user_id],
                )
                conn.commit()
                return None

            if expires_at < now:
                logger.debug("Refresh token expired")
                return None

            if not is_active:
                logger.warning("Refresh token for deactivated user %s", user_id)
                return None

            # Revoke old token
            conn.execute(
                "UPDATE refresh_tokens SET revoked = TRUE WHERE id = %s",
                [rt_id],
            )
            conn.commit()

        # Issue new pair
        new_access = create_access_token(user_id, email, role)
        new_refresh = create_refresh_token(user_id)
        return new_access, new_refresh

    except TokenError:
        raise
    except Exception as e:
        logger.error("Failed to rotate refresh token: %s", e)
        return None


def revoke_refresh_token(token: str) -> None:
    """Revoke a single refresh token."""
    token_hash = _hash_token(token)
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            conn.execute(
                "UPDATE refresh_tokens SET revoked = TRUE WHERE token_hash = %s",
                [token_hash],
            )
            conn.commit()
    except Exception as e:
        logger.error("Failed to revoke refresh token: %s", e)


def revoke_user_tokens(user_id: str) -> None:
    """Revoke all refresh tokens for a user (logout everywhere)."""
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            conn.execute(
                "UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = %s::uuid AND revoked = FALSE",
                [user_id],
            )
            conn.commit()
        logger.info("Revoked all tokens for user %s", user_id)
    except Exception as e:
        logger.error("Failed to revoke user tokens: %s", e)


def cleanup_expired_tokens() -> int:
    """Delete expired and revoked tokens. Returns count deleted."""
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            cur = conn.execute(
                "DELETE FROM refresh_tokens WHERE revoked = TRUE OR expires_at < NOW()"
            )
            conn.commit()
            return cur.rowcount
    except Exception as e:
        logger.error("Failed to cleanup tokens: %s", e)
        return 0
