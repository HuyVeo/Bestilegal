"""Vector store management for semantic search using Qdrant."""

import logging
import threading
from typing import Optional
from functools import lru_cache
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from chatbot_viva.core import config

logger = logging.getLogger(__name__)

# Module-level singleton — avoids re-opening the Qdrant client on every call
_vectorstore_instance: Optional[QdrantVectorStore] = None
_vectorstore_lock = threading.Lock()


class CollectionCheckError(Exception):
    """Raised when we cannot determine if the collection exists (connection error)."""


def _check_collection_exists() -> bool:
    """
    Check if the Qdrant collection already exists.

    Returns:
        True if collection exists, False if it doesn't.

    Raises:
        CollectionCheckError: If Qdrant is unreachable (so caller can
        distinguish "not exists" from "cannot connect").
    """
    try:
        if config.QDRANT_URL:
            client = QdrantClient(
                url=config.QDRANT_URL,
                api_key=config.QDRANT_API_KEY,
            )
        else:
            # Check if local storage path exists
            if not config.VECTORSTORE_PATH.exists():
                return False
            client = QdrantClient(path=str(config.VECTORSTORE_PATH))

        # Try to get collection info
        collections = client.get_collections()
        collection_names = [col.name for col in collections.collections]
        return config.VECTORSTORE_COLLECTION_NAME in collection_names

    except (ConnectionError, TimeoutError, OSError) as e:
        raise CollectionCheckError(f"Cannot connect to Qdrant: {e}") from e
    except Exception as e:
        # Other Qdrant errors (auth, permission) — also a connection issue
        raise CollectionCheckError(f"Qdrant check failed: {e}") from e


@lru_cache(maxsize=1)
def _get_embeddings():
    """
    Get embeddings model (cached).
    Always uses OpenAI embeddings for Qdrant compatibility.
    """
    from langchain_openai import OpenAIEmbeddings
    model = config.EMBEDDING_MODEL or "text-embedding-3-small"
    # Override gemini embedding model — Qdrant collection uses OpenAI dimensions
    if "gemini" in model:
        model = "text-embedding-3-small"
    logger.info("Using OpenAI embeddings: %s", model)
    return OpenAIEmbeddings(
        model=model,
        openai_api_key=config.OPENAI_API_KEY,
    )



def get_vectorstore() -> QdrantVectorStore:
    """
    Get existing Qdrant vector store without documents.
    Returns the cached singleton if already opened in this process.
    Thread-safe via double-checked locking.

    Returns:
        QdrantVectorStore instance.
    """
    global _vectorstore_instance

    if _vectorstore_instance is not None:
        return _vectorstore_instance

    with _vectorstore_lock:
        if _vectorstore_instance is not None:
            return _vectorstore_instance

        embeddings = _get_embeddings()

        if config.QDRANT_URL:
            vectorstore = QdrantVectorStore.from_existing_collection(
                embedding=embeddings,
                collection_name=config.VECTORSTORE_COLLECTION_NAME,
                url=config.QDRANT_URL,
                api_key=config.QDRANT_API_KEY,
            )
        else:
            vectorstore = QdrantVectorStore.from_existing_collection(
                embedding=embeddings,
                collection_name=config.VECTORSTORE_COLLECTION_NAME,
                path=str(config.VECTORSTORE_PATH),
            )

        _vectorstore_instance = vectorstore
        return vectorstore


def get_retriever(
    vectorstore: Optional[QdrantVectorStore] = None,
    k: int = None,
) -> VectorStoreRetriever:
    """
    Get a retriever from the vector store.

    Args:
        vectorstore: Existing vector store. If None, loads from Qdrant.
        k: Number of documents to retrieve. Defaults to config.RETRIEVER_K.

    Returns:
        VectorStoreRetriever instance.
    """
    if k is None:
        k = config.RETRIEVER_K
    if vectorstore is None:
        vectorstore = get_vectorstore()
    return vectorstore.as_retriever(search_kwargs={"k": k})
