"""Centralized compiled regex patterns for Vietnamese legal document processing.

Shared across: loader.py, rag_service.py, legal_page_analyzer.py.
Import from here to avoid duplication.
"""

import re

# ── Article/clause extraction ──────────────────────────────────────

# Match "Điều 1", "Điều 2a", "Điều 45đ" (article number with optional suffix)
ARTICLE_RE = re.compile(r'(Điều\s+\d+[a-zđ]?)', re.IGNORECASE)

# Match "Khoản 1", "Khoản 2" (clause number)
CLAUSE_RE = re.compile(r'(Khoản\s+\d+)', re.IGNORECASE)

# Article heading with title: "Điều 1. Phạm vi điều chỉnh"
# Captures: (article_number, article_title)
ARTICLE_HEADING_RE = re.compile(
    r'(?:^|\n)\s*(?:\*\*\s*)?'
    r'((?:Điều|ĐIỀU)\s+\d+[a-zA-Z]?)'
    r'[\.\:]\s*'
    r'([^\n*]+?)'
    r'(?:\s*\*\*)?'
    r'\s*\n',
    re.IGNORECASE | re.UNICODE,
)

# ── Cross-reference detection ──────────────────────────────────────

# "theo Điều 48 Luật Đất đai 2024", "tại Điều 12 của Luật Nhà ở"
CROSS_REF_RE = re.compile(
    r'(?:theo|tại|quy định tại|căn cứ|xem|nêu tại|áp dụng)?\s*'
    r'(Điều\s+\d+[a-zđ]?)'
    r'(?:\s+(?:của\s+)?([A-ZĐÀ-Ỹa-zđà-ỹ][A-ZĐÀ-Ỹa-zđà-ỹ\s]*(?:20\d{2})?))?',
    re.IGNORECASE | re.UNICODE,
)

# ── Document type patterns ─────────────────────────────────────────

# Nghị định: "149/2024/NĐ-CP" or "149_2024_ND"
ND_PATTERN = re.compile(r'(\d+)[_/](\d{4})[_/]?N[DĐ]', re.IGNORECASE)

# Thông tư: "Thông tư 01"
TT_PATTERN = re.compile(r'[Tt]hông\s*tư\s*(\d+)', re.IGNORECASE)

# Known document name patterns → readable names
DOC_NAME_PATTERNS = [
    (re.compile(r'[Ll]uật\s*[Đđ]ất\s*đai'), 'Luật Đất đai'),
    (re.compile(r'[Ll]uật\s*[Nn]hà\s*ở'), 'Luật Nhà ở'),
    (re.compile(r'[Ll]uật\s*[Kk]inh\s*doanh\s*[Bb]ất\s*động\s*sản'), 'Luật Kinh doanh BĐS'),
    (re.compile(r'[Bb]ộ\s*luật\s*[Dd]ân\s*sự'), 'Bộ luật Dân sự'),
]
