"""Conversation service — CRUD for conversation history via PostgreSQL."""

import datetime
import json
import logging
import re
import uuid
from typing import List, Dict, Optional

from chatbot_viva.core.db import get_db_pool
from chatbot_viva.core.exceptions import DatabaseError, ConversationNotFoundError

logger = logging.getLogger(__name__)


class ConversationTitleGenerator:
    """Generate conversation titles from message content."""

    TOPIC_PATTERNS = {
        r'(chuyển nhượng|sang tên|bán đất|mua đất)': 'Chuyển nhượng bất động sản',
        r'(thủ tục|hồ sơ|giấy tờ|đăng ký|làm sao)': 'Thủ tục hành chính',
        r'(thuế|lệ phí|chi phí|tiền|phí|giá)': 'Chi phí và thuế phí',
        r'(tranh chấp|kiện|vi phạm|tòa án|luật sư)': 'Tranh chấp pháp lý',
        r'(định giá|thẩm định|giá trị|bao nhiêu)': 'Định giá bất động sản',
        r'(chung cư|căn hộ|condotel|officetel)': 'Chung cư và căn hộ',
        r'(quy hoạch|xây dựng|phép|giấy phép)': 'Quy hoạch xây dựng',
        r'(sổ đỏ|giấy chứng nhận|sổ hồng)': 'Giấy tờ sở hữu',
        r'(vay vốn|ngân hàng|tín dụng|vay)': 'Vay vốn mua nhà',
        r'(hợp đồng|ký kết|thỏa thuận)': 'Hợp đồng mua bán',
        r'(nhà ở|nhà riêng|biệt thự)': 'Nhà ở riêng lẻ',
        r'(đất nông nghiệp|đất trồng trọt)': 'Đất nông nghiệp',
        r'(đất thổ cư|đất ở|đất xây)': 'Đất thổ cư',
        r'(công chứng|chứng thực)': 'Công chứng giao dịch',
        r'(kế thừa|thừa kế|di sản)': 'Kế thừa bất động sản',
    }

    _compiled = [(re.compile(p, re.IGNORECASE), t) for p, t in TOPIC_PATTERNS.items()]

    @staticmethod
    def generate(messages: List[Dict]) -> str:
        if not messages:
            return f"Cuộc trò chuyện {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
        first_user = next((m['content'] for m in messages if m['role'] == 'user'), "")
        if not first_user:
            return f"Cuộc trò chuyện {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
        lower = first_user.lower()
        for pattern, title in ConversationTitleGenerator._compiled:
            if pattern.search(lower):
                return title
        clean = re.sub(r'[^\w\s]', '', first_user)
        stop = {
            'là', 'gì', 'như', 'thế', 'nào', 'có', 'được',
            'không', 'tôi', 'mình', 'em', 'anh', 'chị'}
        words = [w for w in clean.split()[:8] if w.lower() not in stop and len(w) > 2]
        if words:
            return ' '.join(words[:4]).title()
        return (first_user[:50] + "...") if len(first_user) > 50 else first_user


def _serialize_dt(dt):
    """Serialize datetime for JSON response."""
    if hasattr(dt, 'isoformat'):
        return dt.isoformat()
    return str(dt)


def list_conversations(page: int = 1, per_page: int = 50, user_id: Optional[str] = None) -> List[Dict]:
    """List conversations with pagination, ordered by most recent.
    If user_id is provided, only return that user's conversations."""
    try:
        pool = get_db_pool()
        offset = (page - 1) * per_page
        if user_id:
            query = (
                "SELECT id, title, created_at, updated_at, message_count "
                "FROM conversations WHERE user_id = %s::uuid ORDER BY updated_at DESC LIMIT %s OFFSET %s"
            )
            params = [user_id, per_page, offset]
        else:
            query = (
                "SELECT id, title, created_at, updated_at, message_count "
                "FROM conversations ORDER BY updated_at DESC LIMIT %s OFFSET %s"
            )
            params = [per_page, offset]
        with pool.connection() as conn:
            cur = conn.execute(query, params)
            rows = cur.fetchall()
            cols = [desc.name for desc in cur.description]
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            d["created_at"] = _serialize_dt(d["created_at"])
            d["updated_at"] = _serialize_dt(d["updated_at"])
            result.append(d)
        return result
    except Exception as e:
        logger.error("Failed to list conversations: %s", e)
        raise DatabaseError(f"Failed to list conversations: {e}") from e


