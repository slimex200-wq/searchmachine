from __future__ import annotations

from typing import Any


def init_debug_state(*, link_key: str) -> dict[str, Any]:
    return {
        "hub_url": "",
        "requested_url": [],
        "hub_http_status": "",
        "http_status": [],
        "hub_html_length": "",
        "html_length": [],
        "valid_source_page_count": 0,
        link_key: 0,
        "detail_pages_parsed": 0,
        "raw_candidates": 0,
        "fallback_candidates": 0,
        "filtered_candidates": 0,
        "items_extracted": 0,
        "parser_mode": "hub_selector",
        "failure_reason": "",
        "reasons": [],
    }


def build_signal_row(
    *,
    title: str,
    link: str,
    body_text: str,
    platform_hint: str,
    category_hint: str,
    start_date: str | None = None,
    end_date: str | None = None,
    signal_type: str = "detail",
    confidence_score: float | None = None,
    image_url: str | None = None,
) -> dict[str, Any]:
    row = {
        "title": title,
        "link": link,
        "context": body_text[:500],
        "content": body_text[:1000],
        "date_text": body_text[:300],
        "platform_hint": platform_hint,
        "category_hint": category_hint,
        "source_url": link,
        "signal_type": signal_type,
    }
    if start_date is not None:
        row["start_date"] = start_date
    if end_date is not None:
        row["end_date"] = end_date
    if confidence_score is not None:
        row["confidence_score"] = confidence_score
    if image_url:
        row["image_url"] = image_url
    return row
