from __future__ import annotations

import os
from urllib.parse import urlparse
from typing import Any

import requests
from bs4 import BeautifulSoup

from utils import normalize_link, normalize_space

KEYWORDS = ("세일", "이벤트", "기획전", "특가", "페어", "할인", "o!sale", "집요한세일", "전시")


def _seed_urls() -> list[str]:
    return [
        "https://ohou.se/exhibitions",
        "https://ohou.se/events",
        "https://store.ohou.se/exhibitions",
        "https://ohou.se/store",
    ]


def _save_snapshot(debug_dir: str, source: str, idx: int, html: str) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{source}_{idx}.html")
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(html)


def _is_allowed_ohouse_link(link: str) -> bool:
    host = urlparse(link).netloc.lower()
    return host.endswith("ohou.se") or host.endswith("store.ohou.se") or host.endswith("todayhouse.com")


def _extract_rows(candidates: list[Any], source_url: str, limit: int) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    pre_filter_count = len(candidates)

    for a in candidates:
        title = normalize_space(a.get_text(" ", strip=True))
        context = normalize_space(a.parent.get_text(" ", strip=True) if a.parent else title)
        if not title:
            continue
        if not any(k in f"{title} {context}".lower() for k in KEYWORDS):
            continue

        link = normalize_link(a.get("href", ""), source_url)
        if not link or link in seen or not _is_allowed_ohouse_link(link):
            continue
        seen.add(link)

        rows.append(
            {
                "title": title,
                "link": link,
                "context": context,
                "content": context,
                "date_text": context,
                "platform_hint": "오늘의집",
                "category_hint": "리빙",
                "source_url": source_url,
            }
        )
        if len(rows) >= limit:
            break

    return rows, pre_filter_count


def scrape_ohouse(
    timeout_seconds: int = 20,
    limit: int = 12,
    debug_save_html: bool = True,
    debug_dir: str = "scraper_debug",
) -> dict[str, Any]:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://ohou.se/"})

    rows: list[dict[str, Any]] = []
    debug = {
        "requested_url": [],
        "http_status": [],
        "html_length": [],
        "raw_candidates": 0,
        "filtered_candidates": 0,
        "reasons": [],
    }

    for i, url in enumerate(_seed_urls()):
        debug["requested_url"].append(url)
        try:
            r = s.get(url, timeout=timeout_seconds)
            html = r.text or ""
            debug["http_status"].append(str(r.status_code))
            debug["html_length"].append(str(len(html)))
            print(f"[ohouse] request={url} status={r.status_code} html_len={len(html)}")

            if debug_save_html:
                _save_snapshot(debug_dir, "ohouse", i, html)

            if r.status_code == 403:
                debug["reasons"].append("access_denied_403")

            if not html.strip():
                debug["reasons"].append("empty_html")
                continue

            soup = BeautifulSoup(html, "html.parser")
            selected = soup.select("a[href*='exhibitions'], a[href*='events'], a[href*='sale'], a[href*='store']")
            print(f"[ohouse] selector_count={len(selected)}")

            if not selected:
                debug["reasons"].append("selector_zero")
                selected = soup.select("a[href]")
                print(f"[ohouse] fallback_anchor_count={len(selected)}")

            extracted, pre_filter_count = _extract_rows(selected, url, max(1, limit - len(rows)))
            debug["raw_candidates"] += pre_filter_count
            debug["filtered_candidates"] += len(extracted)
            print(f"[ohouse] pre_filter={pre_filter_count} post_filter={len(extracted)}")

            rows.extend(extracted)
            if len(rows) >= limit:
                break
        except requests.RequestException as exc:
            debug["http_status"].append("ERR")
            debug["html_length"].append("0")
            debug["reasons"].append(f"request_error:{type(exc).__name__}")
            continue

    if not rows and debug["raw_candidates"] > 0 and debug["filtered_candidates"] == 0:
        debug["reasons"].append("filtered_all")

    return {"rows": rows[:limit], "debug": debug}
