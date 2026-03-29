"""Legal web fetcher — query expansion and parallel Tavily fetch with filtering."""

import logging
import re
import time
import concurrent.futures
from datetime import datetime
from typing import List

import pytz

from chatbot_viva.core import config
from chatbot_viva.tools.tavily_utils import safe_tavily_search
from chatbot_viva.quality.source_reliability import (
    get_reliability_scorer,
    is_source_blocked,
)

logger = logging.getLogger(__name__)

# Legal reference pattern for query expansion
_LEGAL_REF_RE = re.compile(
    r'(?:Luật|Nghị\s*định|Thông\s*tư|Bộ\s*luật|Điều)\s+\d+',
    re.IGNORECASE,
)

# Max pages to keep after dedup + filter
_TARGET_PAGES = config.LEGAL_WEB_TARGET_PAGES
_RAW_PER_QUERY = config.LEGAL_WEB_RAW_PER_QUERY


class LegalQueryExpander:
    """Generate sub-queries to catch amendments and implementation decrees."""

    def expand(self, query: str, needs_realtime: bool = False) -> List[str]:
        try:
            vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
            now = datetime.now(vn_tz)
        except Exception:
            now = datetime.now()

        year = now.year
        date_str = now.strftime("%d/%m/%Y")

        if needs_realtime:
            queries = [f"{query} {date_str}"]
        else:
            queries = [query]

        if not _LEGAL_REF_RE.search(query):
            return queries

        try:
            vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
            year = datetime.now(vn_tz).year
        except Exception:
            year = datetime.now().year

        queries.append(f"{query} sửa đổi bổ sung mới nhất {year}")
        queries.append(f"{query} hướng dẫn thi hành nghị định thông tư")

        return queries


# ── Singleton scorer ──
_reliability_scorer = None


def _get_scorer():
    global _reliability_scorer
    if _reliability_scorer is None:
        _reliability_scorer = get_reliability_scorer()
    return _reliability_scorer


def _fetch_single_query(query: str) -> list:
    """Fetch results for a single query via Tavily."""
    return safe_tavily_search(
        query,
        max_results=_RAW_PER_QUERY,
        include_raw_content=True,
        search_depth="basic",
    )


def fetch_legal_pages(queries: List[str]) -> List[dict]:
    """
    Fetch web pages for multiple queries in parallel.
    Dedup by URL, filter blocked/low-reliability, keep top N.
    """
    t0 = time.perf_counter()
    logger.info("Fetching pages for %d queries", len(queries))

    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_fetch_single_query, q): q for q in queries}
        for future in concurrent.futures.as_completed(futures):
            results = future.result()
            if isinstance(results, list):
                all_results.extend(results)

    logger.info("Raw results: %d (from %d queries)", len(all_results), len(queries))

    # Dedup by URL
    seen_urls = set()
    unique_results = []
    for r in all_results:
        if not isinstance(r, dict):
            continue
        url = r.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique_results.append(r)

    # Filter blocked + low reliability
    scorer = _get_scorer()
    filtered = []
    blocked_count = 0

    for r in unique_results:
        url = r.get("url", "")
        blocked, reason = is_source_blocked(url)
        if blocked:
            blocked_count += 1
            continue
        reliability = scorer.get_reliability_score(url)
        if reliability < 0.4:
            blocked_count += 1
            continue
        r["reliability"] = reliability
        filtered.append(r)

    filtered.sort(key=lambda x: x.get("reliability", 0), reverse=True)
    pages = filtered[:_TARGET_PAGES]

    elapsed = time.perf_counter() - t0
    logger.info("Kept %d pages (blocked/low: %d) in %.2fs", len(pages), blocked_count, elapsed)

    return pages
