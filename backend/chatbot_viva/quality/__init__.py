"""Quality control: source reliability scoring, snippet ranking."""

# Lazy imports to avoid circular dependency chain
__all__ = [
    "get_reliability_scorer",
    "get_ranking_engine",
]


def get_reliability_scorer():
    from .source_reliability import get_reliability_scorer as _get
    return _get()


def get_ranking_engine():
    from .snippet_ranking import get_ranking_engine as _get
    return _get()
