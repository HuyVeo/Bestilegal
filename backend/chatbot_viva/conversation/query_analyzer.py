"""
Query Analyzer — Single LLM call to understand, classify, and decide next action.

Replaces:
  - rewrite_query() in context.py
  - is_legal_or_admin_question() in classifier.py
  - classify_question() in classifier.py

Outputs:
  - action: search | clarify | greeting
  - response_style: advice | legal | news_data | general
  - needs_realtime: bool
  - search_query: clean optimized query
"""

import hashlib
import json
import logging

logger = logging.getLogger(__name__)
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from langchain_core.messages import HumanMessage


@dataclass
class AnalysisResult:
    """Output of query analysis."""
    action: str                   # "search" | "clarify" | "greeting"
    search_query: str             # Clean query for search (action=search)
    category: str                 # "legal" | "general" — controls search pipeline
    response_style: str           # "advice" | "legal" | "news_data" | "general" — controls prompt
    needs_realtime: bool          # True = cần dữ liệu mới nhất
    clarify_question: str         # Follow-up question (action=clarify)
    greeting_response: str        # Direct response (action=greeting)
    key_entities: List[str]       # Extracted entities
    reasoning: str                # Brief reasoning for the decision
    raw_response: str             # Raw LLM response for debugging


_SYSTEM_PROMPT = """Bạn là Query Analyzer cho chatbot tư vấn bất động sản Việt Nam.

NHIỆM VỤ: Phân tích câu hỏi + lịch sử hội thoại → quyết định hành động.

═══ BƯỚC 1: ĐỌC KỸ LỊCH SỬ HỘI THOẠI ═══

QUAN TRỌNG: Lịch sử hội thoại chứa thông tin user đã cung cấp trước đó.
- Nếu user đã nói "tôi có 1 tỉ, muốn mua nhà 6 tỉ" ở lượt trước → bạn ĐÃ BIẾT thông tin này.
- Nếu user nói "tôi muốn vay ngân hàng" → kết hợp với context trước (mua nhà 6 tỉ) → hiểu ngay.
- KHÔNG hỏi lại thông tin đã có trong lịch sử.

═══ BƯỚC 2: CHỌN ACTION ═══

ACTION "search" (MẶC ĐỊNH — ưu tiên search hơn clarify):
Dùng khi câu hỏi ĐỦ để tìm kiếm. Hầu hết câu hỏi đều đủ rõ.

QUY TẮC VIẾT LẠI QUERY:
- Gộp thông tin quan trọng từ LỊCH SỬ vào query nếu liên quan trực tiếp.
  VD: User trước hỏi "mua nhà 6 tỉ", giờ hỏi "vay ngân hàng" → query = "vay ngân hàng mua nhà 6 tỷ đồng"
- KHÔNG thêm thông tin từ chủ đề CŨ nếu user đang hỏi chủ đề MỚI.
- Giữ query ngắn gọn, tập trung.

SUY LUẬN THỜI GIAN — BẮT BUỘC:
- Nếu user nói "2 năm gần đây" → tính: năm hiện tại là 2026, vậy = từ 2024 đến 2026.
  → Query: "giá vàng 2024 2025 2026 biến động" (KHÔNG hỏi lại "khoảng thời gian nào")
- "gần đây" = 1-2 năm. "mấy năm qua" = 3-5 năm. "hôm nay" = ngày hiện tại.
- Luôn chuyển thời gian tương đối thành MỐC CỤ THỂ trong search_query.

ACTION "clarify" (RẤT HIẾM KHI DÙNG):
CHỈ dùng khi THỰC SỰ không thể search được:
- "cái đó thì sao" mà lịch sử KHÔNG có context nào
- Câu 1-2 từ mơ hồ không rõ ý: "vậy à", "thêm đi"

KHÔNG dùng clarify khi:
- User đã cung cấp đủ thông tin qua nhiều lượt chat
- Câu hỏi ngắn nhưng rõ ý: "có nên không", "phù hợp không", "cần làm gì"
- Có thể suy luận từ lịch sử hội thoại

ACTION "greeting":
CHỈ khi HOÀN TOÀN là chào hỏi, cảm ơn, tạm biệt.

═══ BƯỚC 3: XÁC ĐỊNH response_style ═══

"advice" — Câu hỏi TƯ VẤN, xin ý kiến, quyết định:
  VD: "có nên mua?", "phù hợp không?", "nên đầu tư ở đâu?", "vay bao nhiêu hợp lý?"
  → LLM cần: logic + tính toán + kết luận rõ ràng

"legal" — Câu hỏi PHÁP LUẬT, thủ tục, quyền, điều kiện:
  VD: "thủ tục sang tên", "Việt kiều mua đất được không", "Điều 45 Luật Đất đai"
  → LLM cần: trích điều khoản, hướng dẫn từng bước

"news_data" — Câu hỏi TIN TỨC, GIÁ CẢ, dữ liệu thời gian thực:
  VD: "giá vàng hôm nay", "tin BĐS mới nhất", "lãi suất ngân hàng"
  → LLM cần: chỉ data mới nhất, bảng giá, ngắn gọn

"general" — Câu hỏi khác (giải thích, so sánh, kiến thức chung):
  VD: "nguyên nhân giá vàng cao", "chung cư và nhà đất khác gì"
  → LLM cần: phân tích, giải thích logic

═══ BƯỚC 4: XÁC ĐỊNH needs_realtime ═══

true: Cần dữ liệu hôm nay (giá, tỷ giá, tin tức mới)
false: Kiến thức chung, phân tích, thủ tục, tư vấn

═══ BƯỚC 5: XÁC ĐỊNH category ═══

"legal": Câu hỏi cần search cả vector database pháp luật + web
"general": Chỉ cần web search

═══ FORMAT OUTPUT (BẮT BUỘC) ═══
JSON duy nhất, KHÔNG text khác:
{
  "action": "search",
  "search_query": "query tối ưu cho search",
  "category": "legal" | "general",
  "response_style": "advice" | "legal" | "news_data" | "general",
  "needs_realtime": true | false,
  "clarify_question": "",
  "greeting_response": "",
  "key_entities": ["entity1"],
  "reasoning": "lý do ngắn"
}"""


