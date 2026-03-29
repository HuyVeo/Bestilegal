"""Tavily web search utilities."""

import json
import logging
from typing import List

logger = logging.getLogger(__name__)


def safe_tavily_search(
    query: str,
    *,
    max_results: int = 3,
    include_raw_content: bool = True,
    search_depth: str = "advanced",
    api_key: str | None = None,
) -> List[dict]:
    """
    Invoke Tavily search and always return a list of dicts.

    Handles all known failure modes:
    - langchain_tavily.TavilySearch returning dict with 'error' key
    - langchain_community.TavilySearchResults returning a JSON string
    - API errors (432 quota, network errors, etc.)

    Returns:
        list[dict] — each dict has at least 'url', 'title', 'content' keys.
        Returns [] on any error.
    """
    if api_key is None:
        from chatbot_viva.core import config
        api_key = config.TAVILY_API_KEY

    # Try new langchain_tavily first, fallback to langchain_community
    try:
        from langchain_tavily import TavilySearch
        tavily = TavilySearch(
            max_results=max_results,
            tavily_api_key=api_key,
            include_raw_content=include_raw_content,
            search_depth=search_depth,
        )
    except ImportError:
        from langchain_community.tools.tavily_search import TavilySearchResults
        tavily = TavilySearchResults(
            max_results=max_results,
            api_key=api_key,
            include_raw_content=include_raw_content,
            search_depth=search_depth,
        )

    try:
        results = tavily.invoke(query)
    except Exception as e:
        logger.warning("[TAVILY] invoke failed: %s", e)
        return []

    return _normalize_tavily_results(results)


def _normalize_tavily_results(results) -> List[dict]:
    """Normalize Tavily output into a list of dicts, regardless of format."""
    # Case 1: already a list
    if isinstance(results, list):
        return [r for r in results if isinstance(r, dict)]

    # Case 2: dict — new TavilySearch may return {"error": ...} or a single result
    if isinstance(results, dict):
        if "error" in results:
            logger.warning("[TAVILY] API error: %s", results['error'])
            return []
        # Some versions wrap results in {"results": [...]}
        if "results" in results and isinstance(results["results"], list):
            return [r for r in results["results"] if isinstance(r, dict)]
        # Single result dict with 'url' key
        if "url" in results:
            return [results]
        return []

    # Case 3: string — deprecated TavilySearchResults returns JSON string or error string
    if isinstance(results, str):
        # Try parsing as JSON
        try:
            parsed = json.loads(results)
            return _normalize_tavily_results(parsed)
        except (json.JSONDecodeError, TypeError):
            pass
        logger.warning("[TAVILY] returned string: %s", results[:150])
        return []

    logger.warning("[TAVILY] unexpected type: %s", type(results))
    return []
