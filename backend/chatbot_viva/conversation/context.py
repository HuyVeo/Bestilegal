"""
Context Management — Maintains conversation history and builds context prompts.

Single Responsibility: Extract context from message history, build context-aware prompts.
Does NOT do classification (see question_classifier.py) or profile tracking (see memory.py).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Topic detection patterns (shared across conversation analysis) ──
_TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "chuyển nhượng": ["chuyển nhượng", "sang tên", "bán đất", "mua đất"],
    "thủ tục hành chính": ["thủ tục", "hồ sơ", "giấy tờ", "đăng ký"],
    "thuế và lệ phí": ["thuế", "lệ phí", "chi phí", "phí"],
    "tranh chấp": ["tranh chấp", "kiện tụng", "vi phạm", "tòa án"],
    "định giá": ["giá", "định giá", "thẩm định"],
    "chung cư": ["chung cư", "căn hộ", "condotel", "officetel"],
    "quy hoạch": ["quy hoạch", "xây dựng", "phép xây", "giấy phép"],
}

_ENTITY_KEYWORDS: List[str] = [
    "chuyển nhượng", "sổ đỏ", "giấy chứng nhận", "đất đai",
    "bất động sản", "mua bán", "thuế", "lệ phí", "thủ tục",
    "hồ sơ", "công chứng", "chung cư", "nhà ở", "đất nông nghiệp",
    "đất thổ cư", "quy hoạch", "giá đất", "định giá", "thẩm định",
    "ngân hàng", "vay vốn", "hợp đồng", "vi bằng", "tranh chấp",
    "tòa án", "luật sư",
]

_MAX_ENTITIES = 10
_MAX_RECENT_PAIRS = 3


@dataclass
class ConversationContext:
    """Immutable snapshot of conversation context at a point in time."""

    messages: List[Dict]
    current_topic: Optional[str] = None
    key_entities: List[str] = field(default_factory=list)
    conversation_summary: Optional[str] = None


class ContextManager:
    """
    Extracts and manages conversation context for building context-aware prompts.

    Responsibilities:
      - Extract key entities from conversation history
      - Identify current topic
      - Generate conversation summary
      - Build context prompt string for LLM
    """

    def __init__(self, max_context_messages: int = 10) -> None:
        logger.info("Context manager initializing (max_messages=%d)", max_context_messages)
        self.max_context_messages = max_context_messages

    def get_conversation_context(self, messages: List[Dict]) -> ConversationContext:
        """
        Extract and build conversation context from message history.

        Args:
            messages: Full conversation message list.

        Returns:
            ConversationContext with topic, entities, and summary.
        """
        if not messages:
            return ConversationContext(messages=[])

        recent = messages[-self.max_context_messages:]
        return ConversationContext(
            messages=recent,
            current_topic=_identify_topic(recent),
            key_entities=_extract_entities(recent),
            conversation_summary=_generate_summary(recent),
        )

    def build_context_prompt(
        self,
        current_question: str,
        context: ConversationContext,
    ) -> str:
        """
        Build context-aware prompt section for the LLM.

        Args:
            current_question: The current user question.
            context: ConversationContext from get_conversation_context().

        Returns:
            Formatted context prompt string, or empty string if not enough history.
        """
        if not context.messages or len(context.messages) <= 1:
            return ""

        parts: List[str] = ["\n=== BỐI CẢNH CUỘC TRÒ CHUYỆN ==="]

        if context.conversation_summary:
            parts.append(f"Tóm tắt: {context.conversation_summary}")
        if context.current_topic:
            parts.append(f"Chủ đề hiện tại: {context.current_topic}")
        if context.key_entities:
            parts.append(f"Các khái niệm đã thảo luận: {', '.join(context.key_entities[:5])}")

        parts.append("\nCác câu hỏi gần đây:")
        parts.extend(_format_recent_pairs(context.messages))

        parts.append(f"\n=== CÂU HỎI HIỆN TẠI ===\n{current_question}")
        parts.append(
            "\nQUAN TRỌNG: Người dùng đã cung cấp thông tin ở các câu trước. "
            "KHÔNG hỏi lại những gì đã biết. "
            "Sử dụng trực tiếp thông tin đã có để trả lời."
        )

        return "\n".join(parts)

    def should_use_context(self, messages: List[Dict]) -> bool:
        """Determine if context should be used (need at least 2 messages)."""
        return len(messages) >= 2


# ── Private helper functions (extracted for SRP) ──

def _extract_entities(messages: List[Dict]) -> List[str]:
    """Extract key real-estate entities mentioned in conversation."""
    entities: set = set()
    for message in messages:
        content = str(message.get("content", "")).lower()
        for keyword in _ENTITY_KEYWORDS:
            if keyword in content:
                entities.add(keyword)
    return list(entities)[:_MAX_ENTITIES]


def _identify_topic(messages: List[Dict]) -> Optional[str]:
    """Identify current conversation topic from recent user messages."""
    if not messages:
        return None

    recent_user_messages = [
        str(msg.get("content", "")).lower()
        for msg in messages[-5:]
        if msg.get("role") == "user"
    ]
    recent_text = " ".join(recent_user_messages)

    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in recent_text for kw in keywords):
            return topic

    return "bất động sản chung"


def _generate_summary(messages: List[Dict]) -> Optional[str]:
    """Generate brief conversation summary from user questions."""
    if len(messages) <= 1:
        return None

    user_questions = [
        msg.get("content", "")
        for msg in messages
        if msg.get("role") == "user"
    ]
    if not user_questions:
        return None

    count = len(user_questions)
    if count == 1:
        return f"Người dùng đã hỏi về: {user_questions[0][:100]}..."
    elif count <= 3:
        return f"Người dùng đã hỏi {count} câu về bất động sản"
    return f"Cuộc trò chuyện dài với {count} câu hỏi về các vấn đề bất động sản khác nhau"


def _format_recent_pairs(messages: List[Dict]) -> List[str]:
    """Format recent Q&A pairs for context prompt."""
    recent_pairs: List[Dict[str, str]] = []

    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") == "user" and len(recent_pairs) < _MAX_RECENT_PAIRS:
            assistant_response = ""
            if i + 1 < len(messages) and messages[i + 1].get("role") == "assistant":
                assistant_response = str(messages[i + 1].get("content", ""))[:800] + "..."

            recent_pairs.append({
                "question": msg.get("content", ""),
                "response": assistant_response,
            })

    lines: List[str] = []
    for i, pair in enumerate(reversed(recent_pairs)):
        lines.append(f"\nCâu {i + 1}. {pair['question']}")
        if pair["response"]:
            lines.append(f"Trả lời: {pair['response']}")

    return lines


def get_context_manager() -> ContextManager:
    """Get or create context manager instance."""
    return ContextManager(max_context_messages=10)