class QueryAnalyzer:
    """Analyze user query with LLM to decide next action."""

    def __init__(self, max_cache: int = 200):
        self._cache: Dict[str, AnalysisResult] = {}
        self._max_cache = max_cache

    def analyze(self, question: str, messages: List[Dict],
                llm) -> AnalysisResult:
        t0 = time.perf_counter()

        recent_history = self._build_history(messages)

        cache_key = hashlib.md5(
            f"{question}|{recent_history}".encode()
        ).hexdigest()

        if cache_key in self._cache:
            cached = self._cache[cache_key]
            elapsed = time.perf_counter() - t0
            logger.info("Analyzer cache hit: action=%s (%.2fs)", cached.action, elapsed)
            return cached

        user_prompt = self._build_user_prompt(question, recent_history)

        try:
            response = llm.invoke([HumanMessage(content=user_prompt)])
            raw = response.content.strip() if hasattr(response, 'content') else str(response).strip()
        except Exception as e:
            logger.warning("Analyzer LLM call failed: %s", e)
            return self._fallback(question)

        result = self._parse_response(raw, question)

        if len(self._cache) >= self._max_cache:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[cache_key] = result

        elapsed = time.perf_counter() - t0
        self._log_result(result, question, elapsed)

        return result

    def _build_history(self, messages: List[Dict]) -> str:
        if not messages:
            return ""
        lines = []
        for msg in messages[-8:]:  # More context for multi-turn
            role = "User" if msg.get("role") == "user" else "AI"
            content = str(msg.get("content", ""))[:300]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _build_user_prompt(self, question: str, history: str) -> str:
        parts = [_SYSTEM_PROMPT, ""]

        if history:
            parts.append(f"=== LỊCH SỬ HỘI THOẠI ===\n{history}\n")
        else:
            parts.append("=== LỊCH SỬ HỘI THOẠI ===\n(Chưa có lịch sử)\n")

        parts.append(f"=== CÂU HỎI HIỆN TẠI ===\n{question}")
        return "\n".join(parts)

    def _parse_response(self, raw: str, question: str) -> AnalysisResult:
        cleaned = raw
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^{}]*\}', cleaned, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return self._fallback(question)
            else:
                return self._fallback(question)

        action = data.get("action", "search")
        if action not in ("search", "clarify", "greeting"):
            action = "search"

        response_style = data.get("response_style", "general")
        if response_style not in ("advice", "legal", "news_data", "general"):
            response_style = "general"

        return AnalysisResult(
            action=action,
            search_query=data.get("search_query", question),
            category=data.get("category", "general"),
            response_style=response_style,
            needs_realtime=data.get("needs_realtime", False),
            clarify_question=data.get("clarify_question", ""),
            greeting_response=data.get("greeting_response", ""),
            key_entities=data.get("key_entities", []),
            reasoning=data.get("reasoning", ""),
            raw_response=raw,
        )

    def _fallback(self, question: str) -> AnalysisResult:
        return AnalysisResult(
            action="search",
            search_query=question,
            category="legal",
            response_style="general",
            needs_realtime=False,
            clarify_question="",
            greeting_response="",
            key_entities=[],
            reasoning="fallback — LLM parse failed",
            raw_response="",
        )

    def _log_result(self, result: AnalysisResult, question: str,
                    elapsed: float):
        logger.info(
            "Query analysis: action=%s query='%s' style=%s category=%s realtime=%s (%.2fs)",
            result.action, result.search_query[:60] if result.action == "search" else question[:60],
            result.response_style, result.category, result.needs_realtime, elapsed,
        )
        logger.info("─────────────────────────────────────────\n")


from chatbot_viva.core.singleton import singleton


@singleton
def get_query_analyzer() -> QueryAnalyzer:
    return QueryAnalyzer()
