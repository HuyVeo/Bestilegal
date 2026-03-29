"""Utilities for searching comparable properties on the web."""

from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel

from chatbot_viva.core import config
from chatbot_viva.tools.tavily_utils import safe_tavily_search

PRICE_PATTERN = re.compile(
    r"(?P<value>\d[\d.,]*)\s*(?P<unit>t(?:ỷ|y)|ty|tỉ|tr(?:iệu|ieu)?)",
    re.IGNORECASE,
)
AREA_PATTERN = re.compile(
    r"(?P<value>\d[\d.,]*)\s*(?:m2|m\u00b2|mét vu\u00f4ng|met vuong|m2)",
    re.IGNORECASE,
)


class ComparableProperty(BaseModel):
    """Structured representation of a comparable property listing."""

    title: str
    summary: str
    url: Optional[str] = None
    source: Optional[str] = None
    price_billion: Optional[float] = None  # price in billion VND
    area_sqm: Optional[float] = None


def _normalize_number(value: str) -> Optional[float]:
    """Normalize Vietnamese number format: '.' as thousands, ',' as decimal.

    Examples: "1.000" → 1000, "1.000,5" → 1000.5, "3,5" → 3.5, "500" → 500
    """
    try:
        if "," in value and "." in value:
            # "1.000,50" → remove '.' (thousands), replace ',' with '.' (decimal)
            return float(value.replace(".", "").replace(",", "."))
        elif "," in value:
            # "3,5" → replace ',' with '.' (decimal)
            return float(value.replace(",", "."))
        elif "." in value:
            # Ambiguous: could be "1.000" (thousands) or "3.5" (decimal)
            # If ALL groups after first '.' have exactly 3 digits → thousands separator
            parts = value.split(".")
            if len(parts) >= 2 and all(len(p) == 3 for p in parts[1:]):
                return float(value.replace(".", ""))  # thousands separator
            if len(parts) == 2:
                return float(value)  # decimal point
            return float(value.replace(".", ""))  # fallback: remove dots
        return float(value)
    except ValueError:
        return None


def _extract_price_billion(text: str) -> Optional[float]:
    match = PRICE_PATTERN.search(text.lower())
    if not match:
        return None
    raw_value = _normalize_number(match.group("value"))
    if raw_value is None:
        return None
    unit = match.group("unit").lower()
    if unit.startswith("tr"):
        return raw_value / 1000  # convert million to billion
    return raw_value


def _extract_area(text: str) -> Optional[float]:
    match = AREA_PATTERN.search(text.lower())
    if not match:
        return None
    return _normalize_number(match.group("value"))


def search_comparable_properties(
    location: str,
    property_type: str = "",
    question_context: str = "",
    max_results: int = 5,
) -> List[ComparableProperty]:
    """Search Tavily for comparable properties near the provided location."""
    if not config.TAVILY_API_KEY:
        return []

    query_parts = [
        "giá bất động sản",
        location.strip(),
        property_type.strip(),
        question_context.strip(),
    ]
    query = " ".join(part for part in query_parts if part).strip()

    results = safe_tavily_search(
        query,
        max_results=max_results,
        include_raw_content=False,
        search_depth="basic",
    )
    if not results:
        return []

    comparables: List[ComparableProperty] = []

    for item in results:
        title = (item.get("title") or "").strip()
        summary = (item.get("content") or item.get("snippet") or "").strip()
        url = item.get("url")
        source = item.get("source")
        text_blob = f"{title} {summary}"

        comp = ComparableProperty(
            title=title or (location.strip() or "Tin rao"),
            summary=summary or "Chưa có mô tả chi tiết.",
            url=url,
            source=source,
            price_billion=_extract_price_billion(text_blob),
            area_sqm=_extract_area(text_blob),
        )
        comparables.append(comp)

    return comparables
