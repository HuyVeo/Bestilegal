"""Legal page analyzer — parse raw web content and score for relevance."""

import logging
import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

import pytz

from chatbot_viva.tools.legal_web_search import (
    LegalExtract, ArticleBlock, AmendmentInfo, ScoredPage,
)

logger = logging.getLogger(__name__)

# ── Regex patterns ──
_ARTICLE_RE = re.compile(
    r'(Điều\s+\d+[a-zđ]?)\s*[\.:]\s*([^\n]+)',
    re.IGNORECASE,
)
_CLAUSE_RE = re.compile(
    r'(Khoản\s+\d+)\s*[\.:]\s*([^\n]+)',
    re.IGNORECASE,
)
_AMENDMENT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'(sửa\s*đổi[,\s]*bổ\s*sung)',
        r'(bãi\s*bỏ)',
        r'(thay\s*thế)',
        r'(hết\s*hiệu\s*lực)',
        r'(được\s*sửa\s*đổi\s*bởi)',
        r'(được\s*bổ\s*sung\s*bởi)',
        r'(ngưng\s*hiệu\s*lực)',
    ]
]
_EFFECTIVE_DATE_RE = re.compile(
    r'(?:có\s*hiệu\s*lực|hiệu\s*lực\s*từ|áp\s*dụng\s*từ)\s*[:\s]*'
    r'(?:ngày\s*)?(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})',
    re.IGNORECASE,
)
_LEGAL_DOC_REF_RE = re.compile(
    r'((?:Luật|Nghị\s*định|Thông\s*tư|Quyết\s*định|Bộ\s*luật)'
    r'\s*(?:số\s*)?\d+[\w/\-]*)',
    re.IGNORECASE,
)
_PUBLISH_DATE_RE = re.compile(
    r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})',
)
_URL_DATE_RE = re.compile(r'/(\d{4})/(\d{1,2})/')

_NOISE_RES = [
    re.compile(p, re.IGNORECASE) for p in [
        r'<[^>]+>',
        r'Xem thêm:.*?(?=\n|$)',
        r'Đọc tiếp:.*?(?=\n|$)',
        r'Bài viết liên quan.*?(?=\n|$)',
        r'Tags?:.*?(?=\n|$)',
        r'\d+ lượt xem',
        r'\d+ bình luận',
        r'Chia sẻ.*?(?=\n|$)',
        r'Facebook|Twitter|Zalo|TikTok',
        r'Quảng cáo|Advertisement',
        r'https?://\S+',
    ]
]


