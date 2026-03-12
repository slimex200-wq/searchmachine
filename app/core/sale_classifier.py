from __future__ import annotations

import re
from datetime import date
from typing import Iterable

from app.core.keyword_rules_v2 import (
    DISCOUNT_KEYWORDS,
    DISCOUNT_PERCENT_PATTERN,
    MEDIUM_NEGATIVE_KEYWORDS,
    MEDIUM_POSITIVE_KEYWORDS,
    PLATFORM_MEGA_SALES,
    STRONG_NEGATIVE_KEYWORDS,
    STRONG_POSITIVE_KEYWORDS,
    WIDE_SCOPE_KEYWORDS,
)


def _hits(text: str, keywords: Iterable[str]) -> list[str]:
    lowered = text.lower()
    return [kw for kw in keywords if kw.lower() in lowered]


def _safe_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def _extract_max_discount_percent(text: str) -> int | None:
    """텍스트에서 할인율 숫자를 추출하여 가장 큰 값 반환."""
    matches = re.findall(DISCOUNT_PERCENT_PATTERN, text)
    if not matches:
        return None
    percents = [int(m) for m in matches if 10 <= int(m) <= 99]
    return max(percents) if percents else None


def classify_sale_importance(
    title: str,
    description: str,
    link: str,
    start_date: str | None,
    end_date: str | None,
    signal_type: str = "detail",
    confidence_score: float | None = None,
    platform: str | None = None,
    source_page_count: int = 1,
) -> tuple[str, int, str]:
    """
    개선된 세일 중요도 분류기 (0~100점 스케일).

    변경 사항:
    - 점수 범위: 0~100 (기존 약 -8~12)
    - 플랫폼별 대형 세일 자동 인식
    - 할인율/금액 키워드 인식
    - 뉴스 소스 패널티 제거 + 다중 기사 보너스
    """
    text = f"{title} {description}".lower()
    link_text = (link or "").lower()
    score = 0
    reasons: list[str] = []

    # ── 1. 플랫폼별 대형 세일 매칭 (최대 +30) ──
    mega_matched = False
    if platform:
        mega_keywords = PLATFORM_MEGA_SALES.get(platform, ())
        mega_hits = [kw for kw in mega_keywords if kw.lower() in text]
        if mega_hits:
            score += 30
            mega_matched = True
            reasons.append(f"platform_mega_sale:{mega_hits[0]}")

    # ── 2. 키워드 기반 점수 (최대 +35) ──
    sp = _hits(text, STRONG_POSITIVE_KEYWORDS)
    mp = _hits(text, MEDIUM_POSITIVE_KEYWORDS)
    ws = _hits(text, WIDE_SCOPE_KEYWORDS)

    if sp:
        # 플랫폼 메가세일과 중복이면 축소 가점
        bonus = 10 if mega_matched else 15
        score += bonus
        reasons.append(f"strong_positive:{sp[0]}")
    if mp:
        score += 10
        reasons.append(f"medium_positive:{mp[0]}")
    if ws:
        score += 10
        reasons.append(f"wide_scope:{ws[0]}")

    # 공식 이벤트 URL
    event_url_tokens = ("event", "events", "sale", "promotion", "exhibition", "plan", "campaign")
    if any(x in link_text for x in event_url_tokens):
        score += 8
        reasons.append("official_event_url")

    # ── 3. 할인율/금액 인식 (최대 +15) ──
    discount_hits = _hits(text, DISCOUNT_KEYWORDS)
    max_percent = _extract_max_discount_percent(text)

    if max_percent and max_percent >= 50:
        score += 15
        reasons.append(f"high_discount:{max_percent}%")
    elif max_percent and max_percent >= 30:
        score += 10
        reasons.append(f"medium_discount:{max_percent}%")
    elif discount_hits:
        score += 8
        reasons.append(f"discount_keyword:{discount_hits[0]}")

    # ── 4. 소스 타입 보정 (뉴스 패널티 제거) ──
    signal = (signal_type or "detail").lower()
    # 기존: news=-1, community=-2 → 개선: news=0, community=-5
    surface_adjustments = {
        "detail": 5,
        "event_hub": 3,
        "homepage": 0,
        "news": 0,       # 패널티 제거!
        "community": -5,
    }
    adj = surface_adjustments.get(signal, 0)
    score += adj
    reasons.append(f"signal_type:{signal}")

    # ── 5. 다중 기사/페이지 보너스 (최대 +15) ──
    if source_page_count >= 5:
        score += 15
        reasons.append(f"multi_source:{source_page_count}pages")
    elif source_page_count >= 3:
        score += 10
        reasons.append(f"multi_source:{source_page_count}pages")
    elif source_page_count >= 2:
        score += 5
        reasons.append(f"multi_source:{source_page_count}pages")

    # ── 6. 신뢰도 점수 ──
    if confidence_score is not None:
        if confidence_score >= 0.85:
            score += 8
            reasons.append("confidence_gte_0.85")
        elif confidence_score >= 0.65:
            score += 4
            reasons.append("confidence_gte_0.65")
        elif confidence_score <= 0.4:
            score -= 5
            reasons.append("confidence_lte_0.4")

    # ── 7. 기간 보정 ──
    s = _safe_date(start_date)
    e = _safe_date(end_date)
    if s and e:
        days = (e - s).days + 1
        if days >= 7:
            score += 8
            reasons.append("duration_gte_7d")
        elif days >= 3:
            score += 5
            reasons.append("duration_gte_3d")
        elif days <= 1:
            score -= 8
            reasons.append("short_duration")

    # ── 8. 감점 키워드 ──
    sn = _hits(text, STRONG_NEGATIVE_KEYWORDS)
    mn = _hits(text, MEDIUM_NEGATIVE_KEYWORDS)

    if sn:
        score -= 15
        reasons.append(f"strong_negative:{sn[0]}")
    if mn:
        score -= 8
        reasons.append(f"medium_negative:{mn[0]}")

    # ── 9. 최종 클램핑 & 분류 ──
    score = max(0, min(100, score))

    if score >= 35:
        tier = "major"
    elif score >= 15:
        tier = "minor"
    else:
        tier = "excluded"

    return tier, score, ",".join(reasons) if reasons else "no_signal"
