"""
Metadata-Driven Filtering (RBAC).

Tags documents with metadata during loading and filters during retrieval.

Payload fields (from metadata.json via loader):
- loai_van_ban: Loại văn bản (Luật, Nghị định, Thông tư, ...)
- so_hieu: Số hiệu (149/2025/QH15)
- trang_thai: Trạng thái (Còn hiệu lực, Hết hiệu lực)
- co_quan_ban_hanh: Cơ quan ban hành
- dieu_so: Điều số (Điều 2)
- ten_dieu: Tên điều đầy đủ
- ngay_ban_hanh: Ngày ban hành
- ngay_hieu_luc: Ngày hiệu lực
- source_url: URL nguồn

Enrichment fields (auto-detected):
- department: Phòng ban (legal, finance, general, hdsd)
- urgency: Mức độ ưu tiên (high, medium, low)
- access_level: Cấp truy cập (public, internal, restricted)
- topics: Chủ đề chính
- year: Năm ban hành (extracted)
"""

import re
import logging
from typing import List, Optional, Set
from dataclasses import dataclass, field
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


@dataclass
class AccessContext:
    """Defines what the current user/bot can access."""
    role: str = "public"                   # public, internal, admin
    departments: Set[str] = field(
        default_factory=lambda: {
            "legal", "finance", "general", "hdsd"})
    max_access_level: str = "public"       # public, internal, restricted

    ACCESS_HIERARCHY = {"public": 0, "internal": 1, "restricted": 2}

    def can_access(self, access_level: str) -> bool:
        my_level = self.ACCESS_HIERARCHY.get(self.max_access_level, 0)
        doc_level = self.ACCESS_HIERARCHY.get(access_level, 0)
        return my_level >= doc_level


# Default access context (public bot)
DEFAULT_ACCESS = AccessContext(
    role="public",
    departments={"legal", "finance", "general", "hdsd"},
    max_access_level="public",
)


# ═══════════════════════════════════════════════════════════════
# Document type mapping from loai_van_ban
# ═══════════════════════════════════════════════════════════════

_LOAI_VAN_BAN_TO_DOC_TYPE = {
    "luật": "law",
    "bộ luật": "law",
    "nghị định": "decree",
    "thông tư": "circular",
    "quyết định": "decision",
    "nghị quyết": "resolution",
    "hướng dẫn": "guide",
}


def _map_doc_type(loai_van_ban: str) -> str:
    """Map loai_van_ban to internal doc_type."""
    if not loai_van_ban:
        return "general"
    for key, doc_type in _LOAI_VAN_BAN_TO_DOC_TYPE.items():
        if key in loai_van_ban.lower():
            return doc_type
    return "general"


# Pre-compiled department detection patterns
_DEPARTMENT_COMPILED = {
    "legal": [
        re.compile(p, re.IGNORECASE) for p in [
            r"luật", r"pháp\s+lý", r"nghị\s+định", r"thông\s+tư",
            r"điều\s+\d+", r"khoản\s+\d+", r"quy\s+định",
            r"tranh\s+chấp", r"hợp\s+đồng", r"công\s+chứng",
        ]
    ],
    "finance": [
        re.compile(p, re.IGNORECASE) for p in [
            r"thuế", r"lệ\s+phí", r"chi\s+phí", r"giá",
            r"lãi\s+suất", r"vay\s+vốn", r"tín\s+dụng",
            r"định\s+giá", r"thẩm\s+định\s+giá",
        ]
    ],
    "hdsd": [
        re.compile(p, re.IGNORECASE) for p in [
            r"hdsd", r"hướng\s+dẫn\s+sử\s+dụng", r"app",
            r"tính\s+năng", r"cài\s+đặt", r"đăng\s+ký",
        ]
    ],
    "general": [],
}

