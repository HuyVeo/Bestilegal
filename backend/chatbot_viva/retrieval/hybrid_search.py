"""Hybrid Search: BM25 + Vector Search for better retrieval."""

import logging
import os
import pickle
import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

_VIET_TOKEN_RE = re.compile(
    r'[^\w\d\sàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]'
)


@dataclass
class SearchResult:
    """Search result with combined score."""
    document: Document
    vector_score: float
    bm25_score: float
    combined_score: float
    source_credibility: str  # "high", "medium", "low"
    content_year: Optional[int] = None  # Year extracted from content


# Trusted domains for Vietnamese legal content
TRUSTED_DOMAINS = {
    # === GOVERNMENT SOURCES (highest trust) ===
    "chinhphu.vn": "high",
    "vanban.chinhphu.vn": "high",
    "congbao.chinhphu.vn": "high",
    "moj.gov.vn": "high",
    "monre.gov.vn": "high",
    "most.gov.vn": "high",
    "moc.gov.vn": "high",
    "sbv.gov.vn": "high",
    "mof.gov.vn": "high",
    "molisa.gov.vn": "high",
    "mpi.gov.vn": "high",
    "mic.gov.vn": "high",
    "quochoi.vn": "high",
    "toaan.gov.vn": "high",
    "vksndtc.gov.vn": "high",

    # === LEGAL DATABASES (high trust) ===
    "thuvienphapluat.vn": "high",
    "luatvietnam.vn": "high",
    "lawnet.vn": "high",
    "vbpl.vn": "high",
    "tracuuphapluat.com": "high",

    # === REAL ESTATE SPECIFIC (high trust for BDS domain) ===
    "moc.gov.vn/vbpq": "high",
    "qdnd.vn": "medium",

    # === REPUTABLE NEWS (medium trust) ===
    "vnexpress.net": "medium",
    "vietnamnet.vn": "medium",
    "tuoitre.vn": "medium",
    "thanhnien.vn": "medium",
    "dantri.com.vn": "medium",
    "nhandan.vn": "medium",
    "baochinhphu.vn": "medium",

    # === REAL ESTATE NEWS (medium trust) ===
    "cafef.vn": "medium",
    "cafeland.vn": "medium",
    "batdongsan.com.vn": "medium",
    "muabannhadat.vn": "medium",
    "nhadatviet.vn": "medium",
    "reatimes.vn": "medium",
    "vietnamfinance.vn": "medium",

    # === LEGAL CONSULTING (medium trust) ===
    "luatduonggia.vn": "medium",
    "luatsux.vn": "medium",
    "luatminhkhue.vn": "medium",
    "luathungphat.vn": "medium",
    "lawkey.vn": "medium",
    "hocluat.vn": "medium",
}

# Credibility boost factors
CREDIBILITY_BOOST = {
    "high": 1.5,
    "medium": 1.2,
    "low": 1.0,
}

# Freshness boost factors (newer = better for legal documents)
FRESHNESS_BOOST = {
    "current": 1.3,
    "recent": 1.15,
    "dated": 1.0,
    "old": 0.9,
}


def extract_year_from_content(text: str, url: str = "") -> Optional[int]:
    """Extract document year from content or URL."""
    current_year = datetime.now().year

    legal_pattern = r'\d+/(\d{4})/[A-ZĐ]+'
    matches = re.findall(legal_pattern, text)
    if matches:
        years = [int(y) for y in matches if 1990 <= int(y) <= current_year]
        if years:
            return max(years)

    year_pattern = r'(?:năm|year)\s*(\d{4})'
    matches = re.findall(year_pattern, text.lower())
    if matches:
        years = [int(y) for y in matches if 1990 <= int(y) <= current_year]
        if years:
            return max(years)

    date_pattern = r'(?:\d{1,2}/\d{1,2}/(\d{4})|(\d{4})-\d{1,2}-\d{1,2})'
    matches = re.findall(date_pattern, text)
    if matches:
        years = []
        for m in matches:
            y = m[0] or m[1]
            if y and 1990 <= int(y) <= current_year:
                years.append(int(y))
        if years:
            return max(years)

    if url:
        url_year_pattern = r'/(\d{4})/'
        matches = re.findall(url_year_pattern, url)
        if matches:
            years = [int(y) for y in matches if 1990 <= int(y) <= current_year]
            if years:
                return max(years)

    return None


