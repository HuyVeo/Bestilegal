"""Legal article lookup and cleaning endpoints."""
from __future__ import annotations

import re
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from chatbot_viva.core.dependencies import get_optional_user, check_rate_limit
from chatbot_viva.core.cache import InMemoryCache
from chatbot_viva.llm.factory import get_llm_factory

router = APIRouter()
log = logging.getLogger(__name__)

_clean_cache = InMemoryCache(max_items=500)


@router.post(
    "/api/legal-article/search",
    dependencies=[Depends(check_rate_limit)],
)
async def search_legal_article(request: Request, _user=Depends(get_optional_user)):
    body = await request.json()
    document_name = (body.get("document_name") or "").strip()
    article = (body.get("article") or "").strip()
    rag_content = (body.get("rag_content") or "").strip()

    if not document_name:
        raise HTTPException(status_code=400, detail="document_name required")

    query_parts = [document_name]
    if article:
        query_parts.append(article)
    query = " ".join(query_parts)

    log.info("Legal article lookup: %s", query)

    from chatbot_viva.tools.tavily_utils import safe_tavily_search
    results = safe_tavily_search(
        f"site:hethongphapluat.vn {query}",
        max_results=3,
    )

    if not results:
        return {
            "source": "rag",
            "content": rag_content or "Không tìm thấy nội dung trên hethongphapluat.vn.",
            "url": None,
            "title": f"{document_name} {article}".strip(),
        }

    best = results[0]
    if article:
        for r in results:
            title = (r.get("title") or "").lower()
            art_num = re.search(r'\d+', article)
            if art_num and art_num.group() in title:
                best = r
                break

    raw = best.get("raw_content") or best.get("content") or ""
    url = best.get("url") or ""
    title = best.get("title") or ""

    extracted = _extract_article_section(raw, article) if article else raw[:3000]

    return {
        "source": "web",
        "content": extracted,
        "url": url,
        "title": title,
    }


def _extract_article_section(raw_content: str, article: str) -> str:
    """Extract the specific Điều section from raw page content."""
    if not raw_content or not article:
        return raw_content[:3000] if raw_content else ""

    art_num_match = re.search(r'\d+[a-zđ]?', article)
    if not art_num_match:
        return raw_content[:3000]

    art_num = art_num_match.group()

    pattern = re.compile(
        rf'(Điều\s+{re.escape(art_num)}[\.\s:][^\n]*\n)',
        re.IGNORECASE,
    )
    match = pattern.search(raw_content)
    if not match:
        return raw_content[:3000]

    start = match.start()

    next_article = re.search(
        rf'(?:^|\n)(Điều\s+(?!{re.escape(art_num)}[\.\s:])\d+)',
        raw_content[match.end():],
        re.IGNORECASE,
    )
    end = match.end() + next_article.start() if next_article else min(start + 5000, len(raw_content))

    return raw_content[start:end].strip()


@router.post(
    "/api/legal-article/clean",
    dependencies=[Depends(check_rate_limit)],
)
async def clean_legal_article(request: Request, _user=Depends(get_optional_user)):
    body = await request.json()
    content = (body.get("content") or "").strip()
    document_name = (body.get("document_name") or "").strip()
    article = (body.get("article") or "").strip()

    if not content:
        raise HTTPException(status_code=400, detail="content required")

    cache_key = f"{document_name}|{article}|{hash(content)}"
    cached = _clean_cache.get(cache_key)
    if cached:
        return {"cleaned": cached}

    label = f"{document_name} {article}".strip() if article else document_name

    prompt = f"""Định dạng lại nội dung điều luật sau thành markdown chuẩn.

QUY TẮC:
1. Giữ nguyên 100% nội dung pháp lý gốc — KHÔNG thêm, bớt hay diễn giải
2. Xóa: metadata rác, URL, ký tự lặp, text không liên quan đến nội dung điều luật
3. Tên Điều dùng heading ## trên MỘT dòng duy nhất. Ví dụ đúng:
   ## Điều 45. Sử dụng hợp đồng trong kinh doanh bất động sản
4. Các khoản (1, 2, 3...) → danh sách số thụt vào
5. Các điểm (a, b, c...) → bullet - thụt vào thêm 1 cấp
6. **bold** phải mở và đóng trên CÙNG MỘT dòng, tuyệt đối KHÔNG xuống dòng giữa **
7. KHÔNG dùng bold cho tên Điều (đã là heading ##)
8. CHỈ trả về markdown, không giải thích gì thêm

VĂN BẢN: {label}

NỘI DUNG GỐC:
{content}"""

    try:
        factory = get_llm_factory()
        llm = factory.create(task="rewrite", temperature=0, streaming=False)
        result = llm.invoke(prompt)
        cleaned = result.content if hasattr(result, 'content') else str(result)

        _clean_cache.set(cache_key, cleaned, ttl=3600)
        return {"cleaned": cleaned}

    except Exception as e:
        log.warning("LLM clean failed: %s", e)
        return {"cleaned": content}
