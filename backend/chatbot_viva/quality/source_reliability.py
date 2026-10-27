"""
Source Reliability Score - Hệ thống xếp hạng độ tin cậy nguồn.

Như Perplexity, hệ thống này:
1. Phân loại nguồn theo categories (Gov, Academic, News, Social...)
2. Gán điểm tin cậy cho từng nguồn
3. Block/downrank nguồn kém tin cậy (Facebook, TikTok, forums...)
4. Ưu tiên nguồn chính thống khi có conflict

Centralized module - được sử dụng bởi:
- source_grounding.py
- snippet_ranking.py
- web_search.py
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class SourceCategory(Enum):
    """Phan loai nguon theo do tin cay."""
    GOVERNMENT = "government"           # Chinh phu, co quan nha nuoc
    LEGAL_OFFICIAL = "legal_official"   # Van ban phap luat chinh thuc
    ACADEMIC = "academic"               # Hoc thuat, nghien cuu
    MAJOR_NEWS = "major_news"           # Bao chi lon, uy tin
    INDUSTRY_EXPERT = "industry_expert"  # Chuyen gia nganh BDS
    BUSINESS_NEWS = "business_news"     # Tin tuc kinh doanh
    LOCAL_NEWS = "local_news"           # Bao dia phuong
    AGGREGATOR = "aggregator"           # Trang tong hop
    BLOG = "blog"                       # Blog ca nhan
    SOCIAL_MEDIA = "social_media"       # Mang xa hoi
    FORUM = "forum"                     # Dien dan
    UNKNOWN = "unknown"                 # Khong xac dinh


class SourceType(Enum):
    """Loai nguon don gian - dung cho display."""
    NEWS = "Tin tuc"                    # Tin tuc, bao chi
    REAL_ESTATE = "Trang BDS"           # Trang BDS, tin dang ban
    LEGAL = "Phap luat"                 # Phap luat, chinh thong


@dataclass
class SourceInfo:
    """Thông tin về một nguồn."""
    url: str
    domain: str
    category: SourceCategory
    reliability_score: float  # 0.0 - 1.0
    is_blocked: bool
    reason: str  # Lý do block hoặc note


class SourceReliabilityScorer:
    """
    Hệ thống đánh giá độ tin cậy nguồn.
    """

    # ========== TIER 1: HIGHEST RELIABILITY (0.95 - 1.0) ==========
    # Nguồn chính phủ, cơ quan nhà nước
    GOVERNMENT_DOMAINS = {
        # Vietnam Government
        "chinhphu.vn": 1.0,
        "gov.vn": 1.0,
        "moj.gov.vn": 1.0,          # Bộ Tư pháp
        "monre.gov.vn": 1.0,        # Bộ TN&MT
        "moc.gov.vn": 1.0,          # Bộ Xây dựng
        "most.gov.vn": 0.95,        # Bộ KH&CN
        "gso.gov.vn": 0.95,         # Tổng cục Thống kê
        "sbv.gov.vn": 0.95,         # Ngân hàng Nhà nước
        "customs.gov.vn": 0.95,
        "gdla.gov.vn": 1.0,         # Cục Quản lý đất đai

        # International Organizations
        "un.org": 1.0,
        "who.int": 1.0,
        "imf.org": 1.0,
        "worldbank.org": 1.0,
        "adb.org": 0.95,            # Asian Development Bank
        "oecd.org": 0.95,
    }

    # ========== TIER 2: LEGAL OFFICIAL (0.90 - 0.95) ==========
    LEGAL_OFFICIAL_DOMAINS = {
        "thuvienphapluat.vn": 0.95,
        "luatvietnam.vn": 0.95,
        "vbpl.vn": 0.95,            # Văn bản pháp luật
        "lawnet.vn": 0.90,
        "tracuuphapluat.vn": 0.90,
        "congbao.chinhphu.vn": 0.95,
        "vietlaw.gov.vn": 0.95,
    }

    # ========== TIER 3: ACADEMIC (0.85 - 0.95) ==========
    ACADEMIC_DOMAINS = {
        "scholar.google": 0.95,
        "pubmed.ncbi": 0.95,
        "sciencedirect.com": 0.90,
        "researchgate.net": 0.85,
        "academia.edu": 0.85,
        "jstor.org": 0.90,
        # Vietnam Universities
        "vnu.edu.vn": 0.90,         # ĐH Quốc gia HN
        "hcmus.edu.vn": 0.90,       # ĐH KHTN HCM
        "neu.edu.vn": 0.90,         # ĐH Kinh tế Quốc dân
        "ueh.edu.vn": 0.90,         # ĐH Kinh tế HCM
        "hcmulaw.edu.vn": 0.90,     # ĐH Luật HCM
    }

    # ========== TIER 4: MAJOR NEWS (0.80 - 0.90) ==========
    MAJOR_NEWS_DOMAINS = {
        # International
        "reuters.com": 0.90,
        "bloomberg.com": 0.90,
        "bbc.com": 0.85,
        "nytimes.com": 0.85,
        "wsj.com": 0.85,
        "ft.com": 0.85,             # Financial Times
        "economist.com": 0.85,

        # Vietnam Major News
        "vnexpress.net": 0.85,
        "tuoitre.vn": 0.85,
        "thanhnien.vn": 0.85,
        "dantri.com.vn": 0.80,
        "vietnamnet.vn": 0.80,
        "vtv.vn": 0.85,             # Đài truyền hình
        "vov.vn": 0.85,             # Đài tiếng nói
        "nhandan.vn": 0.85,         # Báo Nhân dân
        "baochinhphu.vn": 0.90,     # Báo Chính phủ
    }

    # ========== TIER 5: INDUSTRY EXPERT - BĐS (0.75 - 0.85) ==========
    INDUSTRY_EXPERT_DOMAINS = {
        # Real Estate Official
        "batdongsan.com.vn": 0.85,
        "cafeland.vn": 0.80,
        "homedy.com": 0.75,
        "nhadatviet.vn": 0.75,
        "vars.vn": 0.85,            # Hội Môi giới BĐS VN
        "vnrea.vn": 0.85,           # Hiệp hội BĐS VN
        "horea.org.vn": 0.85,       # Hiệp hội BĐS TPHCM

        # Real Estate Research
        "savills.com.vn": 0.85,
        "cbre.com.vn": 0.85,
        "jll.com.vn": 0.85,
        "cushmanwakefield.com": 0.85,
        "colliers.com": 0.80,
    }

    # ========== TIER 6: BUSINESS NEWS (0.70 - 0.80) ==========
    BUSINESS_NEWS_DOMAINS = {
        "cafef.vn": 0.75,
        "vietstock.vn": 0.75,
        "tinnhanhchungkhoan.vn": 0.75,
        "ndh.vn": 0.70,             # Người đồng hành
        "kinhtedothi.vn": 0.70,
        "baodautu.vn": 0.75,
        "enternews.vn": 0.70,
        "forbes.vn": 0.75,
    }

    # ========== TIER 7: LOCAL/AGGREGATOR (0.50 - 0.70) ==========
    LOCAL_AGGREGATOR_DOMAINS = {
        "24h.com.vn": 0.60,
        "kenh14.vn": 0.55,
        "soha.vn": 0.60,
        "zing.vn": 0.65,
        "genk.vn": 0.55,
        "eva.vn": 0.50,
        "afamily.vn": 0.50,
        "yan.vn": 0.50,
        "tinhte.vn": 0.65,          # Tech, nhưng có BĐS
    }

    # ========== BLOCKED SOURCES (0.0 - Không sử dụng) ==========
    BLOCKED_DOMAINS = {
        # Social Media
        "facebook.com": "Mạng xã hội - không đáng tin cậy cho thông tin pháp lý/BĐS",
        "fb.com": "Facebook shortlink",
        "tiktok.com": "Mạng xã hội video ngắn - không phù hợp",
        "twitter.com": "Mạng xã hội - thông tin chưa xác minh",
        "x.com": "Twitter/X",
        "instagram.com": "Mạng xã hội hình ảnh",
        "threads.net": "Mạng xã hội",
        "zalo.me": "Tin nhắn/MXH VN",

        # Forums
        "webtretho.com": "Diễn đàn - thông tin không chính thống",
        "tinhte.vn/thread": "Forum thread",
        "voz.vn": "Diễn đàn",
        "otofun.net": "Diễn đàn",
        "reddit.com": "Diễn đàn quốc tế",
        "quora.com": "Q&A platform - thông tin chưa xác minh",

        # User Generated Content
        "medium.com": "Blog platform - chất lượng không đồng đều",
        "blogspot.com": "Blog cá nhân",
        "wordpress.com": "Blog cá nhân",
        "substack.com": "Newsletter cá nhân",

        # Wikipedia (không block hoàn toàn nhưng cảnh báo)
        # "wikipedia.org": "Wiki - cần verify nguồn gốc",

        # Spam/Low quality
        "*.blogspot.com": "Blog spam",
        "*.wordpress.com": "Blog spam",
    }

    # ========== LOW QUALITY PATTERNS (downrank) ==========
    LOW_QUALITY_PATTERNS = [
        r"forum\.",
        r"\.forum\.",
        r"/forum/",
        r"/thread/",
        r"blog\.",
        r"\.blog\.",
        r"/blog/",
        r"comment",
        r"reply",
        r"\.tumblr\.",
        r"\.wix\.",
        r"\.weebly\.",
    ]

    def __init__(self):
        """Initialize scorer với compiled patterns."""
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for performance."""
        self.low_quality_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.LOW_QUALITY_PATTERNS
        ]

    def get_source_info(self, url: str) -> SourceInfo:
        """
        Đánh giá một URL và trả về thông tin đầy đủ.

        Args:
            url: URL cần đánh giá

        Returns:
            SourceInfo với category, score, và trạng thái
        """
        if not url:
            return SourceInfo(
                url=url,
                domain="unknown",
                category=SourceCategory.UNKNOWN,
                reliability_score=0.3,
                is_blocked=False,
                reason="URL không hợp lệ"
            )

        # Extract domain
        domain = self._extract_domain(url)
        url_lower = url.lower()

        # Check blocked first
        block_reason = self._check_blocked(url_lower, domain)
        if block_reason:
            return SourceInfo(
                url=url,
                domain=domain,
                category=SourceCategory.SOCIAL_MEDIA if "facebook" in domain or "tiktok" in domain else SourceCategory.FORUM,
                reliability_score=0.0,
                is_blocked=True,
                reason=block_reason)

        # Check each tier
        category, score = self._categorize_and_score(url_lower, domain)

        # Apply low quality penalty
        if self._is_low_quality(url_lower):
            score = max(0.3, score - 0.2)
            category = SourceCategory.BLOG if score < 0.5 else category

        return SourceInfo(
            url=url,
            domain=domain,
            category=category,
            reliability_score=score,
            is_blocked=False,
            reason=f"Category: {category.value}"
        )

    def get_reliability_score(self, url: str) -> float:
        """
        Shortcut để lấy chỉ reliability score.

        Args:
            url: URL cần đánh giá

        Returns:
            float: Điểm tin cậy 0.0 - 1.0
        """
        info = self.get_source_info(url)
        return info.reliability_score

    def is_blocked(self, url: str) -> Tuple[bool, str]:
        """
        Kiểm tra xem URL có bị block không.

        Returns:
            Tuple[is_blocked, reason]
        """
        info = self.get_source_info(url)
        return info.is_blocked, info.reason

    def filter_sources(
        self,
        urls: List[str],
        min_score: float = 0.5
    ) -> List[Tuple[str, float]]:
        """
        Lọc và sắp xếp danh sách URLs theo reliability.

        Args:
            urls: Danh sách URLs
            min_score: Điểm tối thiểu để giữ lại

        Returns:
            List[(url, score)] đã sắp xếp theo score giảm dần
        """
        results = []
        for url in urls:
            info = self.get_source_info(url)
            if not info.is_blocked and info.reliability_score >= min_score:
                results.append((url, info.reliability_score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _extract_domain(self, url: str) -> str:
        """Extract domain từ URL."""
        match = re.search(r'https?://(?:www\.)?([^/]+)', url.lower())
        return match.group(1) if match else url.lower()

    def _check_blocked(self, url_lower: str, domain: str) -> Optional[str]:
        """Kiểm tra xem URL có trong blocked list không."""
        for blocked_domain, reason in self.BLOCKED_DOMAINS.items():
            if blocked_domain.startswith("*"):
                # Wildcard pattern
                pattern = blocked_domain[1:]  # Remove *
                if pattern in url_lower:
                    return reason
            elif blocked_domain in domain or blocked_domain in url_lower:
                return reason
        return None

    def _categorize_and_score(
        self,
        url_lower: str,
        domain: str
    ) -> Tuple[SourceCategory, float]:
        """Phân loại và cho điểm nguồn."""

        # Check Government
        for gov_domain, score in self.GOVERNMENT_DOMAINS.items():
            if gov_domain in domain or gov_domain in url_lower:
                return SourceCategory.GOVERNMENT, score

        # Check Legal Official
        for legal_domain, score in self.LEGAL_OFFICIAL_DOMAINS.items():
            if legal_domain in domain:
                return SourceCategory.LEGAL_OFFICIAL, score

        # Check Academic
        for academic_domain, score in self.ACADEMIC_DOMAINS.items():
            if academic_domain in domain:
                return SourceCategory.ACADEMIC, score

        # Check Major News
        for news_domain, score in self.MAJOR_NEWS_DOMAINS.items():
            if news_domain in domain:
                return SourceCategory.MAJOR_NEWS, score

        # Check Industry Expert (BĐS)
        for expert_domain, score in self.INDUSTRY_EXPERT_DOMAINS.items():
            if expert_domain in domain:
                return SourceCategory.INDUSTRY_EXPERT, score

        # Check Business News
        for biz_domain, score in self.BUSINESS_NEWS_DOMAINS.items():
            if biz_domain in domain:
                return SourceCategory.BUSINESS_NEWS, score

        # Check Local/Aggregator
        for local_domain, score in self.LOCAL_AGGREGATOR_DOMAINS.items():
            if local_domain in domain:
                return SourceCategory.AGGREGATOR, score

        # Check for .gov.vn pattern (catch-all for government)
        if ".gov.vn" in domain:
            return SourceCategory.GOVERNMENT, 0.90

        # Check for .edu.vn pattern (catch-all for education)
        if ".edu.vn" in domain or ".edu" in domain:
            return SourceCategory.ACADEMIC, 0.80

        # Default unknown
        return SourceCategory.UNKNOWN, 0.50

    def _is_low_quality(self, url_lower: str) -> bool:
        """Kiểm tra các pattern low quality."""
        for pattern in self.low_quality_regex:
            if pattern.search(url_lower):
                return True
        return False

    def get_category_description(self, category: SourceCategory) -> str:
        """Mô tả chi tiết cho từng category."""
        descriptions = {
            SourceCategory.GOVERNMENT: "Nguồn chính phủ, cơ quan nhà nước - Độ tin cậy cao nhất",
            SourceCategory.LEGAL_OFFICIAL: "Văn bản pháp luật chính thức - Rất đáng tin cậy",
            SourceCategory.ACADEMIC: "Nguồn học thuật, nghiên cứu - Đáng tin cậy cao",
            SourceCategory.MAJOR_NEWS: "Báo chí lớn, uy tín - Đáng tin cậy",
            SourceCategory.INDUSTRY_EXPERT: "Chuyên gia ngành BĐS - Đáng tin cậy cho lĩnh vực",
            SourceCategory.BUSINESS_NEWS: "Tin tức kinh doanh - Tin cậy vừa",
            SourceCategory.LOCAL_NEWS: "Báo địa phương - Cần verify",
            SourceCategory.AGGREGATOR: "Trang tổng hợp - Cần kiểm tra nguồn gốc",
            SourceCategory.BLOG: "Blog cá nhân - Độ tin cậy thấp",
            SourceCategory.SOCIAL_MEDIA: "Mạng xã hội - KHÔNG đáng tin cậy",
            SourceCategory.FORUM: "Diễn đàn - KHÔNG đáng tin cậy",
            SourceCategory.UNKNOWN: "Không xác định - Cần verify",
        }
        return descriptions.get(category, "Không xác định")


from chatbot_viva.core.singleton import singleton


@singleton
def get_reliability_scorer() -> SourceReliabilityScorer:
    """Get singleton instance."""
    return SourceReliabilityScorer()


# Convenience functions
def get_source_reliability(url: str) -> float:
    """Quick function để lấy reliability score."""
    return get_reliability_scorer().get_reliability_score(url)


def is_source_blocked(url: str) -> Tuple[bool, str]:
    """Quick function để check blocked."""
    return get_reliability_scorer().is_blocked(url)


def get_source_category(url: str) -> SourceCategory:
    """Quick function để lấy category."""
    return get_reliability_scorer().get_source_info(url).category


def get_source_type(url: str) -> SourceType:
    """
    Lay loai nguon don gian (3 loai) tu URL.

    Returns:
        SourceType: NEWS, REAL_ESTATE, hoac LEGAL
    """
    info = get_reliability_scorer().get_source_info(url)
    category = info.category

    # Map category to simple type
    if category in [SourceCategory.GOVERNMENT,
                    SourceCategory.LEGAL_OFFICIAL, SourceCategory.ACADEMIC]:
        return SourceType.LEGAL
    elif category == SourceCategory.INDUSTRY_EXPERT:
        return SourceType.REAL_ESTATE
    else:
        # MAJOR_NEWS, BUSINESS_NEWS, LOCAL_NEWS, AGGREGATOR, etc -> NEWS
        return SourceType.NEWS


def get_source_type_label(url: str) -> str:
    """Lay label hien thi cho loai nguon."""
    source_type = get_source_type(url)
    return source_type.value
