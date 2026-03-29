"""
Stock Price Tool — fetch realtime stock prices from CafeF (banggia.cafef.vn).

Usage in main.py:
    from chatbot_viva.tools.stock_price import get_stock_context
    stock_ctx = get_stock_context(question)
    # stock_ctx is a string to inject into LLM context, or "" if not a stock question
"""

import logging
import re
import time
import requests
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# Ticker detection — map Vietnamese company names to stock codes
# ════════════════════════════════════════════════════════════════

# Common Vietnamese stock tickers and their aliases
_TICKER_MAP: Dict[str, List[str]] = {
    "VCB": ["vietcombank", "ngoại thương"],
    "BID": ["bidv", "đầu tư và phát triển"],
    "CTG": ["vietinbank", "công thương"],
    "TCB": ["techcombank"],
    "MBB": ["mbbank", "mb bank", "quân đội"],
    "VPB": ["vpbank", "vp bank", "việt nam thịnh vượng"],
    "ACB": ["acb", "á châu"],
    "HDB": ["hdbank", "hd bank", "phát triển tp"],
    "STB": ["sacombank"],
    "SHB": ["shb", "sài gòn hà nội"],
    "TPB": ["tpbank", "tp bank", "tiên phong"],
    "LPB": ["lienvietpostbank", "liên việt"],
    "EIB": ["eximbank"],
    "MSB": ["msb", "hàng hải"],
    "VIB": ["vib", "quốc tế"],
    "OCB": ["ocb", "phương đông"],
    "SSB": ["seabank", "sea bank", "đông nam á"],
    "NAB": ["nam á"],
    "ABB": ["abbank", "ab bank", "an bình"],
    "BAB": ["bac a bank", "bắc á"],
    "KLB": ["kienlongbank", "kiên long"],
    "PGB": ["pgbank", "pg bank", "xăng dầu"],
    "BVB": ["viet capital", "bản việt"],
    "SGB": ["saigonbank", "sài gòn công thương"],
    "VIC": ["vingroup"],
    "VHM": ["vinhomes"],
    "VRE": ["vincom retail"],
    "HPG": ["hòa phát", "hoa phat"],
    "FPT": ["fpt"],
    "MWG": ["thế giới di động", "mobile world"],
    "VNM": ["vinamilk"],
    "GAS": ["pvgas", "pv gas", "khí việt nam"],
    "SAB": ["sabeco", "bia sài gòn"],
    "MSN": ["masan"],
    "PLX": ["petrolimex", "xăng dầu"],
    "GVR": ["cao su việt nam"],
    "BCM": ["becamex"],
    "SSI": ["ssi", "chứng khoán ssi"],
    "VND": ["vndirect", "chứng khoán vndirect"],
    "HCM": ["hcmc securities", "chứng khoán hcm"],
    "NVL": ["novaland"],
    "PDR": ["phát đạt"],
    "DXG": ["đất xanh"],
    "KDH": ["khang điền"],
    "DIG": ["dic group"],
    "IJC": ["idico"],
    "VGC": ["viglacera"],
    "SBT": ["thành thành công"],
    "DPM": ["đạm phú mỹ"],
    "DCM": ["đạm cà mau"],
    "POW": ["điện lực dầu khí"],
    "PPC": ["nhiệt điện phả lại"],
    "REE": ["ree"],
    "BWE": ["nước bình dương"],
}

# Regex to detect stock ticker directly in text (3-letter uppercase code)
_TICKER_DIRECT_RE = re.compile(r'\b([A-Z]{3})\b')

# Regex patterns for stock-related questions
_STOCK_QUESTION_RE = re.compile(
    r'(?:giá|cổ phiếu|cp|chứng khoán|stock|ticker|mã ck|mã cổ phiếu|'
    r'cổ phiếu.*giá|giá.*cổ phiếu|giá.*hôm nay|giá.*hiện tại|'
    r'giá cổ|giá cp)',
    re.IGNORECASE,
)


def detect_tickers(question: str) -> List[str]:
    """
    Detect stock tickers from user question.
    Returns list of ticker codes (e.g. ["VCB", "ACB"]).
    """
    tickers = []
    q_lower = question.lower()

    # 1. Direct ticker mention (e.g. "VCB", "FPT")
    for match in _TICKER_DIRECT_RE.finditer(question):
        code = match.group(1)
        if code in _TICKER_MAP:
            tickers.append(code)

    # 2. Company name mention
    for code, aliases in _TICKER_MAP.items():
        if code in tickers:
            continue
        for alias in aliases:
            if alias in q_lower:
                tickers.append(code)
                break

    return tickers


