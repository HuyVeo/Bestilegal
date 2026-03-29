"""
Question Classifier — Phân loại câu hỏi dựa trên keyword patterns.

Single Responsibility: Chỉ phân loại loại câu hỏi, không build prompt.
Extracted from prompt_templates.py để tách classification khỏi prompt generation.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import List, Tuple

# Pre-compiled patterns for each question type
_PatternList = List[re.Pattern]


class QuestionType(Enum):
    """Loại câu hỏi — dùng để chọn prompt template phù hợp."""

    NEWS = "news"
    COMPARISON = "comparison"
    LEGAL_PROCEDURE = "legal_procedure"
    PRICE_DATA = "price_data"
    CONCEPT = "concept"
    ADVICE = "advice"
    GENERAL = "general"
    WEB_QUICK = "web_quick"


def _compile_patterns(raw_patterns: List[str]) -> _PatternList:
    """Compile list of regex strings thành compiled patterns."""
    return [re.compile(p) for p in raw_patterns]


_CLASSIFICATION_PATTERNS: dict[QuestionType, _PatternList] = {
    QuestionType.NEWS: _compile_patterns([
        r'tin tức', r'tin mới', r'cập nhật', r'hôm nay', r'ngày \d+',
        r'tuần này', r'tháng \d+', r'năm \d{4}', r'mới nhất', r'gần đây',
        r'diễn biến', r'tình hình', r'thị trường', r'xu hướng',
        r'biến động', r'sự kiện', r'thông tin mới',
    ]),
    QuestionType.COMPARISON: _compile_patterns([
        r'so sánh', r'khác nhau', r'giống nhau', r'khác biệt',
        r'so với', r'hơn', r'kém', r'tốt hơn', r'xấu hơn',
        r'nên chọn', r'hay là', r'hoặc', r' vs ', r'versus',
        r'ưu điểm', r'nhược điểm', r'điểm khác', r'điểm giống',
    ]),
    QuestionType.LEGAL_PROCEDURE: _compile_patterns([
        r'thủ tục', r'quy trình', r'hồ sơ', r'giấy tờ', r'điều kiện',
        r'yêu cầu', r'cần những gì', r'làm sao', r'làm thế nào',
        r'bước', r'trình tự', r'đăng ký', r'xin cấp', r'nộp',
        r'sang tên', r'chuyển nhượng', r'cấp sổ', r'thời hạn',
        r'luật', r'nghị định', r'quy định', r'pháp lý',
    ]),
    QuestionType.PRICE_DATA: _compile_patterns([
        r'giá', r'bao nhiêu', r'chi phí', r'phí', r'thuế',
        r'lãi suất', r'tỷ lệ', r'số liệu', r'thống kê',
        r'bảng giá', r'mức giá', r'đơn giá', r'tổng chi phí',
        r'triệu', r'tỷ', r'đồng/m', r'vnd', r'\d+%',
    ]),
    QuestionType.CONCEPT: _compile_patterns([
        r'là gì', r'nghĩa là', r'định nghĩa', r'khái niệm',
        r'hiểu như thế nào', r'giải thích', r'có nghĩa',
        r'thế nào là', r'gọi là', r'tức là',
    ]),
    QuestionType.ADVICE: _compile_patterns([
        r'nên', r'có nên', r'tư vấn', r'khuyên', r'gợi ý',
        r'đề xuất', r'lời khuyên', r'làm gì', r'phải làm',
        r'cách tốt nhất', r'chiến lược', r'kế hoạch',
    ]),
}


def classify_question(question: str) -> Tuple[QuestionType, float]:
    """
    Phân loại câu hỏi dựa trên keyword matching.

    Args:
        question: Câu hỏi của user.

    Returns:
        Tuple (QuestionType, confidence 0.0-1.0).
        GENERAL nếu không match pattern nào.
    """
    question_lower = question.lower()
    scores: dict[QuestionType, float] = {qtype: 0.0 for qtype in QuestionType}

    for qtype, patterns in _CLASSIFICATION_PATTERNS.items():
        for pattern in patterns:
            matches = pattern.findall(question_lower)
            if matches:
                scores[qtype] += len(matches) * 1.0

    max_score = max(scores.values())
    if max_score == 0:
        return QuestionType.GENERAL, 0.5

    best_type = max(scores, key=scores.get)
    confidence = min(max_score / 3.0, 1.0)
    return best_type, confidence


def analyze_user_intent(question: str, history_context: str = "", llm=None) -> dict:
    """
    Router nhẹ: keyword matching cho comparison/deep_analysis.

    Args:
        question: Câu hỏi của user.
        history_context: Unused, kept for backward compat.
        llm: Unused, kept for backward compat.

    Returns:
        Dict with keys: intent, reasoning, missing_info.
    """
    question_lower = question.lower()

    comparison_keywords = [
        "so sánh", "kẻ bảng", "lập bảng", "đối chiếu",
        "khác nhau thế nào", "vs", "bảng giá",
    ]
    if any(k in question_lower for k in comparison_keywords):
        return {"intent": "comparison", "reasoning": "Keyword match", "missing_info": ""}

    deep_keywords = [
        "phân tích", "chi tiết", "đánh giá", "nhận định", "tiềm năng", "tại sao",
    ]
    if any(k in question_lower for k in deep_keywords):
        return {"intent": "deep_analysis", "reasoning": "Keyword match", "missing_info": ""}

    return {"intent": "basic_rag", "reasoning": "Default", "missing_info": ""}
