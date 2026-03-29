"""Share service — conversation sharing via public links."""

import logging
import uuid
from typing import Dict, List, Optional

from chatbot_viva.core.db import get_db_pool
from chatbot_viva.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


def _serialize_dt(dt):
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def create_share_link(conv_id: str, user_id: str, expires_hours: int = None) -> Dict:
    """Create a share link for a conversation. Returns share record."""
    share_token = uuid.uuid4().hex[:16]  # 16-char hex token

    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            # Verify the conversation belongs to this user
            cur = conn.execute(
                "SELECT id FROM conversations WHERE id = %s AND user_id = %s::uuid",
                [conv_id, user_id],
            )
            if cur.fetchone() is None:
                return None

            expires_at = None
            if expires_hours:
                from datetime import datetime, timedelta, timezone
                expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

            cur = conn.execute(
                """INSERT INTO shared_conversations (conv_id, share_token, created_by, expires_at)
                   VALUES (%s, %s, %s::uuid, %s)
                   RETURNING id, conv_id, share_token, created_at, expires_at, is_active""",
                [conv_id, share_token, user_id, expires_at],
            )
            row = cur.fetchone()
            cols = [desc.name for desc in cur.description]
            conn.commit()

        d = dict(zip(cols, row))
        d["id"] = str(d["id"])
        d["created_at"] = _serialize_dt(d["created_at"])
        d["expires_at"] = _serialize_dt(d["expires_at"]) if d["expires_at"] else None
        return d
    except Exception as e:
        logger.error("Failed to create share link: %s", e)
        raise DatabaseError(f"Failed to create share link: {e}") from e


def get_shared_conversation(share_token: str) -> Optional[Dict]:
    """Get a shared conversation by token. Returns conversation data or None."""
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            cur = conn.execute(
                """SELECT c.id, c.title, c.created_at, c.updated_at, c.messages,
                          sc.expires_at, sc.is_active
                   FROM shared_conversations sc
                   JOIN conversations c ON c.id = sc.conv_id
                   WHERE sc.share_token = %s AND sc.is_active = TRUE""",
                [share_token],
            )
            row = cur.fetchone()
            if row is None:
                return None
            cols = [desc.name for desc in cur.description]

        d = dict(zip(cols, row))
        # Check expiration
        if d["expires_at"] is not None:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            if d["expires_at"].tzinfo is None:
                from datetime import timezone as tz
                d["expires_at"] = d["expires_at"].replace(tzinfo=tz.utc)
            if d["expires_at"] < now:
                return None

        d["created_at"] = _serialize_dt(d["created_at"])
        d["updated_at"] = _serialize_dt(d["updated_at"])
        d.pop("expires_at", None)
        d.pop("is_active", None)
        return d
    except Exception as e:
        logger.error("Failed to get shared conversation: %s", e)
        raise DatabaseError(f"Failed to get shared conversation: {e}") from e


def revoke_share_link(share_id: str, user_id: str) -> bool:
    """Revoke a share link. Returns True if found and revoked."""
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            cur = conn.execute(
                "UPDATE shared_conversations SET is_active = FALSE "
                "WHERE id = %s::uuid AND created_by = %s::uuid",
                [share_id, user_id],
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error("Failed to revoke share link: %s", e)
        raise DatabaseError(f"Failed to revoke share link: {e}") from e


def list_share_links(conv_id: str, user_id: str) -> List[Dict]:
    """List all share links for a conversation."""
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            cur = conn.execute(
                """SELECT id, conv_id, share_token, created_at, expires_at, is_active
                   FROM shared_conversations
                   WHERE conv_id = %s AND created_by = %s::uuid
                   ORDER BY created_at DESC""",
                [conv_id, user_id],
            )
            rows = cur.fetchall()
            cols = [desc.name for desc in cur.description]
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            d["id"] = str(d["id"])
            d["created_at"] = _serialize_dt(d["created_at"])
            d["expires_at"] = _serialize_dt(d["expires_at"]) if d["expires_at"] else None
            result.append(d)
        return result
    except Exception as e:
        logger.error("Failed to list share links: %s", e)
        raise DatabaseError(f"Failed to list share links: {e}") from e