def is_stock_question(question: str) -> bool:
    """Check if the question is asking about stock prices."""
    return bool(_STOCK_QUESTION_RE.search(question))


# ════════════════════════════════════════════════════════════════
# CafeF API — fetch realtime price
# ════════════════════════════════════════════════════════════════

_CAFEF_URL = "https://banggia.cafef.vn/stockhandler.ashx"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Field mapping from CafeF's obfuscated keys
# a=ticker, b=ref, c=ceiling, d=floor, e=matched/last price,
# k=change, v=high, w=low, n=totalvolume, Time=timestamp
_FIELD_MAP = {
    "a": "ticker",
    "b": "ref_price",
    "c": "ceiling",
    "d": "floor",
    "e": "last_price",
    "k": "change",
    "v": "high",
    "w": "low",
    "n": "total_volume",
    "totalvolume": "total_volume_2",
    "Time": "time",
}


def _fetch_price(ticker: str) -> Optional[Dict]:
    """Fetch realtime price for a single ticker from CafeF."""
    try:
        resp = requests.get(
            _CAFEF_URL,
            params={"center": "", "index": "", "stocklist": ticker},
            headers=_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("[STOCK] CafeF API failed: %s", e)
        return None

    # Find the ticker in response
    for item in data:
        if item.get("a") == ticker:
            return item

    return None


def _format_price(raw: Dict) -> Dict:
    """Convert raw CafeF data to readable format."""
    ticker = raw.get("a", "")
    ref = raw.get("b", 0)
    last = raw.get("e", 0)
    change = raw.get("k", 0)
    ceiling = raw.get("c", 0)
    floor = raw.get("d", 0)
    high = raw.get("v", 0)
    low = raw.get("w", 0)
    volume = raw.get("totalvolume", raw.get("n", 0))
    timestamp = raw.get("Time", "")

    # CafeF returns prices in thousands (e.g. 59.6 = 59,600 VND)
    def fmt(v):
        if v == 0:
            return "0"
        return f"{v * 1000:,.0f}"

    change_pct = round((change / ref * 100), 2) if ref else 0
    direction = "tăng" if change > 0 else "giảm" if change < 0 else "không đổi"

    return {
        "ticker": ticker,
        "last_price": fmt(last),
        "last_price_raw": last * 1000,
        "ref_price": fmt(ref),
        "ceiling": fmt(ceiling),
        "floor": fmt(floor),
        "high": fmt(high),
        "low": fmt(low),
        "change": fmt(abs(change)),
        "change_pct": f"{abs(change_pct):.2f}%",
        "direction": direction,
        "volume": f"{volume:,.0f}",
        "time": timestamp,
    }


# ════════════════════════════════════════════════════════════════
# Public API — the only function main.py needs to call
# ════════════════════════════════════════════════════════════════

def get_stock_context(question: str) -> str:
    """
    Detect stock tickers in question, fetch realtime prices,
    and return formatted context string for LLM injection.

    Returns "" if not a stock question or no tickers found.
    """
    if not is_stock_question(question):
        return ""

    tickers = detect_tickers(question)
    if not tickers:
        return ""

    logger.info("[STOCK] Detected tickers: %s", tickers)
    t0 = time.perf_counter()

    results = []
    for ticker in tickers[:5]:  # max 5 tickers per question
        raw = _fetch_price(ticker)
        if raw:
            formatted = _format_price(raw)
            results.append(formatted)
            logger.info("[STOCK] %s: %s VND (%s %s) @ %s",
                        ticker, formatted['last_price'],
                        formatted['direction'], formatted['change'], formatted['time'])

    if not results:
        return ""

    # Build context string for LLM
    lines = ["=== DỮ LIỆU GIÁ CỔ PHIẾU REALTIME (từ CafeF) ===",
             "Dữ liệu bên dưới là REALTIME, BẮT BUỘC sử dụng khi trả lời về giá cổ phiếu.\n"]

    for r in results:
        lines.append(f"Mã: {r['ticker']}")
        lines.append(f"  Giá hiện tại: {r['last_price']} VND ({r['direction']} {r['change']} VND, {r['change_pct']})")
        lines.append(f"  Giá tham chiếu: {r['ref_price']} VND")
        lines.append(f"  Trần: {r['ceiling']} VND | Sàn: {r['floor']} VND")
        lines.append(f"  Cao nhất: {r['high']} VND | Thấp nhất: {r['low']} VND")
        lines.append(f"  Khối lượng: {r['volume']} CP")
        lines.append(f"  Thời gian cập nhật: {r['time']}")
        lines.append("")

    elapsed = time.perf_counter() - t0
    logger.info("[STOCK] Done in %.2fs", elapsed)

    return "\n".join(lines)
