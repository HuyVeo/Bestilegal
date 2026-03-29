"""Retrieval layer: vector store, hybrid search, reranker, metadata filtering."""

__all__ = [
    "get_vectorstore",
    "get_retriever",
    "HybridSearcher",
    "get_hybrid_searcher",
    "init_hybrid_searcher",
    "get_domain_credibility",
    "get_reranker",
    "enrich_documents_batch",
    "filter_documents",
    "boost_by_metadata",
]


def __getattr__(name):
    if name in ("get_vectorstore", "get_retriever"):
        from .vector_store import get_vectorstore, get_retriever
        return locals()[name]
    if name in ("HybridSearcher", "get_hybrid_searcher", "init_hybrid_searcher",
                "get_domain_credibility"):
        from .hybrid_search import (
            HybridSearcher, get_hybrid_searcher, init_hybrid_searcher,
            get_domain_credibility,
        )
        return locals()[name]
    if name == "get_reranker":
        from .reranker import get_reranker
        return get_reranker
    if name in ("enrich_documents_batch", "filter_documents", "boost_by_metadata"):
        from .metadata_filter import (
            enrich_documents_batch, filter_documents, boost_by_metadata,
        )
        return locals()[name]
    raise AttributeError(f"module 'chatbot_viva.retrieval' has no attribute {name!r}")
