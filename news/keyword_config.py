from __future__ import annotations

PLATFORM_NEWS_QUERIES: dict[str, list[str]] = {
    "musinsa": [
        "무신사 뷰티 페스타",
        "무신사 할인 행사",
    ],
    "wconcept": [
        "W컨셉 위캔드오프",
        "W컨셉 할인 행사",
    ],
    "29cm": [
        "29CM 이구홈위크",
        "29CM 할인 행사",
    ],
    "ssg": [
        "SSG 쓱세일",
        "SSG 할인 행사",
    ],
    "oliveyoung": [
        "올영세일",
        "올리브영 할인 행사",
        "올리브영 세일",
    ],
    "coupang": [
        "쿠팡 할인 행사",
        "쿠팡 와우 세일",
        "쿠팡 로켓와우 세일",
    ],
    "ohouse": [
        "오늘의집 할인 행사",
        "오늘의집 세일",
        "오늘의집 리빙 페스타",
    ],
    "kream": [
        "KREAM 할인 행사",
        "KREAM 위크",
        "크림 할인 행사",
        "크림 세일",
        "크림 한정판 위크",
        "KREAM 스니커즈 세일",
        "크림 리셀 페스타",
    ],
}

PLATFORM_HINTS: dict[str, tuple[str, ...]] = {
    "musinsa": ("무신사", "MUSINSA"),
    "wconcept": ("W컨셉", "W CONCEPT", "Wconcept"),
    "29cm": ("29CM", "이구홈위크"),
    "ssg": ("SSG", "쓱데이", "쓱세일"),
    "oliveyoung": ("올리브영", "Olive Young", "올영"),
    "coupang": ("쿠팡", "Coupang", "로켓와우"),
    "ohouse": ("오늘의집", "오늘의 집", "오하우스", "Ohouse", "ohouse"),
    "kream": ("KREAM", "크림", "한정판", "리셀"),
}

INCLUDE_PRIORITY_KEYWORDS = (
    "세일",
    "할인",
    "브랜드위크",
    "블랙프라이데이",
    "팝업위크",
    "이구홈위크",
    "쓱데이",
    "페스타",
    "기획전",
    "대규모",
    "최대",
    "역대 최대",
    "쓱세일",
    "올영세일",
    "위캔드오프",
    "뷰티 페스타",
    "할인 행사",
    "한정판 위크",
    "리셀 페스타",
)

EXCLUDE_PRIORITY_KEYWORDS = (
    "체험단",
    "사은품",
    "응모",
    "샘플",
    "쿠폰",
    "카드 할인",
    "증정",
    "단독 발매",
    "업데이트",
    "1개 상품",
    "한정 수량",
)
