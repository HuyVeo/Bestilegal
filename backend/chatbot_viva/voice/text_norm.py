"""
Text Normalization — Chuẩn hóa văn bản tiếng Việt trước khi đưa vào TTS

Pipeline: Text → Thay viết tắt → Chuyển số thành chữ → Xóa markdown → Text sạch
"""
import re

ABBREVIATIONS = {
    # Lịch sử
    r"\bTCN\b": "Trước công nguyên",
    r"\bSCN\b": "Sau công nguyên",
    # Đơn vị đo
    r"\bkm2\b": "ki lô mét vuông",
    r"\bkm²\b": "ki lô mét vuông",
    r"\bkm\b": "ki lô mét",
    r"\bcm\b": "xen ti mét",
    r"\bmm\b": "mi li mét",
    r"\bm2\b": "mét vuông",
    r"\bm²\b": "mét vuông",
    r"\bm3\b": "mét khối",
    r"\bm³\b": "mét khối",
    r"\bm\b": "mét",
    r"\bha\b": "héc ta",
    r"\bkg\b": "ki lô gam",
    r"\bg\b": "gam",
    r"\btấn\b": "tấn",
    # Tiền tệ
    r"\bđ\b": "đồng",
    r"\bvnđ\b": "việt nam đồng",
    r"\bVNĐ\b": "Việt Nam đồng",
    r"\bUSD\b": "đô la mỹ",
    r"\bEUR\b": "ơ rô",
    # Hành chính
    r"\bTP\b": "thành phố",
    r"\bTP\.": "thành phố",
    r"\bHĐND\b": "Hội đồng nhân dân",
    r"\bUBND\b": "Ủy ban nhân dân",
    r"\bBĐS\b": "bất động sản",
    r"\bGCN\b": "giấy chứng nhận",
    r"\bQSDĐ\b": "quyền sử dụng đất",
    r"\bSDĐ\b": "sử dụng đất",
    r"\bNĐ-CP\b": "nghị định chính phủ",
    r"\bTT-BTC\b": "thông tư bộ tài chính",
    r"\bQĐ\b": "quyết định",
    r"\bNĐ\b": "nghị định",
    r"\bTT\b": "thông tư",
    # Thông dụng
    r"\bĐH\b": "đại học",
    r"\bCĐ\b": "cao đẳng",
    r"\bPGĐ\b": "phó giám đốc",
    r"\bGĐ\b": "giám đốc",
    r"\bCTy\b": "công ty",
    r"\bDN\b": "doanh nghiệp",
}


def _number_to_vietnamese(number_str: str) -> str:
    """Chuyển chuỗi số thành chữ tiếng Việt."""
    # Xử lý số thập phân kiểu Việt (3,5 → 3.5)
    if "," in number_str and "." not in number_str:
        parts = number_str.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Đây là số thập phân: 3,5 → "ba phẩy năm"
            try:
                from num2words import num2words
                integer_part = num2words(int(parts[0]), lang='vi')
                decimal_part = num2words(int(parts[1]), lang='vi')
                return f"{integer_part} phẩy {decimal_part}"
            except (ImportError, ValueError):
                return number_str

    # Số nguyên với dấu chấm phân cách: 1.234.567
    clean_num = number_str.replace(".", "").replace(",", "")
    if not clean_num.isdigit():
        return number_str
    try:
        from num2words import num2words
        return num2words(int(clean_num), lang='vi')
    except (ImportError, ValueError):
        return number_str


def _replace_percentage(match: re.Match) -> str:
    """50% → năm mươi phần trăm"""
    num = match.group(1)
    converted = _number_to_vietnamese(num)
    return f"{converted} phần trăm"


def _replace_fraction(match: re.Match) -> str:
    """1/3 → một phần ba"""
    try:
        from num2words import num2words
        numerator = num2words(int(match.group(1)), lang='vi')
        denominator = num2words(int(match.group(2)), lang='vi')
        return f"{numerator} phần {denominator}"
    except (ImportError, ValueError):
        return match.group(0)


def normalize_vietnamese_text(text: str) -> str:
    """Chuẩn hóa text tiếng Việt cho TTS."""
    if not text:
        return ""

    # 1. Thay viết tắt (chạy trước số để xử lý đúng "50km" → "50 ki lô mét")
    for pattern, replacement in ABBREVIATIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 2. Phần trăm: 50% → năm mươi phần trăm
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*%', _replace_percentage, text)

    # 3. Phân số: 1/3 → một phần ba
    text = re.sub(r'\b(\d+)/(\d+)\b', _replace_fraction, text)

    # 4. Số thành chữ
    number_pattern = r'\b\d{1,3}(?:\.\d{3})*(?:,\d+)?\b|\b\d+\b'

    try:
        import num2words  # noqa: F401
        text = re.sub(number_pattern, lambda m: _number_to_vietnamese(m.group(0)), text)
    except ImportError:
        pass

    # 5. Xóa markdown
    text = re.sub(r'\*+', '', text)      # bold/italic
    text = re.sub(r'_+', '', text)       # italic
    text = re.sub(r'#+\s*', '', text)    # headings
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # links → text only
    text = re.sub(r'`[^`]*`', '', text)  # inline code
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)  # list markers

    # 6. Normalize khoảng trắng
    text = re.sub(r'\s+', ' ', text).strip()

    return text
