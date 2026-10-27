"""
User Profile Manager — Per-conversation preference tracking.

Single Responsibility: Track user preferences within a single conversation.
In-memory only, resets each new conversation.
"""
from __future__ import annotations

from typing import Dict, List


# ── Preference detection patterns ──
_PREFERENCE_PATTERNS: List[Dict[str, str]] = [
    {"keywords": ["tài chính", "ngân sách"], "key": "budget_concern", "value": "User quan tâm về giá/tài chính"},
    {"keywords": ["chung cư"], "key": "property_type", "value": "Chung cư"},
    {"keywords": ["đầu tư"], "key": "goal", "value": "Đầu tư"},
]


class UserProfileManager:
    """
    Per-conversation user profile — in-memory only, resets each new conversation.
    Tracks preferences mentioned within the CURRENT conversation.

    Thread-safe: each conv_id has its own dict, no shared mutable state.
    """

    def __init__(self, profile_path: str = "") -> None:
        """
        Args:
            profile_path: Deprecated, kept for backward compat. Not used.
        """
        self._profiles: Dict[str, Dict[str, str]] = {}

    def extract_preferences_from_text(self, text: str, conv_id: str = "") -> None:
        """
        Extract preferences from current message within this conversation.

        Args:
            text: User message text.
            conv_id: Conversation ID. No-op if empty.
        """
        if not conv_id:
            return

        prefs = self._profiles.setdefault(conv_id, {})
        text_lower = text.lower()

        for pattern in _PREFERENCE_PATTERNS:
            if any(kw in text_lower for kw in pattern["keywords"]):
                prefs[pattern["key"]] = pattern["value"]

    def get_profile_context(self, conv_id: str = "") -> str:
        """
        Build context string from current conversation's profile.

        Args:
            conv_id: Conversation ID.

        Returns:
            Formatted profile context, or empty string if no prefs.
        """
        if not conv_id:
            return ""

        prefs = self._profiles.get(conv_id, {})
        if not prefs:
            return ""

        lines = [
            "\n=== HỒ SƠ NGƯỜI DÙNG (CUỘC TRÒ CHUYỆN NÀY) ===",
            "Thông tin đã biết về người dùng trong cuộc trò chuyện này:",
        ]
        for k, v in prefs.items():
            lines.append(f"- {k}: {v}")

        return "\n".join(lines)

    def clear_conversation(self, conv_id: str) -> None:
        """Clear profile when conversation ends or resets."""
        self._profiles.pop(conv_id, None)


def get_profile_manager() -> UserProfileManager:
    """Get or create profile manager instance."""
    return UserProfileManager()