# Pre-compiled topic detection patterns
_TOPIC_COMPILED = {
    "transfer": [re.compile(p, re.IGNORECASE) for p in [r"chuyển\s+nhượng", r"sang\s+tên", r"mua\s+bán"]],
    "tax": [re.compile(p, re.IGNORECASE) for p in [r"thuế", r"lệ\s+phí", r"phí\s+trước\s+bạ"]],
    "land_use": [re.compile(p, re.IGNORECASE) for p in [r"sử\s+dụng\s+đất", r"quyền\s+sử\s+dụng", r"sổ\s+đỏ"]],
    "construction": [re.compile(p, re.IGNORECASE) for p in [r"xây\s+dựng", r"giấy\s+phép", r"quy\s+hoạch"]],
    "apartment": [re.compile(p, re.IGNORECASE) for p in [r"chung\s+cư", r"căn\s+hộ", r"condotel"]],
    "dispute": [re.compile(p, re.IGNORECASE) for p in [r"tranh\s+chấp", r"kiện", r"tòa\s+án"]],
    "inheritance": [re.compile(p, re.IGNORECASE) for p in [r"thừa\s+kế", r"di\s+sản", r"di\s+chúc"]],
    "pricing": [re.compile(p, re.IGNORECASE) for p in [r"giá\s+đất", r"giá\s+nhà", r"định\s+giá", r"thẩm\s+định"]],
}


def detect_department(content: str) -> str:
    """Detect which department a document belongs to."""
    text = content.lower()
    scores = {}
    for dept, compiled_patterns in _DEPARTMENT_COMPILED.items():
        scores[dept] = sum(1 for p in compiled_patterns if p.search(text))
    if not scores or max(scores.values()) == 0:
        return "general"
    return max(scores, key=scores.get)


def detect_topics(content: str) -> List[str]:
    """Detect topics covered in the document."""
    text = content.lower()
    topics = []
    for topic, compiled_patterns in _TOPIC_COMPILED.items():
        if any(p.search(text) for p in compiled_patterns):
            topics.append(topic)
    return topics if topics else ["general"]


def _extract_year(meta: dict) -> Optional[int]:
    """Extract year from ngay_ban_hanh or so_hieu."""
    import datetime
    current_year = datetime.datetime.now().year

    # Try ngay_ban_hanh (DD/MM/YYYY)
    ngay = meta.get("ngay_ban_hanh", "")
    if ngay:
        year_match = re.search(r'(\d{4})', ngay)
        if year_match:
            y = int(year_match.group(1))
            if 1990 <= y <= current_year:
                return y

    # Try so_hieu (e.g. "149/2025/QH15")
    so_hieu = meta.get("so_hieu", "")
    if so_hieu:
        year_match = re.search(r'/(\d{4})/', so_hieu)
        if year_match:
            y = int(year_match.group(1))
            if 1990 <= y <= current_year:
                return y

    return None


def detect_urgency(content: str, doc_type: str) -> str:
    """Determine document urgency/priority."""
    text = content.lower()

    if doc_type in ("law", "decree"):
        return "high"

    high_keywords = ["bắt buộc", "nghiêm cấm", "vi phạm", "xử phạt", "khẩn"]
    if any(kw in text for kw in high_keywords):
        return "high"

    if doc_type == "circular":
        return "medium"

    return "low"


def _map_loai_van_ban_to_doc_type(loai_vb: str) -> str:
    """Map Vietnamese document type name to internal doc_type code."""
    loai_lower = loai_vb.lower()
    if "luật" in loai_lower or "bộ luật" in loai_lower:
        return "law"
    if "nghị định" in loai_lower:
        return "decree"
    if "thông tư" in loai_lower:
        return "circular"
    if "hướng dẫn" in loai_lower:
        return "guide"
    return "general"


def _parse_vn_date_year(date_str: str) -> Optional[int]:
    """Extract year from Vietnamese date format dd/mm/yyyy."""
    import re as _re
    match = _re.search(r'(\d{4})', date_str)
    if match:
        y = int(match.group(1))
        if 1990 <= y <= 2030:
            return y
    return None


def enrich_document_metadata(doc: Document) -> Document:
    """
    Enrich a document with auto-detected metadata tags for filtering.

    Uses existing payload fields (loai_van_ban) and adds:
    - department, doc_type, urgency, access_level, topics, year
    """
    meta = doc.metadata
    content = doc.page_content

    # Map loai_van_ban -> doc_type
    doc_type = _map_doc_type(meta.get("loai_van_ban", ""))
    department = detect_department(content)
    topics = detect_topics(content)
    year = _extract_year(meta)
    urgency = detect_urgency(content, doc_type)

    meta.update({
        "department": department,
        "doc_type": doc_type,
        "urgency": urgency,
        "access_level": "public",
        "topics": topics,
        "year": year,
    })

    return doc


