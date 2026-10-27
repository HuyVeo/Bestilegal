"""Langfuse tracing integration for LLM observability (v4 API)."""

import logging
from typing import Optional

from chatbot_viva.core import config
from chatbot_viva.core.singleton import singleton

logger = logging.getLogger(__name__)


def _is_langfuse_configured() -> bool:
    """Check if Langfuse environment variables are set."""
    return bool(config.LANGFUSE_SECRET_KEY and config.LANGFUSE_PUBLIC_KEY)


@singleton
def get_langfuse_callback():
    """
    Get a Langfuse CallbackHandler for LangChain (thread-safe singleton).

    Returns None if Langfuse is not configured or import fails.
    """
    if not _is_langfuse_configured():
        logger.info("Langfuse not configured (missing LANGFUSE_SECRET_KEY or LANGFUSE_PUBLIC_KEY)")
        return None

    try:
        from langfuse.langchain import CallbackHandler

        handler = CallbackHandler()
        logger.info("Langfuse tracing enabled (host=%s)", config.LANGFUSE_HOST)
        return handler
    except ImportError:
        logger.warning("langfuse or langchain package not installed — tracing disabled")
        return None
    except Exception as e:
        logger.warning("Failed to initialize Langfuse: %s", e)
        return None


def create_trace_callback(
    trace_name: str = "llm-call",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list] = None,
):
    """
    Create a NEW Langfuse CallbackHandler for a specific trace.

    Use this when you want a dedicated trace per request (e.g., per chat message).
    Each call creates a fresh handler with its own trace context.

    Args:
        trace_name: Name for this trace (e.g., "chat-stream", "query-analyze").
        user_id: Optional user identifier.
        session_id: Optional session/conversation ID.
        metadata: Optional dict of extra metadata.
        tags: Optional list of tags.

    Returns:
        CallbackHandler or None if Langfuse is not available.
    """
    if not _is_langfuse_configured():
        return None

    try:
        from langfuse.langchain import CallbackHandler
        from langfuse.types import TraceContext

        trace_ctx = TraceContext(name=trace_name)
        if user_id:
            trace_ctx["user_id"] = user_id
        if session_id:
            trace_ctx["session_id"] = session_id
        if metadata:
            trace_ctx["metadata"] = metadata
        if tags:
            trace_ctx["tags"] = tags

        handler = CallbackHandler(trace_context=trace_ctx)
        return handler
    except ImportError:
        return None
    except Exception as e:
        logger.warning("Failed to create Langfuse trace callback: %s", e)
        return None


def flush_langfuse():
    """Flush any pending Langfuse events. Call on app shutdown."""
    try:
        import langfuse
        client = langfuse.get_client()
        if client:
            client.flush()
            logger.info("Langfuse events flushed")
    except Exception as e:
        logger.warning("Failed to flush Langfuse events: %s", e)
