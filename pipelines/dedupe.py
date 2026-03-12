from __future__ import annotations

from typing import Any

from utils import canonical_title


def _dedupe_key(payload: dict[str, Any], title_key: str) -> tuple[str, str]:
    platform = str(payload.get("platform") or "").strip()
    title = canonical_title(str(payload.get(title_key) or ""))
    return platform, title


def dedupe_payloads(rows: list[dict[str, Any]], title_key: str) -> tuple[list[dict[str, Any]], int]:
    seen_links: set[str] = set()
    seen_titles: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    duplicates = 0

    for row in rows:
        link = str(row.get("link") or "").strip()
        title = str(row.get(title_key) or "").strip()
        if not link or not title:
            duplicates += 1
            continue
        if link in seen_links:
            duplicates += 1
            continue
        key = _dedupe_key(row, title_key)
        if key in seen_titles:
            duplicates += 1
            continue
        seen_links.add(link)
        seen_titles.add(key)
        deduped.append(row)

    return deduped, duplicates