def enrich_documents_batch(documents: List[Document]) -> List[Document]:
    """Enrich metadata for a batch of documents."""
    enriched = []
    for doc in documents:
        enriched.append(enrich_document_metadata(doc))

    # Stats
    dept_counts = {}
    type_counts = {}
    for doc in enriched:
        dept = doc.metadata.get("department", "unknown")
        dtype = doc.metadata.get("doc_type", "unknown")
        dept_counts[dept] = dept_counts.get(dept, 0) + 1
        type_counts[dtype] = type_counts.get(dtype, 0) + 1

    logger.info(
        "Metadata enrichment: departments=%s, types=%s",
        dept_counts, type_counts,
    )

    return enriched


def filter_documents(
    documents: List[Document],
    access_ctx: AccessContext = None,
    required_department: str = None,
    required_topics: List[str] = None,
    min_urgency: str = None,
    year_from: int = None,
    year_to: int = None,
    trang_thai: str = None,
) -> List[Document]:
    """
    Filter documents based on metadata and access context.

    Args:
        documents: Documents to filter
        access_ctx: Access control context (RBAC)
        required_department: Only include docs from this department
        required_topics: Only include docs covering these topics
        min_urgency: Minimum urgency level (high > medium > low)
        year_from: Minimum year
        year_to: Maximum year
        trang_thai: Filter by status (e.g. "Còn hiệu lực")

    Returns:
        Filtered list of documents
    """
    if access_ctx is None:
        access_ctx = DEFAULT_ACCESS

    urgency_levels = {"low": 0, "medium": 1, "high": 2}
    min_urgency_val = urgency_levels.get(min_urgency, 0) if min_urgency else 0

    filtered = []
    for doc in documents:
        meta = doc.metadata

        # RBAC: Check access level
        if not access_ctx.can_access(meta.get("access_level", "public")):
            continue

        # RBAC: Check department
        doc_dept = meta.get("department", "general")
        if doc_dept not in access_ctx.departments:
            continue

        # Department filter
        if required_department and doc_dept != required_department:
            continue

        # Topic filter
        if required_topics:
            doc_topics = set(meta.get("topics", []))
            if not doc_topics.intersection(required_topics):
                continue

        # Urgency filter
        doc_urgency = urgency_levels.get(meta.get("urgency", "low"), 0)
        if doc_urgency < min_urgency_val:
            continue

        # Year range filter
        doc_year = meta.get("year")
        if doc_year:
            if year_from and doc_year < year_from:
                continue
            if year_to and doc_year > year_to:
                continue

        # Status filter
        if trang_thai:
            doc_status = meta.get("trang_thai", "")
            if doc_status and trang_thai.lower() not in doc_status.lower():
                continue

        filtered.append(doc)

    return filtered


def boost_by_metadata(
    documents: List[tuple],
    query_topics: List[str] = None,
) -> List[tuple]:
    """
    Apply metadata-based score boosting to search results.

    Args:
        documents: List of (Document, score) tuples
        query_topics: Topics detected from the user query

    Returns:
        List of (Document, boosted_score) tuples, re-sorted
    """
    URGENCY_BOOST = {"high": 1.3, "medium": 1.1, "low": 1.0}
    TOPIC_MATCH_BOOST = 1.2

    boosted = []
    for doc, score in documents:
        meta = doc.metadata
        new_score = score

        # Urgency boost
        urgency = meta.get("urgency", "low")
        new_score *= URGENCY_BOOST.get(urgency, 1.0)

        # Topic match boost
        if query_topics:
            doc_topics = set(meta.get("topics", []))
            if doc_topics.intersection(query_topics):
                new_score *= TOPIC_MATCH_BOOST

        boosted.append((doc, new_score))

    boosted.sort(key=lambda x: x[1], reverse=True)
    return boosted
