from __future__ import annotations

from datetime import date
from typing import Iterable

from app.core.keyword_rules import (
    MEDIUM_NEGATIVE_KEYWORDS,
    MEDIUM_POSITIVE_KEYWORDS,
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


def classify_sale_importance(
    title: str,
    description: str,
    link: str,
    start_date: str | None,
    end_date: str | None,
    signal_type: str = "detail",
    confidence_score: float | None = None,
) -> tuple[str, int, str]:
    text = f"{title} {description}".lower()
    link_text = (link or "").lower()
    score = 0
    reasons: list[str] = []
    signal = (signal_type or "detail").lower()

    sp = _hits(text, STRONG_POSITIVE_KEYWORDS)
    mp = _hits(text, MEDIUM_POSITIVE_KEYWORDS)
    ws = _hits(text, WIDE_SCOPE_KEYWORDS)
    sn = _hits(text, STRONG_NEGATIVE_KEYWORDS)
    mn = _hits(text, MEDIUM_NEGATIVE_KEYWORDS)

    if sp:
        score += 3
        reasons.append(f"strong_positive:{sp[0]}")
    if mp:
        score += 2
        reasons.append(f"medium_positive:{mp[0]}")
    if ws:
        score += 2
        reasons.append(f"wide_scope:{ws[0]}")
    if any(x in link_text for x in ("event", "events", "sale", "promotion", "exhibition", "plan", "campaign")):
        score += 2
        reasons.append("official_event_url")

    surface_adjustments = {
        "detail": 1,
        "event_hub": 0,
        "homepage": -1,
        "news": -1,
        "community": -2,
    }
    score += surface_adjustments.get(signal, 0)
    reasons.append(f"signal_type:{signal}")

    if confidence_score is not None:
        if confidence_score >= 0.85:
            score += 2
            reasons.append("confidence_gte_0.85")
        elif confidence_score >= 0.65:
            score += 1
            reasons.append("confidence_gte_0.65")
        elif confidence_score <= 0.4:
            score -= 1
            reasons.append("confidence_lte_0.4")

    s = _safe_date(start_date)
    e = _safe_date(end_date)
    if s and e:
        days = (e - s).days + 1
        if days >= 3:
            score += 2
            reasons.append("duration_gte_3d")
        if days <= 1:
            score -= 2
            reasons.append("short_duration")

    if sn:
        score -= 4
        reasons.append(f"strong_negative:{sn[0]}")
    if mn:
        score -= 2
        reasons.append(f"medium_negative:{mn[0]}")

    if score >= 4:
        tier = "major"
    elif score >= 1:
        tier = "minor"
    else:
        tier = "excluded"

    return tier, score, ",".join(reasons) if reasons else "no_signal"
