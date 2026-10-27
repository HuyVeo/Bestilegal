"""MongoDB client for loading documents from MongoDB Atlas."""

import logging
from typing import List, Optional

from pymongo import MongoClient
from langchain_core.documents import Document

from chatbot_viva.core import config

logger = logging.getLogger(__name__)

_client: Optional[MongoClient] = None


def get_mongo_client() -> MongoClient:
    """Get or create MongoDB client singleton."""
    global _client
    if _client is None:
        _client = MongoClient(config.MONGODB_URI)
        logger.info("MongoDB client connected")
    return _client


def get_collection():
    """Get the configured MongoDB collection."""
    client = get_mongo_client()
    db = client[config.MONGODB_DB_NAME]
    return db[config.MONGODB_COLLECTION_NAME]


def get_document_count() -> int:
    """Get total document count for change detection."""
    collection = get_collection()
    return collection.estimated_document_count()


def _build_article_text(doc_meta: dict, article: dict) -> str:
    """Build enriched text for a single article (điều luật).

    Format: [loại văn bản] số [số hiệu] - Điều [số]. [tiêu đề]. Nội dung: [nội dung]
    """
    loai = doc_meta.get("loai_van_ban", "")
    so_hieu = doc_meta.get("so_hieu", "")
    dieu = article.get("dieu", "")
    tieu_de = article.get("tieu_de", "")
    noi_dung = article.get("noi_dung", "")

    header = f"{loai} số {so_hieu}" if loai and so_hieu else (loai or so_hieu or "")
    dieu_label = f"Điều {dieu}. {tieu_de}" if dieu else tieu_de

    if header and dieu_label:
        return f"{header} - {dieu_label}. Nội dung chi tiết: {noi_dung}"
    elif dieu_label:
        return f"{dieu_label}. Nội dung chi tiết: {noi_dung}"
    return noi_dung


def load_documents_from_mongo() -> List[Document]:
    """Load all documents from MongoDB and convert to LangChain Documents.

    Each MongoDB document has:
    - content: list of articles [{dieu, tieu_de, noi_dung}, ...]
    - Other fields: metadata (loai_van_ban, so_hieu, trang_thai, etc.)

    Each article becomes a separate LangChain Document.
    """
    collection = get_collection()
    mongo_docs = list(collection.find())
    logger.info("Loaded %d raw documents from MongoDB", len(mongo_docs))

    # Fields that are metadata (not content)
    meta_fields = {
        "loai_van_ban", "title", "so_hieu", "source",
        "ngay_ban_hanh", "ngay_hieu_luc", "ngay_cong_bao",
        "so_cong_bao", "nguoi_ky", "trang_thai", "co_quan_ban_hanh",
    }

    documents = []
    for doc in mongo_docs:
        # Build shared metadata for this document
        metadata = {}
        for key in meta_fields:
            if key in doc and doc[key]:
                metadata[key] = doc[key]

        content = doc.get("content")

        # content is a list of articles — flatten each into a Document
        if isinstance(content, list):
            for article in content:
                if not isinstance(article, dict):
                    continue
                noi_dung = article.get("noi_dung", "")
                if not noi_dung:
                    continue

                text = _build_article_text(metadata, article)
                article_meta = {
                    **metadata,
                    "dieu_so": article.get("dieu", ""),
                    "ten_dieu": article.get("tieu_de", ""),
                }
                documents.append(Document(page_content=text, metadata=article_meta))

        # content is a plain string
        elif isinstance(content, str) and content.strip():
            documents.append(Document(page_content=content, metadata=metadata))

    logger.info("Converted to %d LangChain Documents (articles)", len(documents))
    return documents
