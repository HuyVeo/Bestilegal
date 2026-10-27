"""User service — CRUD for user accounts."""

import datetime
import logging
from typing import Dict, List, Optional

import bcrypt

from chatbot_viva.core.db import get_db_pool
from chatbot_viva.core.exceptions import (
    DatabaseError,
    UserAlreadyExistsError,
    InvalidCredentialsError,
)

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def _serialize_dt(dt):
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _row_to_user(row, cols) -> Dict:
    """Convert a DB row to a user dict (without password_hash)."""
    d = dict(zip(cols, row))
    d.pop("password_hash", None)
    d["id"] = str(d["id"])
    d["created_at"] = _serialize_dt(d["created_at"])
    d["updated_at"] = _serialize_dt(d["updated_at"])
    return d


def create_user(email: str, password: str, display_name: str = "", role: str = "user") -> Dict:
    """Create a new user. Returns user dict (no password_hash)."""
    password_h = hash_password(password)
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            cur = conn.execute(
                """INSERT INTO users (email, password_hash, display_name, role)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id, email, display_name, role, created_at, updated_at, is_active""",
                [email.lower().strip(), password_h, display_name.strip(), role],
            )
            row = cur.fetchone()
            cols = [desc.name for desc in cur.description]
            conn.commit()
        logger.info("Created user: %s", email)
        return _row_to_user(row, cols)
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise UserAlreadyExistsError(f"Email đã được sử dụng: {email}") from e
        logger.error("Failed to create user: %s", e)
        raise DatabaseError(f"Failed to create user: {e}") from e


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email (includes password_hash for auth)."""
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            cur = conn.execute(
                "SELECT id, email, password_hash, display_name, role, created_at, updated_at, is_active "
                "FROM users WHERE email = %s AND is_active = TRUE",
                [email.lower().strip()],
            )
            row = cur.fetchone()
            if row is None:
                return None
            cols = [desc.name for desc in cur.description]
        d = dict(zip(cols, row))
        d["id"] = str(d["id"])
        d["created_at"] = _serialize_dt(d["created_at"])
        d["updated_at"] = _serialize_dt(d["updated_at"])
        return d
    except Exception as e:
        logger.error("Failed to get user by email: %s", e)
        raise DatabaseError(f"Failed to get user: {e}") from e


def get_user_by_id(user_id: str) -> Optional[Dict]:
    """Get user by ID (no password_hash)."""
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            cur = conn.execute(
                "SELECT id, email, display_name, role, created_at, updated_at, is_active "
                "FROM users WHERE id = %s::uuid AND is_active = TRUE",
                [user_id],
            )
            row = cur.fetchone()
            if row is None:
                return None
            cols = [desc.name for desc in cur.description]
        return _row_to_user(row, cols)
    except Exception as e:
        logger.error("Failed to get user by id: %s", e)
        raise DatabaseError(f"Failed to get user: {e}") from e


def update_user_profile(user_id: str, display_name: str = None) -> bool:
    """Update user profile. Returns True if found and updated."""
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            cur = conn.execute(
                "UPDATE users SET display_name = %s, updated_at = %s WHERE id = %s::uuid AND is_active = TRUE",
                [display_name.strip(), datetime.datetime.now(datetime.timezone.utc), user_id],
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error("Failed to update user profile: %s", e)
        raise DatabaseError(f"Failed to update profile: {e}") from e


def change_password(user_id: str, old_password: str, new_password: str) -> bool:
    """Change user password. Verifies old password first."""
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            cur = conn.execute(
                "SELECT password_hash FROM users WHERE id = %s::uuid AND is_active = TRUE",
                [user_id],
            )
            row = cur.fetchone()
            if row is None:
                return False
            if not verify_password(old_password, row[0]):
                raise InvalidCredentialsError("Mật khẩu cũ không đúng")
            new_hash = hash_password(new_password)
            conn.execute(
                "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s::uuid",
                [new_hash, datetime.datetime.now(datetime.timezone.utc), user_id],
            )
            conn.commit()
        logger.info("Password changed for user: %s", user_id)
        return True
    except InvalidCredentialsError:
        raise
    except Exception as e:
        logger.error("Failed to change password: %s", e)
        raise DatabaseError(f"Failed to change password: {e}") from e


def list_users(page: int = 1, per_page: int = 50) -> List[Dict]:
    """List all users (admin). Returns list of user dicts."""
    try:
        pool = get_db_pool()
        offset = (page - 1) * per_page
        with pool.connection() as conn:
            cur = conn.execute(
                "SELECT id, email, display_name, role, created_at, updated_at, is_active "
                "FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s",
                [per_page, offset],
            )
            rows = cur.fetchall()
            cols = [desc.name for desc in cur.description]
        return [_row_to_user(row, cols) for row in rows]
    except Exception as e:
        logger.error("Failed to list users: %s", e)
        raise DatabaseError(f"Failed to list users: {e}") from e


def set_user_role(user_id: str, role: str) -> bool:
    """Set user role (admin only). Returns True if found and updated."""
    if role not in ("user", "admin"):
        return False
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            cur = conn.execute(
                "UPDATE users SET role = %s, updated_at = %s WHERE id = %s::uuid",
                [role, datetime.datetime.now(datetime.timezone.utc), user_id],
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error("Failed to set user role: %s", e)
        raise DatabaseError(f"Failed to set role: {e}") from e


def deactivate_user(user_id: str) -> bool:
    """Deactivate a user account. Returns True if found."""
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            cur = conn.execute(
                "UPDATE users SET is_active = FALSE, updated_at = %s WHERE id = %s::uuid",
                [datetime.datetime.now(datetime.timezone.utc), user_id],
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error("Failed to deactivate user: %s", e)
        raise DatabaseError(f"Failed to deactivate user: {e}") from e
