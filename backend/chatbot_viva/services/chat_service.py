"""
Chat Service — Orchestrates LLM streaming with context, profile, and tracing.

Single Responsibility: Build final prompt + stream LLM response.
Does NOT handle search, caching, or conversation persistence (see chat_orchestrator.py).
"""
from __future__ import annotations

import logging
from typing import Generator, List, Optional

from chatbot_viva.core import config
from chatbot_viva.core.tracing import create_trace_callback
from chatbot_viva.core.singleton import singleton
from chatbot_viva.conversation.context import ContextManager
from chatbot_viva.conversation.memory import UserProfileManager
from chatbot_viva.llm.factory import get_llm_factory
from chatbot_viva.processing.doc_utils import get_domain_name

logger = logging.getLogger(__name__)


@singleton
def _get_profile_manager() -> UserProfileManager:
    """Get or create profile manager singleton (thread-safe)."""
    return UserProfileManager()


@singleton
def _get_context_manager() -> ContextManager:
    """Get or create context manager singleton (thread-safe)."""
    return ContextManager(max_context_messages=config.MAX_CONTEXT_MESSAGES)


def stream_llm_response_plain(
    question: str,
    context: str,
    sources_info: list,
    conversation_messages: Optional[list] = None,
    is_legal_admin: bool = True,
    response_style: str = "general",
    conv_id: str = "",
    user_id: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    Generator that yields text chunks for Flask SSE streaming.

    Builds a complete prompt from:
      - User profile context (per-conversation preferences)
      - Conversation history context (topic, entities, summary)
      - Style-based prompt template (advice/legal/news_data/general)
      - Langfuse tracing (optional)

    Args:
        question: User's question.
        context: RAG context (vector + web combined).
        sources_info: Source references for the LLM prompt.
        conversation_messages: Full conversation history.
        is_legal_admin: Whether this is a legal/admin question.
        response_style: Prompt style from QueryAnalyzer.
        conv_id: Conversation ID for profile tracking.
        user_id: User ID for tracing.

    Yields:
        Text chunks from the LLM.
    """
    logger.info("Starting LLM streaming for: %s...", question[:50])
    factory = get_llm_factory()
    llm = factory.create(task="stream", streaming=True, request_timeout=120)

    long_term_context = _build_profile_context(question, conv_id)
    conversation_context_str = _build_conversation_context(question, conversation_messages)

    sources_ref = _build_sources_ref(sources_info, context)
    final_prompt = _assemble_prompt(
        response_style, question, context, sources_ref,
        long_term_context, conversation_context_str,
    )

    stream_kwargs = _build_stream_kwargs(response_style, conv_id, user_id)

    for chunk in llm.stream(final_prompt, **stream_kwargs):
        if chunk.content:
            yield chunk.content


def _build_profile_context(question: str, conv_id: str) -> str:
    """Extract user preferences and build profile context string."""
    profile_manager = _get_profile_manager()
    profile_manager.extract_preferences_from_text(question, conv_id=conv_id)
    return profile_manager.get_profile_context(conv_id=conv_id)


def _build_conversation_context(
    question: str,
    conversation_messages: Optional[list],
) -> str:
    """Build conversation context from message history."""
    if not conversation_messages:
        return ""

    cm = _get_context_manager()
    if not cm.should_use_context(conversation_messages):
        logger.debug("No conversation context (first message or short history)")
        return ""

    conv_ctx = cm.get_conversation_context(conversation_messages[:-1])
    logger.info("Using conversation context: topic=%s", conv_ctx.current_topic)
    return cm.build_context_prompt(question, conv_ctx)


def _assemble_prompt(
    response_style: str,
    question: str,
    context: str,
    sources_ref: str,
    long_term_context: str,
    conversation_context_str: str,
) -> str:
    """Assemble final prompt from all components."""
    from chatbot_viva.conversation.prompt_templates import build_style_prompt

    logger.info("Prompt style: %s", response_style.upper())
    base_prompt = build_style_prompt(response_style, question, context, sources_ref)

    if conversation_context_str:
        return f"{long_term_context}\n{conversation_context_str}\n\n{base_prompt}"
    return f"{long_term_context}\n\n{base_prompt}"


def _build_stream_kwargs(
    response_style: str,
    conv_id: str,
    user_id: Optional[str],
) -> dict:
    """Build kwargs for LLM.stream() with optional Langfuse tracing."""
    stream_kwargs: dict = {}
    trace_cb = create_trace_callback(
        trace_name="chat-stream",
        user_id=user_id,
        session_id=conv_id or None,
        metadata={"response_style": response_style},
        tags=["stream", response_style],
    )
    if trace_cb:
        stream_kwargs["config"] = {"callbacks": [trace_cb]}
    return stream_kwargs


def _build_sources_ref(sources_info: list, context: str) -> str:
    """
    Build sources reference string for the LLM prompt.

    Two formats:
    - Citation-aware: When context already contains numbered citations [1], [2]...
    - Full snippet: When sources need to be displayed with full text.

    Args:
        sources_info: List of source dicts.
        context: RAG context string (used to detect citation format).

    Returns:
        Formatted sources reference string.
    """
    if not sources_info:
        return "Không có nguồn dữ liệu cụ thể."

    has_citation_context = "=== NGUỒN THAM KHẢO" in context and "[1]" in context

    if has_citation_context:
        return _format_citation_aware_sources(sources_info)
    return _format_full_snippet_sources(sources_info)


def _format_citation_aware_sources(sources_info: list) -> str:
    """Format sources when citation context already exists."""
    lines = ["\n=== DANH SÁCH NGUỒN (ĐÃ CÓ NỘI DUNG CHI TIẾT Ở TRÊN) ==="]
    for i, src in enumerate(sources_info, 1):
        if src.get("type") == "web":
            url = src.get("url", "")
            domain = get_domain_name(url)
            lines.append(f"[{i}] [{domain}]({url})")
        else:
            title = src.get("title", "")
            lines.append(f"[{i}] Tài liệu - {title}")
    return "\n".join(lines)


def _format_full_snippet_sources(sources_info: list) -> str:
    """Format sources with full snippets for LLM reference."""
    lines = ["\n=== DANH SÁCH NGUỒN (SỬ DỤNG ĐỂ TRÍCH DẪN) ==="]
    for i, src in enumerate(sources_info, 1):
        if src.get("type") == "web":
            url = src.get("url", "")
            domain = get_domain_name(url)
            snippet = src.get("snippet", "")
            lines.append(f"\n### Nguồn {i}: [{domain}]({url})\n{snippet}")
        else:
            title = src.get("title", "")
            snippet = src.get("snippet", "")
            lines.append(f"\n### Nguồn {i}: Tài liệu - {title}\n{snippet}")
    return "\n".join(lines)
