"""Agent tools: legal search, comparable search."""

# Lazy imports to avoid circular dependency:
# tools → quality → retrieval → tools
__all__ = [
    "search_comparable_properties",
    "legal_web_search",
    "postprocess_citations",
]


def search_comparable_properties(*args, **kwargs):
    from .comparable_search import search_comparable_properties as _search
    return _search(*args, **kwargs)
