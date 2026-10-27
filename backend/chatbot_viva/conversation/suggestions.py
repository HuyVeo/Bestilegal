"""Utility functions for generating suggested questions."""

import logging
from typing import List
from langchain_core.messages import HumanMessage
from chatbot_viva.llm.factory import get_llm_factory

logger = logging.getLogger(__name__)


def generate_suggested_questions(question: str, answer: str) -> List[str]:
    """
    Generate 5 suggested follow-up questions based on the user's question and chatbot's answer.

    Args:
        question: The user's original question.
        answer: The chatbot's response to the question.

    Returns:
        List of 5 suggested questions (strings).
    """
    logger.info("[SUGGESTIONS] Generating follow-up questions...")
    factory = get_llm_factory()
    llm = factory.create(task="rewrite", temperature=0.7)

    prompt = (
        f"Dựa trên câu hỏi và câu trả lời sau đây, hãy tạo ra 5 câu hỏi gợi ý liên quan "
        f"mà người dùng có thể muốn hỏi tiếp theo.\n\n"
        f"Câu hỏi của người dùng: {question}\n\n"
        f"Câu trả lời của chatbot: {answer}\n\n"
        f"Yêu cầu:\n"
        f"- Tạo ra đúng 5 câu hỏi gợi ý bằng tiếng Việt\n"
        f"- Các câu hỏi phải liên quan đến chủ đề đã được hỏi và trả lời\n"
        f"- Các câu hỏi nên khám phá các khía cạnh khác nhau hoặc đi sâu hơn vào chủ đề\n"
        f"- Câu hỏi phải tự nhiên, dễ hiểu và có thể hỏi trực tiếp\n"
        f"- Trả về chỉ danh sách các câu hỏi, mỗi câu hỏi trên một dòng, không đánh số, không có ký tự đặc biệt ở đầu\n"
        f"- Mỗi câu hỏi phải là một câu hoàn chỉnh, kết thúc bằng dấu chấm hỏi\n\n"
        f"Ví dụ định dạng:\n"
        f"Quy định về thuế khi mua bán nhà đất?\n"
        f"Thủ tục chuyển nhượng quyền sử dụng đất như thế nào?\n"
        f"Cần những giấy tờ gì khi mua nhà?\n")

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        questions = [q.strip() for q in content.split('\n') if q.strip()]

        cleaned_questions = []
        for q in questions:
            q = q.lstrip('0123456789.-) ')
            q = q.lstrip('#* ')
            if q and q.endswith('?'):
                cleaned_questions.append(q)
            elif q:
                cleaned_questions.append(q + '?')

        if len(cleaned_questions) >= 5:
            logger.info("[SUGGESTIONS] Generated 5 follow-up questions")
            return cleaned_questions[:5]
        elif len(cleaned_questions) > 0:
            logger.info("[SUGGESTIONS] Generated %d follow-up questions", len(cleaned_questions))
            return cleaned_questions
        else:
            logger.warning("[SUGGESTIONS] Failed to generate questions")
            return []

    except Exception as e:
        logger.error("[SUGGESTIONS] Error: %s", e)
        return []
