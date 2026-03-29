"""
Legal Web Search Pipeline — Fetch 10 pages, parse legal content, score & cite.

Flow:
  1. LegalQueryExpander  — sinh sub-queries cho sửa đổi/bổ sung
  2. Tavily fetch         — 3 queries song song, dedup, filter → 10 pages
  3. LegalPageParser      — parse raw_content → structured LegalExtract
  4. LegalPageScorer      — rule-based scoring (trust × relevance × freshness × recency)
  5. CitationContextBuilder — build numbered [1]..[10] context for LLM
  6. postprocess_citations — convert [1] → clickable markdown links
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# Data classes (shared across sub-modules)
# ════════════════════════════════════════════════════════════════

@dataclass
class ArticleBlock:
    """A single Điều/Khoản block extracted from a page."""
    article_id: str
    clause_id: str
    content: str
    has_amendment: bool


@dataclass
class AmendmentInfo:
    """Info about a legal amendment found on the page."""
    marker: str
    detail: str
    referenced_doc: str


@dataclass
class LegalExtract:
    """Structured content parsed from a web page."""
    url: str
    title: str
    domain: str
    reliability: float
    articles: List[ArticleBlock] = field(default_factory=list)
    amendments: List[AmendmentInfo] = field(default_factory=list)
    effective_date: Optional[str] = None
    publish_date: Optional[str] = None
    referenced_docs: List[str] = field(default_factory=list)
    key_content: str = ""
    raw_length: int = 0


@dataclass
class ScoredPage:
    """A page with composite score breakdown."""
    extract: LegalExtract
    score: float
    trust_score: float
    relevance_score: float
    freshness_score: float
    recency_score: float
    rank: int = 0


@dataclass
class CitationContext:
    """Final citation context for LLM prompt."""
    context_str: str
    sources: List[dict]
    total_chars: int
    pages_used: int


# ════════════════════════════════════════════════════════════════
# Reliability labels
# ════════════════════════════════════════════════════════════════

_RELIABILITY_LABELS = {
    (0.9, 1.01): "🏛️ Chính thống",
    (0.8, 0.9):  "✅ Uy tín",
    (0.7, 0.8):  "📰 Báo chí",
    (0.6, 0.7):  "📊 Chuyên ngành",
    (0.0, 0.6):  "ℹ️ Tham khảo",
}


def _reliability_label(score: float) -> str:
    for (lo, hi), label in _RELIABILITY_LABELS.items():
        if lo <= score < hi:
            return label
    return "ℹ️ Tham khảo"


# ════════════════════════════════════════════════════════════════
# Citation context builder
# ════════════════════════════════════════════════════════════════

class CitationContextBuilder:
    """Build numbered citation context for LLM prompt."""

    MAX_TOTAL_CHARS = 25_000
    MAX_PER_SOURCE_HIGH = 3500
    MAX_PER_SOURCE_LOW = 1500

    def build(self, scored_pages: List[ScoredPage]) -> CitationContext:
        if not scored_pages:
            return CitationContext(
                context_str="Không tìm thấy nguồn web.",
                sources=[], total_chars=0, pages_used=0,
            )

        sources = []
        context_parts = []
        total_chars = 0

        median_score = scored_pages[len(scored_pages) // 2].score if scored_pages else 0.5

        for sp in scored_pages:
            if total_chars >= self.MAX_TOTAL_CHARS:
                break

            ext = sp.extract
            idx = sp.rank
            label = _reliability_label(ext.reliability)

            budget = self.MAX_PER_SOURCE_HIGH if sp.score >= median_score else self.MAX_PER_SOURCE_LOW
            remaining_budget = self.MAX_TOTAL_CHARS - total_chars
            budget = min(budget, remaining_budget)

            content = ext.key_content[:budget]

            block = f"[{idx}] {ext.title} | {label} | Score: {sp.score:.3f}\n"
            block += f"    URL: {ext.url}\n"

            if ext.publish_date:
                block += f"    Ngày: {ext.publish_date}\n"
            if ext.effective_date:
                block += f"    Hiệu lực: {ext.effective_date}\n"

            if ext.amendments:
                block += f"    ⚠️ SỬA ĐỔI/BỔ SUNG:\n"
                for a in ext.amendments[:3]:
                    block += f"      - {a.marker}"
                    if a.referenced_doc:
                        block += f" ({a.referenced_doc})"
                    block += "\n"

            block += f"    Nội dung:\n{content}\n"

            context_parts.append(block)
            total_chars += len(block)

            sources.append({
                "idx": idx,
                "url": ext.url,
                "title": ext.title,
                "domain": ext.domain,
                "reliability": ext.reliability,
                "score": sp.score,
                "publish_date": ext.publish_date,
            })

        context_str = (
            f"=== NGUỒN THAM KHẢO ({len(sources)} trang web) ===\n"
            f"Khi trích dẫn, dùng số [1], [2]... tương ứng.\n\n"
            + "\n---\n".join(context_parts)
        )

        logger.info("Built citation context: %d chars, %d sources", total_chars, len(sources))

        return CitationContext(
            context_str=context_str,
            sources=sources,
            total_chars=total_chars,
            pages_used=len(sources),
        )


# ════════════════════════════════════════════════════════════════
# Citation post-processor
# ════════════════════════════════════════════════════════════════

def postprocess_citations(response: str, sources: List[dict]) -> str:
    """
    Clean up LLM response: strip inline citation markers and
    remove generated reference/legal-basis sections (shown in UI separately).
    """
    if not sources:
        return response

    cleaned = response
    cleaned = re.sub(r'\[\[R?\d+\]\]\([^)]+\)', '', cleaned)
    cleaned = re.sub(r'<a[^>]*>\[R?\d+\]</a>', '', cleaned)
    cleaned = re.sub(r'\[R?\d+(?:\s*,\s*R?\d+)*\]', '', cleaned)

    cleaned = re.sub(
        r'\n---\s*\n[*]*[Nn]guồn tham khảo[*]*[^\n]*\n(?:[ \t]*[-*\[\d<(][^\n]*\n)*',
        '\n', cleaned)
    cleaned = re.sub(
        r'\n#{1,3}\s*[Nn]guồn tham khảo[^\n]*\n(?:[ \t]*[-*\[\d<(][^\n]*\n)*',
        '\n', cleaned)
    cleaned = re.sub(
        r'\n\*{2}[Nn]guồn tham khảo[^\n]*\n(?:[ \t]*[-*\[\d<(][^\n]*\n)*',
        '\n', cleaned)
    cleaned = re.sub(
        r'\n[Nn]guồn tham khảo\s*:?\s*\n(?:[-*\[\d<(][^\n]*\n?)*',
        '\n', cleaned)

    cleaned = re.sub(
        r'\n#{1,3}\s*[Cc]ăn cứ pháp lý[^\n]*\n(?:[ \t]*[-*\[\d<(][^\n]*\n)*',
        '\n', cleaned)
    cleaned = re.sub(
        r'\n\*{2}[Cc]ăn cứ pháp lý\*{0,2}[^\n]*\n(?:[ \t]*[-*\[\d<(][^\n]*\n)*',
        '\n', cleaned)
    cleaned = re.sub(
        r'\n[Cc]ăn cứ pháp lý\s*:?\s*\n(?:[-*\[].+\n?)*',
        '\n', cleaned)

    cleaned = re.sub(r' ([.,;:!?])', r'\1', cleaned)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    cleaned = re.sub(r'(,\s*){2,}', '', cleaned)
    cleaned = re.sub(r'\.{2,}', '.', cleaned)
    cleaned = re.sub(r',\.', '.', cleaned)
    cleaned = re.sub(r'\.,', '.', cleaned)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    cleaned = cleaned.rstrip()

    return cleaned


# ════════════════════════════════════════════════════════════════
# Main pipeline function
# ════════════════════════════════════════════════════════════════

# Lazy imports to avoid circular dependency
_expander = None
_parser = None
_scorer = None
_builder = CitationContextBuilder()


def _get_components():
    global _expander, _parser, _scorer
    if _expander is None:
        from chatbot_viva.tools.legal_web_fetcher import LegalQueryExpander
        from chatbot_viva.tools.legal_page_analyzer import LegalPageParser, LegalPageScorer
        _expander = LegalQueryExpander()
        _parser = LegalPageParser()
        _scorer = LegalPageScorer()
    return _expander, _parser, _scorer


def legal_web_search(query: str, needs_realtime: bool = False) -> Tuple[CitationContext, List[ScoredPage]]:
    """
    Full legal web search pipeline.

    Returns:
        Tuple of (CitationContext for LLM, list of ScoredPages for reference).
    """
    from chatbot_viva.tools.legal_web_fetcher import fetch_legal_pages

    pipeline_start = time.perf_counter()
    logger.info("Web pipeline starting for: '%s' (realtime=%s)", query[:80], needs_realtime)

    expander, parser, scorer = _get_components()

    # Step 1: Expand queries
    queries = expander.expand(query, needs_realtime=needs_realtime)
    logger.info("Step 1: expanded to %d queries", len(queries))

    # Step 2: Fetch pages
    pages = fetch_legal_pages(queries)
    logger.info("Step 2: fetched %d pages", len(pages))

    if not pages:
        logger.warning("No pages found — returning empty context")
        return CitationContext(
            context_str="Không tìm thấy nguồn web đáng tin cậy.",
            sources=[], total_chars=0, pages_used=0,
        ), []

    # Step 3: Parse pages
    extracts = []
    for p in pages:
        raw = p.get("raw_content") or p.get("content", "")
        url = p.get("url", "")
        title = p.get("title", "") or url
        reliability = p.get("reliability", 0.5)
        ext = parser.parse(raw, url, query, title, reliability)
        extracts.append(ext)
    logger.info("Step 3: parsed %d pages", len(extracts))

    # Step 4: Score pages
    scored = scorer.score_pages(extracts, query)
    logger.info("Step 4: scored %d pages", len(scored))

    # Step 5: Build citation context
    citation_ctx = _builder.build(scored)

    total_time = time.perf_counter() - pipeline_start
    logger.info(
        "Web pipeline complete in %.2fs: %d pages, %d chars",
        total_time, citation_ctx.pages_used, citation_ctx.total_chars,
    )

    return citation_ctx, scored
