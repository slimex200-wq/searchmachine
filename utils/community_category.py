"""커뮤니티 게시글 자동 카테고리 분류기.

프론트엔드 탭: 전체 / 세일 정보(sale_info) / 핫딜(hot_deal) / 쇼핑 팁(shopping_tip)
"""
from __future__ import annotations

import re

# ── 카테고리별 키워드 ──

SALE_INFO_KEYWORDS = (
    "세일", "sale", "할인", "행사", "기획전", "프로모션",
    "이벤트", "시즌오프", "브랜드위크", "페스타",
    "~까지", "기간", "전단", "오픈", "런칭",
)

HOT_DEAL_KEYWORDS = (
    "특가", "핫딜", "hot deal", "최저가", "역대급",
    "파격", "반값", "꿀", "득템", "지름",
    "무료배송", "무배", "1+1", "2+1",
    "원)", "원/", "달러", "$",
)

SHOPPING_TIP_KEYWORDS = (
    "팁", "tip", "꿀팁", "추천", "비교",
    "리뷰", "후기", "사용기", "개봉기",
    "가이드", "방법", "노하우", "정리",
    "vs", "비교", "어떤게", "뭐가",
)

# 가격 패턴: (12,345원), ($47.41) 등
PRICE_PATTERN = re.compile(r"[\d,]+원|[\$€]\s*[\d,.]+|\d+만원")


def classify_community_category(title: str, content: str = "") -> list[str]:
    """제목과 내용을 분석하여 카테고리 리스트 반환.

    하나의 게시글이 여러 카테고리에 해당할 수 있음.
    아무것도 매칭 안 되면 빈 리스트 반환 (프론트에서 "전체"에만 표시).
    """
    text = f"{title} {content}".lower()
    categories: list[str] = []

    # 핫딜 판별 (가격이 포함되어 있거나 핫딜 키워드)
    has_price = bool(PRICE_PATTERN.search(f"{title} {content}"))
    hot_deal_hits = sum(1 for kw in HOT_DEAL_KEYWORDS if kw in text)
    if has_price or hot_deal_hits >= 1:
        categories.append("hot_deal")

    # 세일 정보 판별
    sale_hits = sum(1 for kw in SALE_INFO_KEYWORDS if kw in text)
    if sale_hits >= 1:
        categories.append("sale_info")

    # 쇼핑 팁 판별
    tip_hits = sum(1 for kw in SHOPPING_TIP_KEYWORDS if kw in text)
    if tip_hits >= 1:
        categories.append("shopping_tip")

    # 아무것도 안 걸리면 내용에 가격이 있으면 핫딜로
    if not categories and has_price:
        categories.append("hot_deal")

    return categories
