"""
RAG Data Models — Shared dataclasses cho RAG pipeline.

Single Responsibility: Chỉ chứa data structures, không có logic.
Extracted from rag_service.py để tránh circular imports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LegalArticle:
    """A legal article extracted from RAG results."""

    point_id: str
    document_name: str
    article: str
    clause: str
    content: str
    snippet: str
    score: float
    source_file: str = ""
    loai_van_ban: str = ""
    so_hieu: str = ""
    trang_thai: str = ""
    co_quan_ban_hanh: str = ""
    ten_dieu: str = ""
    source_url: str = ""


@dataclass
class WebResult:
    """A web search result."""

    url: str
    title: str
    domain: str
    snippet: str
    reliability: float
    publish_date: Optional[str]


@dataclass
class RAGResponse:
    """Complete RAG response with separated sources."""

    rag_context: str
    legal_basis: List[LegalArticle]
    web_results: List[WebResult]
    rag_sources_count: int
    web_sources_count: int