def get_freshness_level(year: Optional[int], trang_thai: str = "") -> str:
    """Get freshness level based on document year and legal status.

    Documents marked "Còn hiệu lực" are never penalized regardless of age.
    """
    # Active laws should never be penalized for age
    if trang_thai and "còn hiệu lực" in trang_thai.lower():
        if year is None:
            return "dated"
        current_year = datetime.now().year
        age = current_year - year
        # Still boost recent active laws, but don't penalize old active ones
        if age <= 1:
            return "current"
        elif age <= 3:
            return "recent"
        return "dated"  # No penalty for old-but-active laws

    if year is None:
        return "dated"

    current_year = datetime.now().year
    age = current_year - year

    if age <= 1:
        return "current"
    elif age <= 3:
        return "recent"
    elif age <= 5:
        return "dated"
    else:
        return "old"


def boost_score_by_freshness(score: float, year: Optional[int],
                             trang_thai: str = "") -> float:
    """Apply freshness boost to a score."""
    freshness = get_freshness_level(year, trang_thai)
    return score * FRESHNESS_BOOST.get(freshness, 1.0)


def tokenize_vietnamese(text: str) -> List[str]:
    """Simple Vietnamese tokenizer for BM25."""
    text = text.lower()
    text = _VIET_TOKEN_RE.sub(' ', text)
    tokens = [t.strip() for t in text.split() if t.strip()]
    return tokens


def get_domain_credibility(url: str) -> str:
    """Get credibility level for a domain using proper URL parsing."""
    if not url:
        return "low"

    from urllib.parse import urlparse
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return "low"

    hostname = hostname.lower()

    for domain, credibility in TRUSTED_DOMAINS.items():
        # Match exact domain or subdomain (e.g., "chinhphu.vn" matches "www.chinhphu.vn")
        if hostname == domain or hostname.endswith("." + domain):
            return credibility

    if hostname.endswith(".gov.vn"):
        return "high"

    if hostname.endswith(".edu.vn"):
        return "medium"

    return "low"


def boost_score_by_credibility(score: float, credibility: str) -> float:
    """Apply credibility boost to a score."""
    return score * CREDIBILITY_BOOST.get(credibility, 1.0)


