"""
RAG-first service — Vector search primary, web search secondary.

Refactored: Data models → rag_models.py, extraction → article_extractor.py.
This module now coordinates the RAG pipeline (search → extract → expand → build context).

Public API:
  - rag_search(retriever, query, k) → List[LegalArticle]
  - build_rag_context(legal_articles, web_context, web_sources) → RAGResponse
  - extract_refs_from_response(llm_response, existing_sources) → list
"""
from __future__ import annotations

import logging
import re
import time
from typing import List, Optional, Tuple

from chatbot_viva.core import config

# Re-export models for backward compatibility
from chatbot_viva.services.rag_models import LegalArticle, WebResult, RAGResponse  # noqa: F401
from chatbot_viva.services.article_extractor import (
    extract_legal_articles,
    extract_cross_references,
    extract_doc_name as _extract_doc_name,
    extract_article_info as _extract_article_info,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# Recursive RAG — auto-fetch cross-referenced articles
# ════════════════════════════════════════════════════════════════

def expand_related_articles(
    retriever,
    initial_articles: List[LegalArticle],
    max_refs: Optional[int] = None,
    ref_k: int = 3,
    min_score: float = 0.45,
    _depth: int = 0,
) -> List[LegalArticle]:
    """
    Recursive RAG: scan initial articles for cross-referenced Điều,
    then search Qdrant for each and merge results.

    Args:
        retriever: Qdrant retriever instance.
        initial_articles: Articles to scan for cross-references.
        max_refs: Max references to expand per level.
        ref_k: Number of results per reference query.
        min_score: Minimum similarity score for inclusion.
        _depth: Current recursion depth (internal).

    Returns:
        initial_articles + any related articles found.
    """
    if max_refs is None:
        max_refs = config.MAX_RECURSIVE_REFS
    max_depth = config.MAX_RECURSIVE_DEPTH

    if _depth >= max_depth:
        logger.info("Recursive RAG depth limit reached (%d/%d)", _depth, max_depth)
        return initial_articles

    cross_refs = extract_cross_references(initial_articles)
    if not cross_refs:
        return initial_articles

    cross_refs = cross_refs[:max_refs]
    logger.info(
        "Recursive RAG: expanding %d cross-references (depth=%d/%d)",
        len(cross_refs), _depth + 1, max_depth,
    )

    t0 = time.perf_counter()
    existing_keys = {art.content[:100] for art in initial_articles}
    related: List[LegalArticle] = []

    try:
        vectorstore = retriever.vectorstore
    except Exception as e:
        logger.warning("Cannot access vectorstore for recursive RAG: %s", e)
        return initial_articles

    for article_ref, doc_hint in cross_refs:
        query = f"{article_ref} {doc_hint}".strip() if doc_hint else article_ref

        try:
            docs_with_scores = vectorstore.similarity_search_with_score(query, k=ref_k)
        except Exception as e:
            logger.warning("Recursive RAG search failed for '%s': %s", query, e)
            continue

        for doc, score in docs_with_scores:
            article = _build_recursive_article(
                doc, score, article_ref, min_score, existing_keys,
            )
            if article is not None:
                related.append(article)

    elapsed = time.perf_counter() - t0
    logger.info(
        "Recursive RAG: found %d related articles in %.2fs (depth=%d)",
        len(related), elapsed, _depth + 1,
    )

    return initial_articles + related


def _build_recursive_article(
    doc,
    score: float,
    article_ref: str,
    min_score: float,
    existing_keys: set,
) -> Optional[LegalArticle]:
    """
    Build a LegalArticle from a recursive search result.

    Validates score, content length, dedup, and article match.

    Returns:
        LegalArticle or None if filtered.
    """
    score_val = round(float(score), 4)
    if score_val < min_score:
        return None

    content = doc.page_content.strip()
    if not content or len(content) < 50:
        return None

    content_key = content[:100]
    if content_key in existing_keys:
        return None
    existing_keys.add(content_key)

    meta = doc.metadata
    detected_art = meta.get("dieu_so", "")
    if not detected_art:
        detected_art, _ = _extract_article_info(content)
    if detected_art and detected_art.lower() != article_ref.lower():
        return None

    loai_van_ban = meta.get("loai_van_ban", "")
    so_hieu = meta.get("so_hieu", "")

    if loai_van_ban and so_hieu:
        doc_name = f"{loai_van_ban} số {so_hieu}"
    else:
        source = meta.get("source_url", "")
        doc_name = meta.get("document_name", "") or _extract_doc_name(source, content)

    article = meta.get("dieu_so", "")
    clause = ""
    if not article:
        article, clause = _extract_article_info(content)
    else:
        _, clause = _extract_article_info(content)

    return LegalArticle(
        point_id=str(meta.get("_id", "")),
        document_name=doc_name,
        article=article,
        clause=clause,
        content=content,
        snippet=content[:200] + ("..." if len(content) > 200 else ""),
        score=score_val,
        loai_van_ban=loai_van_ban,
        so_hieu=so_hieu,
        trang_thai=meta.get("trang_thai", ""),
        co_quan_ban_hanh=meta.get("co_quan_ban_hanh", ""),
        ten_dieu=meta.get("ten_dieu", ""),
        source_url=meta.get("source_url", ""),
    )


# ════════════════════════════════════════════════════════════════
# RAG-first search
# ════════════════════════════════════════════════════════════════

def rag_search(retriever, query: str, k: Optional[int] = None) -> List[LegalArticle]:
    """
    Search Qdrant for relevant legal articles with hybrid BM25 rescoring
    and optional LLM reranking.

    Pipeline:
      1. Vector search (wide pool: k * 4)
      2. BM25 hybrid rescoring (vector 60% + BM25 40%)
      3. Metadata filtering + topic boosting
      4. LLM reranking (if enabled and >= 2 docs)
      5. Extract legal articles
      6. Recursive cross-reference expansion

    Args:
        retriever: Qdrant retriever instance.
        query: Search query.
        k: Number of final results (defaults to config.RAG_FETCH_K).

    Returns:
        List of LegalArticle sorted by score.
    """
    from chatbot_viva.retrieval.hybrid_search import get_hybrid_searcher
    from chatbot_viva.retrieval.reranker import get_reranker
    from chatbot_viva.retrieval.metadata_filter import (
        filter_documents, boost_by_metadata, detect_topics,
    )

    if k is None:
        k = config.RAG_FETCH_K
    fetch_k = k * 4
    t0 = time.perf_counter()
    logger.info("RAG search: %s (k=%d, fetch_k=%d)", query[:60], k, fetch_k)

    # Step 1: Vector search
    try:
        vectorstore = retriever.vectorstore
        docs_with_scores = vectorstore.similarity_search_with_score(query, k=fetch_k)
    except Exception as e:
        logger.error("RAG vector search failed: %s", e)
        return []

    # Step 2: BM25 hybrid rescoring
    docs_with_scores = _apply_hybrid_rescoring(docs_with_scores, query, fetch_k)

    # Step 3: Quality filter
    valid_docs = [
        (doc, score) for doc, score in docs_with_scores
        if score >= config.MIN_SIMILARITY_SCORE and len(doc.page_content.strip()) >= 50
    ]

    # Step 4: Metadata filtering + topic boosting
    valid_docs = _apply_metadata_boosting(valid_docs, query, filter_documents, boost_by_metadata, detect_topics)

    # Step 5: LLM reranking
    valid_docs = _apply_reranking(valid_docs, query, k, get_reranker)

    # Step 6: Extract structured legal articles
    articles = extract_legal_articles(valid_docs)

    elapsed = time.perf_counter() - t0
    logger.info("RAG found %d articles in %.2fs", len(articles), elapsed)

    # Step 7: Recursive cross-reference expansion
    if articles:
        articles = expand_related_articles(retriever, articles, _depth=0)

    return articles


def _apply_hybrid_rescoring(docs_with_scores: list, query: str, fetch_k: int) -> list:
    """Apply BM25 hybrid rescoring to vector results."""
    from chatbot_viva.retrieval.hybrid_search import get_hybrid_searcher

    try:
        hybrid_searcher = get_hybrid_searcher()
        if hybrid_searcher.bm25_index is not None and docs_with_scores:
            hybrid_results = hybrid_searcher.hybrid_search(
                query=query,
                vector_results=docs_with_scores,
                k=fetch_k,
                min_score=0.0,
            )
            docs_with_scores = [
                (r.document, r.combined_score) for r in hybrid_results
            ]
            logger.info("Hybrid BM25 rescoring: %d candidates", len(docs_with_scores))
    except Exception as e:
        logger.warning("BM25 hybrid failed, using vector-only: %s", e)

    return docs_with_scores


def _apply_metadata_boosting(valid_docs: list, query: str,
                              filter_fn, boost_fn, detect_fn) -> list:
    """Apply metadata filtering and topic boosting."""
    if not valid_docs:
        return valid_docs

    query_topics = detect_fn(query)
    docs_only = [doc for doc, _ in valid_docs]
    filtered = filter_fn(docs_only)
    filtered_ids = {id(d) for d in filtered}
    valid_docs = [(doc, s) for doc, s in valid_docs if id(doc) in filtered_ids]
    valid_docs = boost_fn(valid_docs, query_topics)
    return valid_docs


def _apply_reranking(valid_docs: list, query: str, k: int, get_reranker_fn) -> list:
    """Apply LLM reranking if enabled."""
    if valid_docs and getattr(config, "RERANK_ENABLED", True) and len(valid_docs) >= 2:
        try:
            reranker = get_reranker_fn()
            reranked = reranker.rerank(
                query=query,
                documents=valid_docs,
                top_k=k,
                min_score=0.2,
            )
            valid_docs = [(r.document, r.relevance_score) for r in reranked]
            if reranked:
                logger.info("LLM reranked %d docs, top score: %.2f",
                            len(reranked), reranked[0].relevance_score)
        except Exception as e:
            logger.warning("Reranking failed, keeping sorted order: %s", e)
            valid_docs = valid_docs[:k]
    else:
        valid_docs = valid_docs[:k]

    return valid_docs


# ════════════════════════════════════════════════════════════════
# Extract legal refs from LLM response → fill missing legal_basis
# ════════════════════════════════════════════════════════════════

_LLM_REF_RE = re.compile(
    r'(Điều\s+\d+[a-zđ]?)'
    r'(?:\s*,\s*(Khoản\s+\d+))?'
    r'(?:\s*,?\s*(?:của\s+)?'
    r'((?:Luật|Nghị định|Thông tư|Bộ luật)[A-ZĐÀ-Ỹa-zđà-ỹ\s/\-]*(?:20\d{2})?'
    r'(?:/[A-ZĐa-zđ\-]+)*))?',
    re.IGNORECASE | re.UNICODE,
)

_DOC_ONLY_RE = re.compile(
    r'((?:Nghị định|Thông tư)\s+\d+/\d{4}/[A-ZĐa-zđ\-]+)',
    re.IGNORECASE | re.UNICODE,
)


def extract_refs_from_response(
    llm_response: str,
    existing_sources: list,
) -> list:
    """
    Scan LLM response for legal references not already in sources.

    Args:
        llm_response: The LLM's text response.
        existing_sources: Already-known source dicts.

    Returns:
        List of new reference dicts to append to legal_basis for frontend.
    """
    existing = set()
    for s in existing_sources:
        key = (s.get("document_name", "").lower(), s.get("article", "").lower())
        existing.add(key)

    new_refs: list = []
    seen: set = set()

    new_refs.extend(_extract_article_refs(llm_response, existing, seen))
    new_refs.extend(_extract_doc_only_refs(llm_response, existing, seen))

    if new_refs:
        logger.info("Extracted %d additional refs from LLM response", len(new_refs))

    return new_refs


def _extract_article_refs(text: str, existing: set, seen: set) -> list:
    """Extract 'Điều X, Khoản Y, Luật Z' style references."""
    refs = []
    for m in _LLM_REF_RE.finditer(text):
        article = m.group(1).strip()
        clause = (m.group(2) or "").strip()
        doc_name = (m.group(3) or "").strip()

        if not doc_name:
            continue

        key = (doc_name.lower(), article.lower())
        if key in existing or key in seen:
            continue
        seen.add(key)

        snippet = f"{article}, {clause}, {doc_name}".strip(", ") if clause else f"{article}, {doc_name}"
        refs.append({
            "type": "legal",
            "document_name": doc_name,
            "article": article,
            "clause": clause,
            "snippet": snippet,
            "content": "",
            "score": 0,
            "from_response": True,
        })
    return refs


def _extract_doc_only_refs(text: str, existing: set, seen: set) -> list:
    """Extract standalone 'Nghị định X/YYYY/NĐ-CP' references."""
    refs = []
    for m in _DOC_ONLY_RE.finditer(text):
        doc_name = m.group(1).strip()
        key = (doc_name.lower(), "")
        if key in existing or key in seen:
            continue
        if any(doc_name.lower() in k[0] for k in seen):
            continue
        seen.add(key)

        refs.append({
            "type": "legal",
            "document_name": doc_name,
            "article": "",
            "clause": "",
            "snippet": doc_name,
            "content": "",
            "score": 0,
            "from_response": True,
        })
    return refs


# ════════════════════════════════════════════════════════════════
# Build RAG-first context for LLM
# ════════════════════════════════════════════════════════════════

def build_rag_context(
    legal_articles: List[LegalArticle],
    web_context: str = "",
    web_sources: Optional[list] = None,
) -> RAGResponse:
    """
    Build LLM context with RAG as primary, web as secondary.

    Args:
        legal_articles: Articles from Qdrant vector search.
        web_context: Citation context from web search pipeline.
        web_sources: Source list from web search.

    Returns:
        RAGResponse with structured data.
    """
    parts: List[str] = []

    if legal_articles:
        parts.append(_format_rag_section(legal_articles))

    if web_context:
        parts.append(_format_web_section(web_context))

    rag_context = "\n\n".join(parts) if parts else "Không tìm thấy thông tin trong cơ sở dữ liệu."

    web_results = _build_web_results(web_sources)

    return RAGResponse(
        rag_context=rag_context,
        legal_basis=legal_articles,
        web_results=web_results,
        rag_sources_count=len(legal_articles),
        web_sources_count=len(web_results),
    )


def _format_rag_section(articles: List[LegalArticle]) -> str:
    """Format legal articles into RAG context section."""
    lines = [
        "=== CĂN CỨ PHÁP LÝ (TỪ CƠ SỞ DỮ LIỆU NỘI BỘ — NGUỒN CHÍNH) ===",
        "Đây là nội dung điều luật chính thức. HÃY ƯU TIÊN sử dụng nguồn này.",
        "BẮT BUỘC: Khi trích dẫn, ghi rõ Điều/Khoản + tên văn bản + [RN]. "
        "VD: (Điều 328, Khoản 2, Bộ luật Dân sự 2015 [R1]).",
        "",
    ]

    for i, art in enumerate(articles, 1):
        label = _format_article_label(art)
        lines.append(f"[R{i}] {label}")
        lines.append(art.content)
        lines.append("---")

    return "\n".join(lines)


def _format_article_label(art: LegalArticle) -> str:
    """Format article label for context display."""
    label = art.document_name
    if art.ten_dieu:
        label += f", {art.ten_dieu}"
    elif art.article:
        label += f", {art.article}"
    if art.clause:
        label += f", {art.clause}"
    if art.trang_thai:
        label += f" [{art.trang_thai}]"
    return label


def _format_web_section(web_context: str) -> str:
    """Format web results into supplementary context section."""
    return (
        "\n=== THÔNG TIN BỔ SUNG TỪ WEB (NGUỒN PHỤ) ===\n"
        "Dùng để kiểm tra sửa đổi/bổ sung mới nhất hoặc bổ sung thông tin.\n\n"
        + web_context
    )


def _build_web_results(web_sources: Optional[list]) -> List[WebResult]:
    """Build WebResult list from raw source dicts."""
    if not web_sources:
        return []
    return [
        WebResult(
            url=s.get("url", ""),
            title=s.get("title", ""),
            domain=s.get("domain", ""),
            snippet=s.get("snippet", ""),
            reliability=s.get("reliability", 0.5),
            publish_date=s.get("publish_date"),
        )
        for s in web_sources
    ]