def get_conversation(conv_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
    """Get a single conversation by ID. If user_id provided, enforce ownership."""
    try:
        pool = get_db_pool()
        if user_id:
            query = (
                "SELECT id, title, created_at, updated_at, message_count, messages "
                "FROM conversations WHERE id = %s AND user_id = %s::uuid"
            )
            params = [conv_id, user_id]
        else:
            query = (
                "SELECT id, title, created_at, updated_at, message_count, messages "
                "FROM conversations WHERE id = %s"
            )
            params = [conv_id]
        with pool.connection() as conn:
            cur = conn.execute(query, params)
            row = cur.fetchone()
            if row is None:
                return None
            cols = [desc.name for desc in cur.description]
        d = dict(zip(cols, row))
        d["created_at"] = _serialize_dt(d["created_at"])
        d["updated_at"] = _serialize_dt(d["updated_at"])
        return d
    except Exception as e:
        logger.error("Failed to get conversation %s: %s", conv_id, e)
        raise DatabaseError(f"Failed to get conversation: {e}") from e


def save_conversation(conv_id: Optional[str], messages: List[Dict], user_id: Optional[str] = None) -> str:
    """Save or update a conversation. Returns the conversation ID."""
    now = datetime.datetime.now()

    if not conv_id:
        conv_id = now.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]

    title = ConversationTitleGenerator.generate(messages)
    msg_count = sum(1 for m in messages if m.get('role') == 'user')
    messages_json = json.dumps(messages, ensure_ascii=False)

    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            conn.execute("""
                INSERT INTO conversations (id, title, created_at, updated_at, message_count, messages, user_id)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::uuid)
                ON CONFLICT (id) DO UPDATE SET
                    messages = EXCLUDED.messages,
                    message_count = EXCLUDED.message_count,
                    updated_at = EXCLUDED.updated_at,
                    title = CASE
                        WHEN conversations.title LIKE 'Cuộc trò chuyện%%'
                             OR length(conversations.title) < 20
                        THEN EXCLUDED.title
                        ELSE conversations.title
                    END
            """, [conv_id, title, now, now, msg_count, messages_json, user_id])
            conn.commit()
        logger.debug("Saved conversation %s (%d messages)", conv_id, msg_count)
        return conv_id
    except Exception as e:
        logger.error("Failed to save conversation %s: %s", conv_id, e)
        raise DatabaseError(f"Failed to save conversation: {e}") from e


def rename_conversation(conv_id: str, new_title: str, user_id: Optional[str] = None) -> bool:
    """Rename a conversation. Returns True if found and renamed."""
    try:
        pool = get_db_pool()
        if user_id:
            query = "UPDATE conversations SET title = %s, updated_at = %s WHERE id = %s AND user_id = %s::uuid"
            params = [new_title, datetime.datetime.now(), conv_id, user_id]
        else:
            query = "UPDATE conversations SET title = %s, updated_at = %s WHERE id = %s"
            params = [new_title, datetime.datetime.now(), conv_id]
        with pool.connection() as conn:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error("Failed to rename conversation %s: %s", conv_id, e)
        raise DatabaseError(f"Failed to rename conversation: {e}") from e


def delete_conversation(conv_id: str, user_id: Optional[str] = None) -> bool:
    """Delete a conversation. Returns True if found and deleted."""
    try:
        pool = get_db_pool()
        if user_id:
            query = "DELETE FROM conversations WHERE id = %s AND user_id = %s::uuid"
            params = [conv_id, user_id]
        else:
            query = "DELETE FROM conversations WHERE id = %s"
            params = [conv_id]
        with pool.connection() as conn:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error("Failed to delete conversation %s: %s", conv_id, e)
        raise DatabaseError(f"Failed to delete conversation: {e}") from e
