"""
Dynamic Re-Ranking Engine.

Upgrades from rule-based snippet ranking to LLM-based reranking.
Supports multiple backends:
1. LLM-based reranking (OpenAI / Anthropic / Gemini) - always available
2. Cross-encoder reranking (if sentence-transformers installed) - optional
"""

import json
import logging
import re
from typing import List, Tuple, Optional
from dataclasses import dataclass
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """A single reranked document with its score."""
    document: Document
    relevance_score: float  # 0-1, LLM-assigned
    reasoning: str  # Why this score
    original_rank: int  # Position before reranking


def _build_rerank_prompt(query: str,
                         documents: List[Tuple[Document,
                                               float]],
                         batch_size: int = 10) -> str:
    """Build a prompt to score document relevance in batch."""
    docs_block = []
    for i, (doc, orig_score) in enumerate(documents[:batch_size]):
        content = doc.page_content.strip()
        if len(content) > 600:
            content = content[:600] + "..."
        source = doc.metadata.get("source_file") or doc.metadata.get("source", "unknown")
        docs_block.append(f"[DOC_{i+1}] (source: {source})\n{content}")

    docs_text = "\n\n---\n\n".join(docs_block)

    return (
        "Bạn là chuyên gia đánh giá độ liên quan tài liệu.\n"
        "Nhiệm vụ: Cho điểm từ 0.0 đến 1.0 cho mỗi tài liệu dựa trên mức độ liên quan với câu hỏi.\n\n"
        "Tiêu chí chấm điểm:\n"
        "- 0.9-1.0: Trả lời trực tiếp, đầy đủ câu hỏi\n"
        "- 0.7-0.8: Liên quan chặt chẽ, chứa thông tin hữu ích\n"
        "- 0.4-0.6: Liên quan một phần, có context phụ trợ\n"
        "- 0.1-0.3: Liên quan rất ít\n"
        "- 0.0: Hoàn toàn không liên quan\n\n"
        f"CÂU HỎI: {query}\n\n"
        f"CÁC TÀI LIỆU:\n{docs_text}\n\n"
        "Trả lời đúng JSON array, không thêm nội dung khác:\n"
        "[\n"
        '  {"doc_id": "DOC_1", "score": 0.85, "reason": "lý do ngắn"},\n'
        '  {"doc_id": "DOC_2", "score": 0.30, "reason": "lý do ngắn"}\n'
        "]")


class LLMReranker:
    """Re-ranks documents using LLM scoring."""

    def __init__(self, llm=None):
        self._llm = llm

    def _get_llm(self):
        """Lazy-load LLM."""
        if self._llm is None:
            try:
                from chatbot_viva.llm.factory import get_llm_factory
                factory = get_llm_factory()
                self._llm = factory.create(task="grade", temperature=0)
            except Exception:
                from langchain_openai import ChatOpenAI
                from chatbot_viva.core import config
                self._llm = ChatOpenAI(
                    model=config.LLM_MODEL,
                    temperature=0,
                    api_key=config.OPENAI_API_KEY,
                )
        return self._llm

    def rerank(
        self,
        query: str,
        documents: List[Tuple[Document, float]],
        top_k: int = 4,
        min_score: float = 0.3,
    ) -> List[RerankResult]:
        """Rerank documents using LLM scoring."""
        if not documents:
            return []

        # Skip LLM call hoàn toàn nếu ít docs (tránh init LLM lãng phí)
        if len(documents) <= 2:
            return [
                RerankResult(
                    document=doc,
                    relevance_score=score,
                    reasoning="few docs, skip rerank",
                    original_rank=i,
                )
                for i, (doc, score) in enumerate(documents)
            ]

        llm = self._get_llm()

        all_results = []
        # Tăng batch size: giảm số lần gọi LLM (10 docs = 1 call thay vì 2)
        batch_size = 10

        for batch_start in range(0, len(documents), batch_size):
            batch = documents[batch_start:batch_start + batch_size]
            batch_results = self._rerank_batch(
                query, batch, llm, batch_start
            )
            all_results.extend(batch_results)

        filtered = [r for r in all_results if r.relevance_score >= min_score]
        filtered.sort(key=lambda r: r.relevance_score, reverse=True)

        return filtered[:top_k]

    def _rerank_batch(
        self,
        query: str,
        batch: List[Tuple[Document, float]],
        llm,
        offset: int,
    ) -> List[RerankResult]:
        """Score a batch of documents."""
        prompt = _build_rerank_prompt(query, batch)

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            raw = response.content.strip()

            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            scores = json.loads(raw)

            results = []
            for i, (doc, orig_score) in enumerate(batch):
                doc_id = f"DOC_{i+1}"
                score_entry = next(
                    (s for s in scores if s.get("doc_id") == doc_id),
                    None,
                )
                if score_entry:
                    llm_score = float(score_entry.get("score", 0))
                    reason = score_entry.get("reason", "")
                else:
                    llm_score = orig_score
                    reason = "LLM did not score this doc"

                results.append(RerankResult(
                    document=doc,
                    relevance_score=llm_score,
                    reasoning=reason,
                    original_rank=offset + i,
                ))

            return results

        except Exception as e:
            logger.warning(
                "LLM reranking failed: %s. Using original scores.",
                e,
            )
            return [
                RerankResult(
                    document=doc,
                    relevance_score=score,
                    reasoning=f"fallback (rerank error: {e})",
                    original_rank=offset + i,
                )
                for i, (doc, score) in enumerate(batch)
            ]


from chatbot_viva.core.singleton import singleton


@singleton
def get_reranker() -> LLMReranker:
    """Get or create the global LLMReranker singleton."""
    return LLMReranker()
