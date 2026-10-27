"""
Article Extractor — Trích xuất legal articles từ RAG vector search results.

Single Responsibility: Chỉ parse/extract structured LegalArticle từ raw documents.
Extracted from rag_service.py.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Set, Tuple

from chatbot_viva.core.patterns import (
    ARTICLE_RE, CLAUSE_RE, CROSS_REF_RE,
    ND_PATTERN, TT_PATTERN, DOC_NAME_PATTERNS,
)
from chatbot_viva.processing.doc_utils import get_legal_doc_name
from chatbot_viva.services.rag_models import LegalArticle

logger = logging.getLogger(__name__)

# Local aliases
_ARTICLE_RE = ARTICLE_RE
_CLAUSE_RE = CLAUSE_RE
_CROSS_REF_RE = CROSS_REF_RE
_ND_PATTERN = ND_PATTERN
_TT_PATTERN = TT_PATTERN
_DOC_NAME_PATTERNS = [(p.pattern, name) for p, name in DOC_NAME_PATTERNS]

# ── Dedup ──
_MIN_CONTENT_LENGTH = 50
_DEDUP_PREFIX_LENGTH = 100
_SNIPPET_LENGTH = 200


def extract_doc_name(source_url: str, content: str) -> str:
    """
    Extract readable document name from source URL or content.

    Tries Nghị định / Thông tư patterns from URL first,
    then known document patterns from content, then filename fallback.

    Args:
        source_url: URL of the source document.
        content: Raw text content.

    Returns:
        Human-readable document name (e.g. "Nghị định 96/2024/NĐ-CP").
    """
    source = source_url or ""

    nd_match = _ND_PATTERN.search(source)
    if nd_match:
        return f"Nghị định {nd_match.group(1)}/{nd_match.group(2)}/NĐ-CP"

    tt_match = _TT_PATTERN.search(source)
    if tt_match:
        return f"Thông tư {tt_match.group(1)}"

    for pattern, name in _DOC_NAME_PATTERNS:
        if re.search(pattern, content[:500]):
            year_match = re.search(r'(20\d{2})', content[:500])
            if year_match:
                return f"{name} {year_match.group(1)}"
            return name

    return get_legal_doc_name(source)


def extract_article_info(content: str) -> Tuple[str, str]:
    """
    Extract Điều (article) and Khoản (clause) from content text.

    Args:
        content: Raw text content.

    Returns:
        Tuple (article_str, clause_str). Either may be empty string.
    """
    article = ""
    clause = ""

    art_match = _ARTICLE_RE.search(content[:200])
    if art_match:
        article = art_match.group(1).strip()

    clause_match = _CLAUSE_RE.search(content[:300])
    if clause_match:
        clause = clause_match.group(1).strip()

    return article, clause


def _build_legal_article_from_doc(doc, score: float, seen_content: Set[str]) -> Optional[LegalArticle]:
    """
    Build a LegalArticle from a Document + score, with deduplication.

    Args:
        doc: LangChain Document with metadata.
        score: Similarity score.
        seen_content: Set of content prefixes already seen (mutated).

    Returns:
        LegalArticle or None if filtered/duplicate.
    """
    meta = doc.metadata
    content = doc.page_content.strip()

    if not content or len(content) < _MIN_CONTENT_LENGTH:
        return None

    content_key = content[:_DEDUP_PREFIX_LENGTH]
    if content_key in seen_content:
        return None
    seen_content.add(content_key)

    loai_van_ban = meta.get("loai_van_ban", "")
    so_hieu = meta.get("so_hieu", "")
    ten_dieu = meta.get("ten_dieu", "")
    dieu_so = meta.get("dieu_so", "")

    if loai_van_ban and so_hieu:
        doc_name = f"{loai_van_ban} số {so_hieu}"
    else:
        source = meta.get("source_url", "")
        doc_name = meta.get("document_name", "") or extract_doc_name(source, content)

    article = dieu_so
    clause = ""
    if not article:
        article, clause = extract_article_info(content)
    else:
        _, clause = extract_article_info(content)

    snippet = content[:_SNIPPET_LENGTH] + ("..." if len(content) > _SNIPPET_LENGTH else "")

    return LegalArticle(
        point_id=str(meta.get("_id", "")),
        document_name=doc_name,
        article=article,
        clause=clause,
        content=content,
        snippet=snippet,
        score=round(float(score), 4),
        loai_van_ban=loai_van_ban,
        so_hieu=so_hieu,
        trang_thai=meta.get("trang_thai", ""),
        co_quan_ban_hanh=meta.get("co_quan_ban_hanh", ""),
        ten_dieu=ten_dieu,
        source_url=meta.get("source_url", ""),
    )


def extract_legal_articles(docs_with_scores: list) -> List[LegalArticle]:
    """
    Extract structured legal articles from vector search results.

    Uses payload fields (loai_van_ban, so_hieu, ten_dieu) when available,
    falls back to content-based extraction.

    Args:
        docs_with_scores: List of (Document, score) tuples from Qdrant.

    Returns:
        Deduplicated list of LegalArticle objects.
    """
    seen_content: Set[str] = set()
    articles: List[LegalArticle] = []

    for doc, score in docs_with_scores:
        article = _build_legal_article_from_doc(doc, score, seen_content)
        if article is not None:
            articles.append(article)

    return articles


def extract_cross_references(articles: List[LegalArticle]) -> List[Tuple[str, str]]:
    """
    Scan article contents for cross-references to other Điều.

    Args:
        articles: Existing articles to scan.

    Returns:
        List of (article_ref, doc_hint) tuples, excluding self-references
        and articles already in the input list.
    """
    existing = {art.article.strip().lower() for art in articles if art.article}
    refs: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()

    for art in articles:
        for match in _CROSS_REF_RE.finditer(art.content):
            article_ref = match.group(1).strip()
            doc_hint = (match.group(2) or "").strip()

            if article_ref.lower() == art.article.strip().lower():
                continue
            if article_ref.lower() in existing:
                continue

            ref_key = (article_ref.lower(), doc_hint.lower())
            if ref_key in seen:
                continue
            seen.add(ref_key)
            refs.append((article_ref, doc_hint))

    return refs