class LegalPageParser:
    """Parse raw web page content into structured legal extract."""

    MAX_KEY_CONTENT = 3000

    def parse(self, raw_content: str, url: str, query: str,
              title: str = "", reliability: float = 0.5) -> LegalExtract:
        if not raw_content:
            raw_content = ""
        cleaned = self._clean(raw_content)
        domain = urlparse(url).netloc if url else ""

        articles = self._extract_articles(cleaned, query)
        amendments = self._extract_amendments(cleaned)
        effective_date = self._extract_effective_date(cleaned)
        publish_date = self._extract_publish_date(cleaned, url)
        referenced_docs = self._extract_referenced_docs(cleaned)
        key_content = self._build_key_content(cleaned, articles, amendments, query)

        return LegalExtract(
            url=url,
            title=title,
            domain=domain,
            reliability=reliability,
            articles=articles,
            amendments=amendments,
            effective_date=effective_date,
            publish_date=publish_date,
            referenced_docs=referenced_docs,
            key_content=key_content,
            raw_length=len(raw_content),
        )

    def _clean(self, text: str) -> str:
        for pattern in _NOISE_RES:
            text = pattern.sub('', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()

    def _extract_articles(self, text: str, query: str) -> List[ArticleBlock]:
        articles = []
        for m in _ARTICLE_RE.finditer(text):
            art_id = m.group(1).strip()
            art_title = m.group(2).strip()
            start = m.start()
            next_art = _ARTICLE_RE.search(text[m.end():])
            end = m.end() + next_art.start() if next_art else min(start + 2000, len(text))
            content = text[start:end].strip()
            has_amendment = any(p.search(content) for p in _AMENDMENT_PATTERNS)
            clause = ""
            cm = _CLAUSE_RE.search(content)
            if cm:
                clause = cm.group(1).strip()
            articles.append(ArticleBlock(
                article_id=art_id,
                clause_id=clause,
                content=content[:1500],
                has_amendment=has_amendment,
            ))
        return articles

    def _extract_amendments(self, text: str) -> List[AmendmentInfo]:
        amendments = []
        for pattern in _AMENDMENT_PATTERNS:
            for m in pattern.finditer(text):
                context_start = max(0, m.start() - 100)
                context_end = min(len(text), m.end() + 200)
                context = text[context_start:context_end].strip()
                ref_match = _LEGAL_DOC_REF_RE.search(context)
                amendments.append(AmendmentInfo(
                    marker=m.group(1).strip(),
                    detail=context[:200],
                    referenced_doc=ref_match.group(1).strip() if ref_match else "",
                ))
        return amendments[:10]

    def _extract_effective_date(self, text: str) -> Optional[str]:
        m = _EFFECTIVE_DATE_RE.search(text)
        return m.group(1) if m else None

    def _extract_publish_date(self, text: str, url: str) -> Optional[str]:
        m = _PUBLISH_DATE_RE.search(text[:500])
        if m:
            return m.group(1)
        um = _URL_DATE_RE.search(url)
        if um:
            return f"{um.group(2)}/{um.group(1)}"
        return None

    def _extract_referenced_docs(self, text: str) -> List[str]:
        refs = list(set(m.group(1).strip() for m in _LEGAL_DOC_REF_RE.finditer(text)))
        return refs[:20]

    def _build_key_content(self, text: str, articles: List[ArticleBlock],
                           amendments: List[AmendmentInfo], query: str) -> str:
        parts = []
        for a in amendments[:3]:
            parts.append(f"[SỬA ĐỔI] {a.detail}")

        query_terms = set(re.findall(r'\w+', query.lower()))
        matched_articles = []
        for art in articles:
            art_terms = set(re.findall(r'\w+', art.content.lower()))
            overlap = len(query_terms & art_terms) / max(len(query_terms), 1)
            if overlap > 0.3 or art.has_amendment:
                matched_articles.append(art)

        for art in matched_articles[:5]:
            parts.append(art.content)

        if not parts:
            parts.append(text[:self.MAX_KEY_CONTENT])

        result = "\n\n".join(parts)
        return result[:self.MAX_KEY_CONTENT]


class LegalPageScorer:
    """Rule-based scoring: trust x relevance x freshness x recency."""

    W_TRUST = 0.25
    W_RELEVANCE = 0.25
    W_FRESHNESS = 0.25
    W_RECENCY = 0.25

    def score_pages(self, extracts: List[LegalExtract],
                    query: str) -> List[ScoredPage]:
        logger.info("Scoring %d pages", len(extracts))

        scored = []
        for ext in extracts:
            trust = self._score_trust(ext)
            relevance = self._score_relevance(ext, query)
            freshness = self._score_freshness(ext)
            recency = self._score_recency(ext)

            composite = (
                self.W_TRUST * trust +
                self.W_RELEVANCE * relevance +
                self.W_FRESHNESS * freshness +
                self.W_RECENCY * recency
            )

            scored.append(ScoredPage(
                extract=ext,
                score=round(composite, 4),
                trust_score=round(trust, 3),
                relevance_score=round(relevance, 3),
                freshness_score=round(freshness, 3),
                recency_score=round(recency, 3),
                rank=0,
            ))

        scored.sort(key=lambda x: x.score, reverse=True)
        for i, sp in enumerate(scored):
            sp.rank = i + 1

        if scored:
            logger.info(
                "Scored %d pages: top=%s (%.4f), bottom=%s (%.4f)",
                len(scored),
                scored[0].extract.domain, scored[0].score,
                scored[-1].extract.domain, scored[-1].score,
            )

        return scored

    def _score_trust(self, ext: LegalExtract) -> float:
        return ext.reliability

    def _score_relevance(self, ext: LegalExtract, query: str) -> float:
        query_terms = set(re.findall(r'\w+', query.lower()))
        if not query_terms:
            return 0.5
        content_lower = ext.key_content.lower()
        matched = sum(1 for t in query_terms if t in content_lower)
        base = matched / len(query_terms)
        if ext.articles:
            base += 0.1
        query_articles = set(re.findall(r'điều\s*\d+', query.lower()))
        if query_articles:
            page_articles = {a.article_id.lower() for a in ext.articles}
            if query_articles & page_articles:
                base += 0.2
        return min(base, 1.0)

    def _score_freshness(self, ext: LegalExtract) -> float:
        score = 0.3
        if ext.amendments:
            score += min(len(ext.amendments) * 0.15, 0.4)
        if ext.effective_date:
            score += 0.1
        if ext.referenced_docs:
            score += min(len(ext.referenced_docs) * 0.05, 0.2)
        return min(score, 1.0)

    def _score_recency(self, ext: LegalExtract) -> float:
        try:
            now = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
        except Exception:
            now = datetime.now()
        current_year = now.year
        year = self._extract_year(ext.publish_date, ext.url)
        if year is None:
            year = self._extract_year(ext.effective_date, "")
        if year is None:
            return 0.4
        age = current_year - year
        if age <= 0:
            return 1.0
        elif age == 1:
            return 0.85
        elif age <= 2:
            return 0.7
        elif age <= 3:
            return 0.55
        elif age <= 5:
            return 0.4
        else:
            return 0.2

    def _extract_year(self, date_str: Optional[str], url: str) -> Optional[int]:
        if date_str:
            m = re.search(r'(\d{4})', date_str)
            if m:
                y = int(m.group(1))
                if 1990 <= y <= 2030:
                    return y
        if url:
            m = re.search(r'/(\d{4})/', url)
            if m:
                y = int(m.group(1))
                if 1990 <= y <= 2030:
                    return y
        return None
