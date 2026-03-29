"""Chat orchestrator — coordinates the full chat pipeline.

Extracted from api/main.py to separate business logic from HTTP handling.
"""

import json
import logging
import time
import concurrent.futures
from typing import Dict, Generator, List, Optional, Tuple

from chatbot_viva.core import config
from chatbot_viva.core.cache import get_response_cache
from chatbot_viva.core.constants import SUGGESTED_QUESTIONS
from chatbot_viva.conversation.query_analyzer import get_query_analyzer
from chatbot_viva.conversation.suggestions import generate_suggested_questions
from chatbot_viva.llm.factory import get_llm_factory
from chatbot_viva.retrieval.vector_store import get_retriever
from chatbot_viva.services.chat_service import stream_llm_response_plain
from chatbot_viva.services.conversation_service import save_conversation
from chatbot_viva.services.rag_service import (
    rag_search, build_rag_context, extract_refs_from_response,
)
from chatbot_viva.tools.legal_article_crawler import enrich_legal_basis
from chatbot_viva.tools.legal_web_search import legal_web_search, postprocess_citations
from chatbot_viva.tools.stock_price import get_stock_context
from chatbot_viva.core.logging_config import get_request_id, set_request_id

logger = logging.getLogger(__name__)


def run_chat_pipeline(
    question: str,
    messages: List[Dict],
    conv_id: Optional[str],
    user_id: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    Full chat pipeline. Yields SSE data strings.
    Replaces the monolithic generate() function in main.py.
    """
    t_start = time.perf_counter()

    def _elapsed(since=None):
        return f"{time.perf_counter() - (since or t_start):.2f}s"

    warnings = []  # Collect non-fatal issues to report to frontend

    try:
        # ── Step 1: Query Analysis
        t0 = time.perf_counter()
        factory = get_llm_factory()
        llm_rw = factory.create(task="rewrite", request_timeout=30)
        analyzer = get_query_analyzer()
        analysis = analyzer.analyze(
            question, messages[:-1] if len(messages) > 1 else [], llm_rw)
        logger.info("Query analysis: action=%s in %s", analysis.action, _elapsed(t0))

        # ── Step 2: Handle non-search actions
        if analysis.action in ("greeting", "clarify"):
            response_text = (
                analysis.greeting_response if analysis.action == "greeting"
                else analysis.clarify_question
            )
            yield _sse_data("chunk", response_text)
            try:
                conv_id = save_conversation(conv_id, messages + [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": response_text, "sources": []},
                ], user_id=user_id)
            except Exception as e:
                logger.error("Failed to save conversation: %s", e)
                warnings.append("Không thể lưu lịch sử hội thoại")
            yield _sse_data("done", None, conv_id=conv_id,
                            sources=[], suggestions=SUGGESTED_QUESTIONS[:3],
                            warnings=warnings)
            return

        # ── Step 3: Search pipeline
        search_query = analysis.search_query
        is_legal_admin = (analysis.category == "legal")
        needs_realtime = analysis.needs_realtime

        logger.info("Search pipeline: query='%s' legal=%s realtime=%s",
                     search_query[:60], is_legal_admin, needs_realtime)

        web_results_for_frontend = []

        # ── Step 4: Check cache (include conversation context in key)
        cache = get_response_cache()
        conv_fingerprint = _conversation_fingerprint(messages)
        cached = cache.get_response(query=search_query, context_fp=conv_fingerprint)

        if cached:
            logger.info("Cache HIT for search query")
            full_response = cached["response"]
            sources = cached.get("sources", [])
            yield _sse_data("chunk", full_response)
        else:
            # ── Step 5: Parallel RAG + Web search
            t0 = time.perf_counter()
            legal_articles, citation_ctx, search_warnings = _parallel_search(
                search_query, needs_realtime,
            )
            warnings.extend(search_warnings)
            logger.info("Search complete in %s: RAG=%d articles", _elapsed(t0), len(legal_articles))

            # Build context
            web_context = citation_ctx.context_str if citation_ctx else ""
            web_sources = citation_ctx.sources if citation_ctx else []
            rag_response = build_rag_context(legal_articles, web_context, web_sources)
            context = rag_response.rag_context

            # Inject stock data if needed
            stock_ctx = get_stock_context(question)
            if stock_ctx:
                context = stock_ctx + "\n\n" + context

            # Build frontend sources
            sources = _build_sources_list(legal_articles)
            web_results_for_frontend = _build_web_results(citation_ctx)

            # ── Step 6: Stream LLM response
            t0 = time.perf_counter()
            full_response = ""
            chunk_count = 0
            for chunk in stream_llm_response_plain(
                    question, context, sources, messages,
                    is_legal_admin=is_legal_admin,
                    response_style=analysis.response_style,
                    conv_id=conv_id or "",
                    user_id=user_id):
                full_response += chunk
                chunk_count += 1
                yield _sse_data("chunk", chunk)
            logger.info("Streamed %d chunks (%d chars) in %s",
                        chunk_count, len(full_response), _elapsed(t0))

            # Post-process citations
            if citation_ctx and citation_ctx.sources:
                full_response = postprocess_citations(
                    full_response, citation_ctx.sources)

            # Cache response (with conversation fingerprint)
            cache.set_response(
                query=search_query,
                response=full_response,
                sources=sources,
                context_fp=conv_fingerprint,
            )

        # ── Step 7: Save conversation (wrapped in try-catch)
        updated_messages = messages + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": full_response, "sources": sources},
        ]
        try:
            conv_id = save_conversation(conv_id, updated_messages, user_id=user_id)
            logger.info("Conversation saved: %s", conv_id)
        except Exception as e:
            logger.error("Failed to save conversation: %s", e)
            warnings.append("Không thể lưu lịch sử hội thoại")

        # ── Step 8: Generate suggestions
        suggestions = []
        try:
            suggestions = generate_suggested_questions(question, full_response)
        except Exception as e:
            logger.warning("Failed to generate suggestions: %s", e)

        # ── Step 9: Build legal basis for frontend
        legal_basis = _build_legal_basis(
            sources, full_response, is_legal_admin,
        )

        # ── Step 10: Final done event
        total_time = time.perf_counter() - t_start
        logger.info("Total pipeline time: %.2fs | response: %d chars",
                     total_time, len(full_response))

        done_event = {
            "type": "done",
            "conv_id": conv_id,
            "final_response": full_response,
            "legal_basis": legal_basis,
            "web_results": web_results_for_frontend,
            "sources": sources,
            "suggestions": suggestions,
            "warnings": warnings,
        }
        yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"

    except Exception as e:
        logger.error("Chat pipeline error after %s: %s", _elapsed(), e, exc_info=True)
        yield _sse_data("error", str(e))


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _sse_data(event_type: str, content, **extra) -> str:
    """Format an SSE data line."""
    payload = {"type": event_type}
    if content is not None:
        payload["content"] = content
    payload.update(extra)
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _parallel_search(search_query: str, needs_realtime: bool):
    """Run RAG + web search in parallel. Returns (legal_articles, citation_ctx, warnings)."""
    citation_ctx = None
    legal_articles = []
    warnings = []

    # Capture request ID from parent thread for worker thread context
    parent_request_id = get_request_id()

    def _run_rag():
        set_request_id(parent_request_id)
        retriever = get_retriever()
        return rag_search(retriever, search_query)

    def _run_web():
        set_request_id(parent_request_id)
        return legal_web_search(search_query, needs_realtime=needs_realtime)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        rag_future = executor.submit(_run_rag)
        web_future = executor.submit(_run_web)

        try:
            legal_articles = rag_future.result(timeout=config.RAG_TIMEOUT)
        except Exception as e:
            logger.error("RAG search failed: %s", e)
            legal_articles = []
            warnings.append("Tìm kiếm cơ sở dữ liệu nội bộ thất bại — chỉ có kết quả web")

        try:
            citation_ctx, _ = web_future.result(timeout=config.WEB_TIMEOUT)
        except Exception as e:
            logger.error("Web search failed: %s", e)
            warnings.append("Tìm kiếm web thất bại — chỉ có kết quả từ cơ sở dữ liệu")

    return legal_articles, citation_ctx, warnings


def _conversation_fingerprint(messages: List[Dict]) -> str:
    """Create a short fingerprint of conversation context for cache key."""
    if not messages:
        return ""
    # Use last 3 user messages to differentiate same question in different contexts
    user_msgs = [m.get("content", "")[:100] for m in messages if m.get("role") == "user"][-3:]
    import hashlib
    return hashlib.md5("|".join(user_msgs).encode()).hexdigest()[:12]


def _build_sources_list(legal_articles) -> List[Dict]:
    """Build deduplicated sources list for frontend."""
    sources = []
    seen_legal = set()
    for art in legal_articles:
        dedup_key = (art.document_name, art.article)
        if dedup_key in seen_legal:
            continue
        seen_legal.add(dedup_key)
        sources.append({
            "type": "legal",
            "document_name": art.document_name,
            "article": art.article,
            "clause": art.clause,
            "snippet": art.snippet,
            "content": art.content,
            "score": art.score,
            "loai_van_ban": art.loai_van_ban,
            "so_hieu": art.so_hieu,
            "trang_thai": art.trang_thai,
            "co_quan_ban_hanh": art.co_quan_ban_hanh,
            "ten_dieu": art.ten_dieu,
            "source_url": art.source_url,
        })
    return sources


def _build_web_results(citation_ctx) -> List[Dict]:
    """Build web results list for frontend."""
    if not citation_ctx or not citation_ctx.sources:
        return []
    return [
        {
            "type": "web",
            "url": s["url"],
            "title": s["title"],
            "domain": s.get("domain", ""),
            "reliability": s.get("reliability", 0.5),
            "publish_date": s.get("publish_date"),
        }
        for s in citation_ctx.sources
    ]


def _build_legal_basis(
    sources: List[Dict],
    full_response: str,
    is_legal_admin: bool,
) -> List[Dict]:
    """Build legal basis section for frontend with score filtering."""
    if not is_legal_admin:
        return []

    min_score = config.MIN_LEGAL_SCORE
    legal_basis = [
        s for s in sources
        if s.get("type") == "legal" and s.get("score", 0) >= min_score
    ]
    extra_refs = extract_refs_from_response(full_response, legal_basis)
    if extra_refs:
        legal_basis = legal_basis + extra_refs
    legal_basis = enrich_legal_basis(legal_basis)
    return legal_basis
