from __future__ import annotations

from dataclasses import replace
from datetime import date
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urlparse

from app.core.keyword_rules import GROUPING_IGNORE_TOKENS
from app.core.models import GroupedSaleEvent, SalePage
from utils import canonical_title

PLATFORM_GROUPING_IGNORE_TOKENS = {
    "musinsa",
    "무신사",
    "wconcept",
    "w",
    "concept",
    "w컨셉",
    "29cm",
    "ssg",
    "oliveyoung",
    "olive",
    "young",
    "올리브영",
    "coupang",
    "쿠팡",
    "kream",
    "ohouse",
    "오늘의집",
}


def _safe_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def _page_rank(page: SalePage) -> tuple[int, date, int]:
    pub = _safe_date(page.pub_date)
    end = _safe_date(page.end_date)
    start = _safe_date(page.start_date)
    signal_bonus = 1 if page.source_type == "news" else 0
    return (
        signal_bonus,
        pub or end or start or date.min,
        page.importance_score,
    )


def _url_group_key(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower().strip("/")
    query = parse_qs(parsed.query)

    # Preserve event identifiers on platforms that reuse the same detail path.
    if "event.ssg.com" in host:
        event_id = query.get("nevntId", [""])[0]
        site_id = query.get("domainSiteNo", [""])[0]
        if event_id:
            return f"ssg:{event_id}:{site_id}"

    parts = [p for p in path.split("/") if p]
    return "/".join(parts[:2])


def _overlap_dates(a_start: str | None, a_end: str | None, b_start: str | None, b_end: str | None) -> bool:
    asd, aed = _safe_date(a_start), _safe_date(a_end)
    bsd, bed = _safe_date(b_start), _safe_date(b_end)
    if not asd or not aed or not bsd or not bed:
        return False
    return asd <= bed and bsd <= aed


def _event_tokens(title: str) -> set[str]:
    tokens = set(canonical_title(title).split())
    return {
        t
        for t in tokens
        if t
        and t not in GROUPING_IGNORE_TOKENS
        and t not in PLATFORM_GROUPING_IGNORE_TOKENS
    }


def _title_similarity(a: str, b: str) -> float:
    a_tokens = sorted(
        t for t in canonical_title(a).split() if t and t not in PLATFORM_GROUPING_IGNORE_TOKENS
    )
    b_tokens = sorted(
        t for t in canonical_title(b).split() if t and t not in PLATFORM_GROUPING_IGNORE_TOKENS
    )
    if a_tokens and b_tokens:
        return SequenceMatcher(None, " ".join(a_tokens), " ".join(b_tokens)).ratio()
    return SequenceMatcher(None, canonical_title(a), canonical_title(b)).ratio()


def _event_key(platform: str, title: str) -> str:
    toks = sorted(list(_event_tokens(title)))[:4]
    joined = "-".join(toks) if toks else canonical_title(title).replace(" ", "-")[:40]
    return f"{platform.lower()}::{joined}"


def _same_event(a: SalePage, b: SalePage) -> bool:
    if a.platform != b.platform:
        return False
    title_similarity = _title_similarity(a.title, b.title)
    shared_tokens = _event_tokens(a.title) & _event_tokens(b.title)

    if title_similarity >= 0.72:
        return True
    if len(shared_tokens) >= 3:
        return True
    if len(shared_tokens) >= 2 and title_similarity >= 0.6:
        return True
    if _url_group_key(a.link) and _url_group_key(a.link) == _url_group_key(b.link):
        return True
    # Date overlap alone is too broad for platform-wide campaign pages.
    # Only use overlapping dates as a grouping signal when titles are already moderately similar.
    if title_similarity >= 0.45 and _overlap_dates(a.start_date, a.end_date, b.start_date, b.end_date):
        return True
    return False


def group_sale_events(pages: list[SalePage]) -> tuple[list[GroupedSaleEvent], list[SalePage]]:
    candidate_pages = [p for p in pages if p.sale_tier in {"major", "minor"}]
    clusters: list[list[SalePage]] = []

    for page in candidate_pages:
        matched = False
        for cluster in clusters:
            if any(_same_event(page, existing) for existing in cluster):
                cluster.append(page)
                matched = True
                break
        if not matched:
            clusters.append([page])

    grouped: list[GroupedSaleEvent] = []
    pages_with_key: list[SalePage] = []

    for cluster in clusters:
        rep = max(cluster, key=_page_rank)
        key = _event_key(rep.platform, rep.title)
        updated_cluster = [replace(p, event_key=key) for p in cluster]
        pages_with_key.extend(updated_cluster)

        starts = [_safe_date(p.start_date) for p in updated_cluster if _safe_date(p.start_date)]
        ends = [_safe_date(p.end_date) for p in updated_cluster if _safe_date(p.end_date)]
        ordered_urls = [rep.link] + [p.link for p in updated_cluster if p.link != rep.link]
        grouped.append(
            GroupedSaleEvent(
                title=rep.title,
                platform=rep.platform,
                start_date=min(starts).isoformat() if starts else rep.start_date,
                end_date=max(ends).isoformat() if ends else rep.end_date,
                source_page_count=len(updated_cluster),
                grouped_urls=ordered_urls,
                importance_score=max(p.importance_score for p in updated_cluster),
                sale_tier="major" if any(p.sale_tier == "major" for p in updated_cluster) else "minor",
                filter_reason=(
                    "grouped_major_event"
                    if any(p.sale_tier == "major" for p in updated_cluster)
                    else "grouped_minor_event"
                ),
                event_key=key,
                category=rep.category,
                description=rep.description,
                source_type=rep.source_type,
                signal_type=rep.signal_type,
                confidence_score=rep.confidence_score,
                pub_date=rep.pub_date,
                image_url=rep.image_url,
                review_status=rep.review_status,
                publish_status=rep.publish_status,
            )
        )

    dedup: dict[tuple[str, str], GroupedSaleEvent] = {}
    for ev in grouped:
        dedup[(ev.platform, ev.event_key or ev.title)] = ev
    return list(dedup.values()), pages_with_key
