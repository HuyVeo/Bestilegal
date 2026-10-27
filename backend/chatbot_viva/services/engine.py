"""Chatbot engine — initializes vectorstore retriever and hybrid search."""

import threading
import logging

from chatbot_viva.retrieval.vector_store import (
    get_retriever, _check_collection_exists, CollectionCheckError,
)
from chatbot_viva.retrieval.hybrid_search import init_hybrid_searcher

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Chatbot initialiser (cached in module-level variable)
# ──────────────────────────────────────────────
_init_lock = threading.Lock()   # Ensures only ONE thread runs initialization
_init_done = threading.Event()  # Signals all waiting threads when init is complete


def initialize_chatbot_flask():
    """
    Initialize the chatbot for use with Flask (no Streamlit cache).
    Thread-safe: only one thread performs initialization; all others
    block on _init_done until the initialization is ready.
    """
    # Try to become the initializer (non-blocking acquire)
    if not _init_lock.acquire(blocking=False):
        # Another thread is already initializing — wait with timeout
        logger.info("Waiting for ongoing initialization to complete...")
        if not _init_done.wait(timeout=3600):
            raise TimeoutError("Chatbot initialization timed out after 3600s")
        return

    # We hold the lock
    try:
        # Check Qdrant collection exists
        try:
            collection_ready = _check_collection_exists()
        except CollectionCheckError as e:
            logger.error("Qdrant unreachable: %s — assuming collection exists", e)
            collection_ready = True

        if collection_ready:
            logger.info("Vector store collection found, loading retriever")
            get_retriever()
        else:
            logger.error(
                "No Qdrant collection found. "
                "Please run the embedding pipeline to create the collection first."
            )

        # Initialize BM25 hybrid search from MongoDB (with cache)
        try:
            init_hybrid_searcher()
            logger.info("Hybrid search initialized")
        except Exception as e:
            logger.warning("Could not initialize BM25 hybrid search (non-critical): %s", e)

        logger.info("Chatbot initialization complete")

    finally:
        _init_done.set()
        _init_lock.release()
