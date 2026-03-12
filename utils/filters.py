from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher
from typing import Any

from utils.normalize import normalize_space

INCLUDE_KEYWORDS = ("세일", "할인", "특가", "쿠폰", "행사", "페어", "브랜드위크", "시즌오프")
EXCLUDE_KEYWORDS = ("품절", "종료", "후기", "반품", "잡담")

PLATFORM_SYNONYMS: dict[str, tuple[str, ...]] = {
    "올리브영": ("올영", "올리브영", "oliveyoung", "olive young"),
    "무신사": ("무신사", "musinsa"),
    "오늘의집": ("오늘의집", "오하우스", "ohouse"),
    "쿠팡": ("쿠팡", "coupang"),
    "SSG": ("ssg", "신세계", "쓱"),
    "KREAM": ("kream", "크림"),
    "29CM": ("29cm",),
    "WCONCEPT": ("wconcept", "w concept", "더블유컨셉", "더블유 컨셉"),
}

DEFAULT_TARGET_PLATFORMS = ("쿠팡", "올리브영", "무신사", "KREAM", "SSG", "오늘의집", "29CM")

STRONG_POSITIVE_KEYWORDS = (
    "블랙프라이데이",
    "black friday",
    "브랜드위크",
    "brand week",
    "시즌오프",
    "season off",
    "메가세일",
    "mega sale",
    "빅세일",
    "big sale",
    "연말결산",
    "결산세일",
    "super sale",
    "슈퍼세일",
)
MEDIUM_POSITIVE_KEYWORDS = (
    "세일",
    "sale",
    "이벤트",
    "event",
    "기획전",
    "promotion",
    "프로모션",
    "페스타",
    "festa",
    "할인전",
)
WIDE_SCOPE_KEYWORDS = (
    "전품목",
    "전체",
    "카테고리",
    "category",
    "전 브랜드",
    "all brands",
    "대규모",
    "메인 행사",
    "시즌",
    "season",
    "월간",
    "monthly",
)
STRONG_NEGATIVE_KEYWORDS = (
    "타임딜",
    "time deal",
    "오늘만",
    "today only",
    "래플",
    "raffle",
    "출석체크",
    "응모",
    "사은품",
    "giveaway",
)
MEDIUM_NEGATIVE_KEYWORDS = (
    "쿠폰",
    "coupon",
    "적립금",
    "포인트",
    "point",
    "카드 할인",
    "청구할인",
    "선착순",
    "gift",
)


def should_keep_community_post(title: str, body: str = "") -> bool:
    text = normalize_space(f"{title} {body}").lower()
    if any(bad in text for bad in EXCLUDE_KEYWORDS):
        return False
    return any(good in text for good in INCLUDE_KEYWORDS)


def normalize_platform(value: str | None) -> str | None:
    if not value:
        return None
    text = normalize_space(value).lower()
    for platform, aliases in PLATFORM_SYNONYMS.items():
        if any(alias in text for alias in aliases):
            return platform
    return None


def infer_platform_from_text(text: str) -> str | None:
    return normalize_platform(text)


def is_target_platform(platform: str | None, targets: tuple[str, ...]) -> bool:
    if not platform:
        return False
    return platform in set(targets)


def estimate_relevance_score(title: str, body: str = "", platform: str | None = None) -> int:
    text = normalize_space(f"{title} {body}").lower()
    score = 0
    if platform:
        score += 45
    score += 10 * sum(1 for kw in INCLUDE_KEYWORDS if kw in text)
    score -= 20 * sum(1 for kw in EXCLUDE_KEYWORDS if kw in text)
    return max(score, 0)


def canonical_title(title: str) -> str:
    text = normalize_space(title).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_similar_title(a: str, b: str, threshold: float = 0.9) -> bool:
    ca, cb = canonical_title(a), canonical_title(b)
    if not ca or not cb:
        return False
    return SequenceMatcher(None, ca, cb).ratio() >= threshold


def _safe_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [kw for kw in keywords if kw.lower() in text]


def compute_sale_classification(
    title: str,
    description: str = "",
    link: str = "",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    text = normalize_space(f"{title} {description}").lower()
    link_text = normalize_space(link).lower()
    reasons: list[str] = []
    score = 0

    strong_positive_hits = _keyword_hits(text, STRONG_POSITIVE_KEYWORDS)
    medium_positive_hits = _keyword_hits(text, MEDIUM_POSITIVE_KEYWORDS)
    wide_scope_hits = _keyword_hits(text, WIDE_SCOPE_KEYWORDS)
    strong_negative_hits = _keyword_hits(text, STRONG_NEGATIVE_KEYWORDS)
    medium_negative_hits = _keyword_hits(text, MEDIUM_NEGATIVE_KEYWORDS)

    if strong_positive_hits:
        score += 3
        reasons.append(f"strong_positive:{strong_positive_hits[0]}")
    if medium_positive_hits:
        score += 2
        reasons.append(f"medium_positive:{medium_positive_hits[0]}")
    if wide_scope_hits:
        score += 2
        reasons.append(f"wide_scope:{wide_scope_hits[0]}")
    if any(token in link_text for token in ("event", "events", "sale", "promotion", "exhibition", "plan", "campaign")):
        score += 2
        reasons.append("official_event_url")

    s = _safe_date(start_date)
    e = _safe_date(end_date)
    if s and e:
        duration = (e - s).days + 1
        if duration >= 3:
            score += 2
            reasons.append("duration_gte_3d")
        elif duration <= 1:
            score -= 2
            reasons.append("short_duration")

    if strong_negative_hits:
        score -= 4
        reasons.append(f"strong_negative:{strong_negative_hits[0]}")
    if medium_negative_hits:
        score -= 2
        reasons.append(f"medium_negative:{medium_negative_hits[0]}")

    if score >= 6:
        sale_tier = "major"
    elif score >= 2:
        sale_tier = "minor"
    else:
        sale_tier = "excluded"

    return {
        "sale_tier": sale_tier,
        "importance_score": score,
        "filter_reason": ",".join(reasons) if reasons else "no_signal",
    }
