from __future__ import annotations

from typing import Any

from utils import compute_sale_classification, is_target_platform


def classify_sale_importance(rows: list[dict[str, Any]], title_key: str, description_key: str) -> list[dict[str, Any]]:
    classified: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        result = compute_sale_classification(
            title=str(item.get(title_key) or ""),
            description=str(item.get(description_key) or ""),
            link=str(item.get("link") or ""),
            start_date=item.get("start_date"),
            end_date=item.get("end_date"),
        )
        item.update(result)
        classified.append(item)
    return classified


def filter_major_sales(rows: list[dict[str, Any]], title_key: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    filtered_out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("sale_tier") == "major" and row.get(title_key) and row.get("link"):
            kept.append(row)
        else:
            filtered_out.append(row)
    return kept, filtered_out


def classify_community_rows(
    normalized_rows: list[dict[str, Any]],
    target_platforms: tuple[str, ...],
    enable_promotion: bool,
) -> dict[str, list[dict[str, Any]]]:
    community_upload: list[dict[str, Any]] = []
    sales_candidates: list[dict[str, Any]] = []
    review_only: list[dict[str, Any]] = []

    for row in normalized_rows:
        community_upload.append(row)
        platform = row.get("platform")
        is_major = row.get("sale_tier") == "major"

        if is_target_platform(platform, target_platforms) and is_major:
            candidate = {
                "platform": platform,
                "sale_name": row.get("title"),
                "start_date": None,
                "end_date": None,
                "category": "커뮤니티",
                "link": row.get("link"),
                "description": row.get("content") or row.get("title"),
                "source_type": "community",
                "status": "draft",
                "sale_tier": row.get("sale_tier"),
                "importance_score": row.get("importance_score"),
                "filter_reason": row.get("filter_reason"),
            }
            if enable_promotion:
                sales_candidates.append(candidate)
            else:
                review_item = dict(row)
                review_item["review_reason"] = "promotion_disabled"
                review_only.append(review_item)
        else:
            review_item = dict(row)
            if not is_target_platform(platform, target_platforms):
                review_item["review_reason"] = "platform_not_target"
            else:
                review_item["review_reason"] = "not_major_event"
            review_only.append(review_item)

    return {
        "community_upload": community_upload,
        "sales_candidates": sales_candidates,
        "review_only": review_only,
    }
