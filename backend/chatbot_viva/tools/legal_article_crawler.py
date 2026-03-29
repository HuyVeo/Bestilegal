"""
Legal Article Crawler — crawl hethongphapluat.vn to enrich legal_basis items
that were extracted from LLM output (from_response=True, content="").

Usage in main.py (2 lines):
    from chatbot_viva.tools.legal_article_crawler import enrich_legal_basis
    legal_basis = enrich_legal_basis(legal_basis)
"""

import logging
import re
import time
import concurrent.futures
from typing import List, Dict, Optional

from chatbot_viva.core import config

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# In-memory cache — auto-expire after 5 minutes (no external deps)
# ════════════════════════════════════════════════════════════════
_cache: Dict[str, dict] = {}
_CACHE_TTL = 300  # seconds


def _cache_key(document_name: str, article: str) -> str:
    return f"{document_name.strip().lower()}|{article.strip().lower()}"


def _cache_get(key: str) -> Optional[dict]:
    entry = _cache.get(key)
    if entry is None:
        return None
    if time.time() - entry["_ts"] > _CACHE_TTL:
        _cache.pop(key, None)
        return None
    return entry


def _cache_set(key: str, value: dict) -> None:
    # Evict expired entries if cache is large
    if len(_cache) > 200:
        now = time.time()
        expired = [k for k, v in _cache.items() if now - v["_ts"] > _CACHE_TTL]
        for k in expired:
            _cache.pop(k, None)
    value["_ts"] = time.time()
    _cache[key] = value


# ════════════════════════════════════════════════════════════════
# Crawl a single legal reference from hethongphapluat.vn
# ════════════════════════════════════════════════════════════════

def _crawl_one(ref: Dict) -> Dict:
    """
    Search hethongphapluat.vn via Tavily for a specific legal reference,
    extract the relevant article section, and return the enriched ref dict.
    """
    document_name = ref.get("document_name", "").strip()
    article = ref.get("article", "").strip()

    if not document_name:
        return ref

    # Check cache first
    key = _cache_key(document_name, article)
    cached = _cache_get(key)
    if cached is not None:
        ref["content"] = cached["content"]
        ref["crawl_url"] = cached.get("url", "")
        ref["crawl_title"] = cached.get("title", "")
        return ref

    # Build search query
    query_parts = [document_name]
    if article:
        query_parts.append(article)
    query = " ".join(query_parts)

    logger.info("[CRAWL] Searching: \"%s\"", query)

    from chatbot_viva.tools.tavily_utils import safe_tavily_search
    results = safe_tavily_search(
        f"site:hethongphapluat.vn {query}",
        max_results=3,
    )

    if not results:
        logger.warning("[CRAWL] No results for \"%s\"", query)
        return ref

    # Pick best result — prefer one that mentions the article number
    best = results[0]
    if article:
        art_num_match = re.search(r'\d+', article)
        if art_num_match:
            art_num = art_num_match.group()
            for r in results:
                title = (r.get("title") or "").lower()
                if art_num in title:
                    best = r
                    break

    raw = best.get("raw_content") or best.get("content") or ""
    url = best.get("url") or ""
    title = best.get("title") or ""

    # Extract the relevant Điều section
    content = _extract_article_section(raw, article) if article else raw[:3000]

    if content:
        ref["content"] = content
        ref["crawl_url"] = url
        ref["crawl_title"] = title

        # Save to cache
        _cache_set(key, {"content": content, "url": url, "title": title})
        logger.info("[CRAWL] Got %d chars for %s %s", len(content), document_name, article)
    else:
        logger.warning("[CRAWL] Could not extract content for \"%s\"", query)

    return ref


def _extract_article_section(raw_content: str, article: str) -> str:
    """Extract the specific Điều section from raw page content."""
    if not raw_content or not article:
        return raw_content[:3000] if raw_content else ""

    art_num_match = re.search(r'\d+[a-zđ]?', article)
    if not art_num_match:
        return raw_content[:3000]

    art_num = art_num_match.group()

    # Find "Điều {num}" in content
    pattern = re.compile(
        rf'(Điều\s+{re.escape(art_num)}[\.\s:][^\n]*\n)',
        re.IGNORECASE,
    )
    match = pattern.search(raw_content)
    if not match:
        return raw_content[:3000]

    start = match.start()

    # Find next "Điều" to delimit the section
    next_article = re.search(
        rf'(?:^|\n)(Điều\s+(?!{re.escape(art_num)}[\.\s:])\d+)',
        raw_content[match.end():],
        re.IGNORECASE,
    )
    if next_article:
        end = match.end() + next_article.start()
    else:
        end = min(start + 5000, len(raw_content))

    return raw_content[start:end].strip()


# ════════════════════════════════════════════════════════════════
# Public API — the only function main.py needs to call
# ════════════════════════════════════════════════════════════════

def enrich_legal_basis(legal_basis: List[Dict]) -> List[Dict]:
    """
    Enrich legal_basis items that have from_response=True and empty content
    by crawling hethongphapluat.vn.

    Crawls in parallel (max 4 workers) to minimize latency.
    Items that already have content are left untouched.

    Args:
        legal_basis: List of legal basis dicts from the pipeline.

    Returns:
        The same list with content filled in where possible.
    """
    # Find items that need enrichment
    to_enrich = [
        ref for ref in legal_basis
        if ref.get("from_response") and not ref.get("content")
    ]

    if not to_enrich:
        return legal_basis

    logger.info("[ENRICH] Enriching %d legal refs from hethongphapluat.vn...", len(to_enrich))
    t0 = time.perf_counter()

    # Crawl in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(to_enrich))) as executor:
        futures = {executor.submit(_crawl_one, ref): ref for ref in to_enrich}
        try:
            for future in concurrent.futures.as_completed(futures, timeout=45):
                try:
                    future.result()
                except Exception as e:
                    ref = futures[future]
                    logger.warning("[ENRICH] Failed for %s: %s", ref.get('document_name'), e)
        except concurrent.futures.TimeoutError:
            not_done = [f for f in futures if not f.done()]
            logger.warning("[ENRICH] %d crawl(s) timed out — skipping", len(not_done))
            for f in not_done:
                f.cancel()

    enriched_count = sum(1 for ref in to_enrich if ref.get("content"))
    elapsed = time.perf_counter() - t0
    logger.info("[ENRICH] Done: %d/%d enriched (%.2fs)", enriched_count, len(to_enrich), elapsed)

    return legal_basis
