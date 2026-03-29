"""Constants for the chatbot application."""

from __future__ import annotations

import re
from typing import Dict, List

USD_TO_VND = 25000
AREA_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:m2|m\u00b2|mét vuông|met vuong|m2)",
    re.IGNORECASE,
)
CRYPTO_SYMBOL = "BTCUSDT"
CRYPTO_LABEL = "Bitcoin (BTC)"
PRECIOUS_METAL_NAME = "gold"
PRECIOUS_METAL_LABEL = "Vàng (XAU)"

CRYPTO_KEYWORDS = [
    "bitcoin",
    "btc",
    "eth",
    "ethereum",
    "coin",
    "crypto",
    "tiền ảo",
    "tỷ giá btc",
    "giá btc",
]

PRECIOUS_METAL_KEYWORDS = [
    "giá vàng",
    "vàng sjc",
    "xau",
    "gold",
    "giá xau",
    "giá kim",
    "giá kim loại quý",
]

OTHER_FINANCE_KEYWORDS = [
    "lãi suất",
    "thị trường tài chính",
    "thị trường bất động sản hôm nay",
    "thị trường bds",
    "chỉ số chứng khoán",
]

FINANCE_KEYWORDS = list(dict.fromkeys(
    CRYPTO_KEYWORDS + PRECIOUS_METAL_KEYWORDS
    + OTHER_FINANCE_KEYWORDS
))

PROPERTY_PRICE_DATA: List[Dict[str,
                               str | float | List[str]]] = [{"name": "Quận 1, TP. Hồ Chí Minh",
                                                             "aliases": ["quận 1",
                                                                         "quan 1",
                                                                         "q1",
                                                                         "district 1",
                                                                         "bến nghé",
                                                                         "đồng khởi",
                                                                         "bến thành"],
                                                             "min_price_million": 210,
                                                             "max_price_million": 260,
                                                             "trend": "Nguồn cung cực kỳ hạn chế, giao dịch chủ yếu ở nhà phố và căn hộ hạng sang.",
                                                             "drivers": "Trung tâm tài chính, nhu cầu thuê cao từ khối FDI, biên lợi nhuận cho thuê tốt.",
                                                             },
                                                            {"name": "Thành phố Thủ Đức, TP. Hồ Chí Minh",
                                                             "aliases": ["thủ đức",
                                                                         "thu duc",
                                                                         "thành phố thủ đức",
                                                                         "thanh pho thu duc",
                                                                         "thuduc"],
                                                             "min_price_million": 95,
                                                             "max_price_million": 145,
                                                             "trend": "Hưởng lợi từ hệ thống metro, các khu công nghệ cao và nguồn cung căn hộ mới.",
                                                             "drivers": "Hạ tầng kết nối mạnh, nhu cầu ở thực lớn từ chuyên gia và kỹ sư.",
                                                             },
                                                            {"name": "Quận 7, TP. Hồ Chí Minh",
                                                             "aliases": ["quận 7",
                                                                         "quan 7",
                                                                         "q7",
                                                                         "district 7",
                                                                         "phú mỹ hưng"],
                                                             "min_price_million": 120,
                                                             "max_price_million": 165,
                                                             "trend": "Nguồn cung cao cấp khá ổn định, tỷ lệ hấp thụ ở mức tốt.",
                                                             "drivers": "Khu đô thị Phú Mỹ Hưng hoàn thiện hạ tầng, nhiều tiện ích quốc tế.",
                                                             },
                                                            {"name": "Quận Hoàn Kiếm, Hà Nội",
                                                             "aliases": ["hoàn kiếm",
                                                                         "hoan kiem",
                                                                         "quận hoàn kiếm",
                                                                         "hoankiem"],
                                                             "min_price_million": 185,
                                                             "max_price_million": 230,
                                                             "trend": "Đất lõi thủ đô khan hiếm, giá duy trì ở mức rất cao.",
                                                             "drivers": "Giá trị thương mại lớn, lượng khách du lịch và dịch vụ cao cấp ổn định.",
                                                             },
                                                            {"name": "Quận Cầu Giấy, Hà Nội",
                                                             "aliases": ["cầu giấy",
                                                                         "cau giay",
                                                                         "quận cầu giấy"],
                                                             "min_price_million": 110,
                                                             "max_price_million": 150,
                                                             "trend": "Khu vực tập trung văn phòng, trường đại học và chuyên gia nước ngoài.",
                                                             "drivers": "Hạ tầng đồng bộ, nhu cầu thuê căn hộ dịch vụ và officetel cao.",
                                                             },
                                                            {"name": "Quận Hải Châu, Đà Nẵng",
                                                             "aliases": ["hải châu",
                                                                         "hai chau",
                                                                         "đà nẵng",
                                                                         "da nang",
                                                                         "quận hải châu"],
                                                             "min_price_million": 70,
                                                             "max_price_million": 95,
                                                             "trend": "Thị trường phục hồi theo du lịch, nhu cầu mua để nghỉ dưỡng tăng.",
                                                             "drivers": "Vị trí trung tâm thành phố biển, hạ tầng du lịch hoàn thiện.",
                                                             },
                                                            {"name": "Thành phố Dĩ An, Bình Dương",
                                                             "aliases": ["dĩ an",
                                                                         "di an",
                                                                         "thành phố dĩ an"],
                                                             "min_price_million": 45,
                                                             "max_price_million": 65,
                                                             "trend": "Nguồn cầu bền vững từ chuyên gia tại các khu công nghiệp.",
                                                             "drivers": "Giáp TP.HCM, quỹ đất còn, giá mềm hơn so với TP.Thủ Đức.",
                                                             },
                                                            {"name": "Thành phố Biên Hòa, Đồng Nai",
                                                             "aliases": ["biên hòa",
                                                                         "bien hoa",
                                                                         "đồng nai",
                                                                         "dong nai",
                                                                         "tp biên hòa"],
                                                             "min_price_million": 40,
                                                             "max_price_million": 60,
                                                             "trend": "Giá tăng nhờ hạ tầng cao tốc và sân bay Long Thành.",
                                                             "drivers": "Kết nối cao tốc, lượng chuyên gia lớn từ các KCN lân cận.",
                                                             },
                                                            ]

# Suggested questions for the chatbot
SUGGESTED_QUESTIONS = [
    "Điều kiện chuyển nhượng quyền sử dụng đất là gì?",
    "Thủ tục mua bán nhà đất cần những giấy tờ nào?",
    "Cách tính thuế khi chuyển nhượng bất động sản?",
    "Quy định về đặt cọc khi mua bán nhà đất?",
    "Thời hạn cấp sổ đỏ sau khi hoàn tất giao dịch?"
]