class HybridSearcher:
    """Hybrid search combining BM25 (keyword) and Vector (semantic) search."""

    # Default cache path — can be overridden via BM25_CACHE_PATH env var
    DEFAULT_CACHE_PATH = Path(__file__).parent.parent.parent.parent / ".cache" / "bm25_index.pkl"

    def __init__(
        self,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
        cache_path: Path = None,
    ):
        self.documents: List[Document] = []
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.bm25_index = None
        self.tokenized_corpus = []
        self._cached_doc_count: int = 0
        self.cache_path = cache_path or Path(
            os.getenv("BM25_CACHE_PATH", str(self.DEFAULT_CACHE_PATH))
        )

    def initialize_from_mongo(self):
        """Load BM25 index from cache or rebuild from MongoDB if data changed."""
        from chatbot_viva.core.mongodb import get_document_count, load_documents_from_mongo

        mongo_count = get_document_count()

        # Try loading cache first
        if self._load_cache():
            if self._cached_doc_count == mongo_count:
                logger.info(
                    "BM25 cache is up-to-date (%d docs), skipping rebuild",
                    mongo_count,
                )
                return
            logger.info(
                "MongoDB doc count changed (%d -> %d), rebuilding BM25 index",
                self._cached_doc_count, mongo_count,
            )

        # Load from MongoDB and rebuild
        self.documents = load_documents_from_mongo()
        self._cached_doc_count = mongo_count
        self._build_bm25_index()
        self._save_cache()

    def _build_bm25_index(self):
        """Build BM25 index from documents."""
        logger.info("Building BM25 index from %d documents...", len(self.documents))
        tokenized_corpus = [
            tokenize_vietnamese(doc.page_content)
            for doc in self.documents
        ]
        self.bm25_index = BM25Okapi(tokenized_corpus)
        # Don't keep tokenized_corpus in memory — BM25Okapi already stores what it needs
        del tokenized_corpus
        logger.info("BM25 index built successfully")

    def _save_cache(self):
        """Save BM25 index and documents to pickle cache."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {
                "documents": self.documents,
                "bm25_index": self.bm25_index,
                "doc_count": self._cached_doc_count,
            }
            with open(self.cache_path, "wb") as f:
                pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info("BM25 cache saved to %s", self.cache_path)
        except Exception as e:
            logger.warning("Failed to save BM25 cache: %s", e)

    def _load_cache(self) -> bool:
        """Load BM25 index from pickle cache. Returns True if loaded."""
        if not self.cache_path.exists():
            logger.info("No BM25 cache found at %s", self.cache_path)
            return False
        try:
            with open(self.cache_path, "rb") as f:
                cache_data = pickle.load(f)
            self.documents = cache_data["documents"]
            self.bm25_index = cache_data["bm25_index"]
            self._cached_doc_count = cache_data.get("doc_count", len(self.documents))
            logger.info(
                "BM25 cache loaded from %s (%d documents)",
                self.cache_path, len(self.documents),
            )
            return True
        except Exception as e:
            logger.warning("Failed to load BM25 cache: %s", e)
            return False

    def bm25_search(self, query: str,
                    k: int = 10) -> List[Tuple[Document, float]]:
        """Search using BM25."""
        if not self.bm25_index or not self.documents:
            return []

        tokenized_query = tokenize_vietnamese(query)
        scores = self.bm25_index.get_scores(tokenized_query)

        doc_scores = list(enumerate(scores))
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        top_k = doc_scores[:k]

        results = []
        for idx, score in top_k:
            if score > 0:
                results.append((self.documents[idx], score))

        return results

    def hybrid_search(
        self,
        query: str,
        vector_results: List[Tuple[Document, float]],
        k: int = 10,
        min_score: float = 0.0,
    ) -> List[SearchResult]:
        """Combine BM25 and vector search results."""
        bm25_results = self.bm25_search(query, k=k * 2)

        vector_scores = self._normalize_scores([s for _, s in vector_results])
        bm25_scores_raw = [s for _, s in bm25_results]
        bm25_scores = self._normalize_scores(bm25_scores_raw)

        vector_dict: Dict[str, Tuple[Document, float]] = {}
        for (doc, _), norm_score in zip(vector_results, vector_scores):
            key = self._doc_key(doc)
            vector_dict[key] = (doc, norm_score)

        bm25_dict: Dict[str, Tuple[Document, float]] = {}
        for (doc, _), norm_score in zip(bm25_results, bm25_scores):
            key = self._doc_key(doc)
            bm25_dict[key] = (doc, norm_score)

        all_keys = set(vector_dict.keys()) | set(bm25_dict.keys())
        combined_results = []

        for key in all_keys:
            vec_score = vector_dict.get(key, (None, 0.0))[1]
            bm25_score = bm25_dict.get(key, (None, 0.0))[1]

            doc = vector_dict.get(key, bm25_dict.get(key))[0]
            if doc is None:
                continue

            combined = (
                self.vector_weight * vec_score +
                self.bm25_weight * bm25_score
            )

            source_url = doc.metadata.get("source_url") or doc.metadata.get("source", "")
            credibility = get_domain_credibility(source_url)
            content_year = doc.metadata.get("year") or extract_year_from_content(
                doc.page_content, source_url)
            boosted_score = boost_score_by_credibility(combined, credibility)
            doc_trang_thai = doc.metadata.get("trang_thai", "")
            boosted_score = boost_score_by_freshness(
                boosted_score, content_year, doc_trang_thai)

            if boosted_score >= min_score:
                combined_results.append(SearchResult(
                    document=doc,
                    vector_score=vec_score,
                    bm25_score=bm25_score,
                    combined_score=boosted_score,
                    source_credibility=credibility,
                    content_year=content_year,
                ))

        combined_results.sort(key=lambda x: x.combined_score, reverse=True)

        return combined_results[:k]

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalize scores to 0-1 range."""
        if not scores:
            return []

        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0

        if max_score == min_score:
            return [1.0] * len(scores)

        return [(s - min_score) / (max_score - min_score) for s in scores]

    def _doc_key(self, doc: Document) -> str:
        """Create unique key for document using content hash."""
        import hashlib
        return hashlib.md5(doc.page_content.encode()).hexdigest()


# Global hybrid searcher instance
_hybrid_searcher: Optional[HybridSearcher] = None


def get_hybrid_searcher() -> HybridSearcher:
    """Get or create global hybrid searcher."""
    global _hybrid_searcher
    if _hybrid_searcher is None:
        _hybrid_searcher = HybridSearcher()
    return _hybrid_searcher


def init_hybrid_searcher() -> HybridSearcher:
    """Initialize hybrid searcher from MongoDB with cache support."""
    global _hybrid_searcher
    _hybrid_searcher = HybridSearcher()
    _hybrid_searcher.initialize_from_mongo()
    return _hybrid_searcher
