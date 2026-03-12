from __future__ import annotations

from datetime import date
from typing import Any

from utils import clean_text, normalize_link, normalize_platform, parse_date_range_to_iso


def normalize_official_rows(raw_rows: list[dict[str, Any]], default_category: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in raw_rows:
        title = clean_text(row.get("title", ""), 120)
        link = normalize_link(row.get("link", ""), row.get("source_url", ""))
        if not title or not link.startswith("http"):
            continue

        platform = normalize_platform(row.get("platform_hint") or row.get("platform") or "")
        if not platform:
            continue

        context_text = clean_text(row.get("context", "") or row.get("content", ""), 300)
        pub_date = row.get("pub_date")
        pub_date_context = None
        if isinstance(pub_date, str):
            try:
                pub_date_context = date.fromisoformat(pub_date)
            except ValueError:
                pub_date_context = None
        start_date = row.get("start_date")
        end_date = row.get("end_date")
        if not start_date or not end_date:
            date_source_text = row.get("date_text", "") or context_text
            start_date, end_date = parse_date_range_to_iso(date_source_text, today=pub_date_context)
        if not start_date and pub_date:
            start_date = pub_date
        if not end_date and pub_date:
            end_date = pub_date
        if not start_date:
            start_date = date.today().isoformat()
        if not end_date:
            end_date = start_date

        normalized.append(
            {
                "platform": platform,
                "sale_name": title,
                "start_date": start_date,
                "end_date": end_date,
                "category": row.get("category_hint") or default_category,
                "link": link,
                "description": context_text or title,
                "source_type": row.get("source_type", "crawler"),
                "signal_type": row.get("signal_type", "detail"),
                "confidence_score": row.get("confidence_score"),
                "source_url": row.get("source_url") or link,
                "image_url": row.get("image_url"),
                "status": row.get("status", "published"),
                "review_status": row.get("review_status"),
                "publish_status": row.get("publish_status"),
                "sale_tier": row.get("sale_tier"),
                "importance_score": row.get("importance_score"),
                "filter_reason": row.get("filter_reason"),
                "publisher": row.get("publisher"),
                "pub_date": row.get("pub_date"),
            }
        )
    return normalized


def normalize_community_rows(raw_rows: list[dict[str, Any]], source_site: str) -> list[dict[str, Any]]:
    from utils.community_category import classify_community_category

    normalized: list[dict[str, Any]] = []
    for row in raw_rows:
        title = clean_text(row.get("title", ""), 160)
        link = normalize_link(row.get("link", ""), row.get("source_url", ""))
        content = clean_text(row.get("content", "") or row.get("context", ""), 600)
        if not title or not link.startswith("http"):
            continue

        # 자동 카테고리 분류
        categories = classify_community_category(title, content)

        normalized.append(
            {
                "title": title,
                "content": content,
                "link": link,
                "platform": normalize_platform(row.get("platform_hint") or row.get("platform") or ""),
                "source_site": source_site,
                "signal_type": row.get("signal_type", "community"),
                "confidence_score": row.get("confidence_score"),
                "source_url": row.get("source_url") or link,
                "image_url": row.get("image_url"),
                "review_status": "pending",
                "sale_tier": None,
                "importance_score": None,
                "filter_reason": None,
                "category": categories,
                "raw_payload": row,
            }
        )
    return normalized
