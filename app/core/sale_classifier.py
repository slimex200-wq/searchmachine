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
    matches = re.findall(DISCOUNT_PERCENT_PATTERN, text)
    if not matches:
        return None
    percents = [int(match) for match in matches if 10 <= int(match) <= 99]
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
    text = f"{title} {description}".lower()
    link_text = (link or "").lower()
    score = 0
    reasons: list[str] = []

    mega_matched = False
    if platform:
        mega_keywords = PLATFORM_MEGA_SALES.get(platform, ())
        mega_hits = [kw for kw in mega_keywords if kw.lower() in text]
        if mega_hits:
            score += 3
            mega_matched = True
            reasons.append(f"platform_mega_sale:{mega_hits[0]}")

    strong_positive_hits = _hits(text, STRONG_POSITIVE_KEYWORDS)
    medium_positive_hits = _hits(text, MEDIUM_POSITIVE_KEYWORDS)
    wide_scope_hits = _hits(text, WIDE_SCOPE_KEYWORDS)

    if strong_positive_hits:
        score += 2 if mega_matched else 3
        reasons.append(f"strong_positive:{strong_positive_hits[0]}")
    if medium_positive_hits:
        score += 2
        reasons.append(f"medium_positive:{medium_positive_hits[0]}")
    if wide_scope_hits:
        score += 2
        reasons.append(f"wide_scope:{wide_scope_hits[0]}")

    event_url_tokens = ("event", "events", "sale", "promotion", "exhibition", "plan", "campaign")
    if any(token in link_text for token in event_url_tokens):
        score += 2
        reasons.append("official_event_url")

    discount_hits = _hits(text, DISCOUNT_KEYWORDS)
    max_percent = _extract_max_discount_percent(text)
    if max_percent and max_percent >= 50:
        score += 3
        reasons.append(f"high_discount:{max_percent}%")
    elif max_percent and max_percent >= 30:
        score += 2
        reasons.append(f"medium_discount:{max_percent}%")
    elif discount_hits:
        score += 1
        reasons.append(f"discount_keyword:{discount_hits[0]}")

    signal = (signal_type or "detail").lower()
    surface_adjustments = {
        "detail": 1,
        "event_hub": 0,
        "homepage": 0,
        "news": -1,
        "community": -2,
    }
    score += surface_adjustments.get(signal, 0)
    reasons.append(f"signal_type:{signal}")

    if source_page_count >= 5:
        score += 2
        reasons.append(f"multi_source:{source_page_count}pages")
    elif source_page_count >= 2:
        score += 1
        reasons.append(f"multi_source:{source_page_count}pages")

    if confidence_score is not None:
        if confidence_score >= 0.85:
            score += 1
            reasons.append("confidence_gte_0.85")
        elif confidence_score >= 0.65:
            score += 1
            reasons.append("confidence_gte_0.65")
        elif confidence_score <= 0.4:
            score -= 1
            reasons.append("confidence_lte_0.4")

    start = _safe_date(start_date)
    end = _safe_date(end_date)
    if start and end:
        duration = (end - start).days + 1
        if duration >= 7:
            score += 2
            reasons.append("duration_gte_7d")
        elif duration >= 3:
            score += 2
            reasons.append("duration_gte_3d")
        elif duration <= 1:
            score -= 2
            reasons.append("short_duration")

    strong_negative_hits = _hits(text, STRONG_NEGATIVE_KEYWORDS)
    medium_negative_hits = _hits(text, MEDIUM_NEGATIVE_KEYWORDS)
    if strong_negative_hits:
        score -= 4
        reasons.append(f"strong_negative:{strong_negative_hits[0]}")
    if medium_negative_hits:
        score -= 2
        reasons.append(f"medium_negative:{medium_negative_hits[0]}")

    score = max(0, score)
    if score >= 4:
        tier = "major"
    elif score >= 1:
        tier = "minor"
    else:
        tier = "excluded"

    return tier, score, ",".join(reasons) if reasons else "no_signal"
