from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from utils import normalize_link, normalize_space

KEYWORDS = ("sale", "event", "promotion", "exhibition", "campaign", "benefit")


def _seed_urls() -> list[str]:
    return [
        "https://pages.coupang.com/p/158622",
        "https://pages.coupang.com/p/150093",
        "https://pages.coupang.com/p/136197",
    ]


def _save_snapshot(debug_dir: str, source: str, idx: int, html: str) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{source}_{idx}.html")
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(html)


def _is_allowed_coupang_link(link: str) -> bool:
    parsed = urlparse(link)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if not (host.endswith("coupang.com") or host.endswith("pages.coupang.com")):
        return False
    return any(token in path for token in ("/p/", "/np/campaigns", "/vp/events", "/f/"))


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
        if not link or link in seen or not _is_allowed_coupang_link(link):
            continue
        if "/products/" in link or "/vp/products/" in link:
            continue
        seen.add(link)

        rows.append(
            {
                "title": title,
                "link": link,
                "context": context,
                "content": context,
                "date_text": context,
                "platform_hint": "쿠팡",
                "category_hint": "종합",
                "source_url": source_url,
            }
        )
        if len(rows) >= limit:
            break

    return rows, pre_filter_count


def scrape_coupang(
    timeout_seconds: int = 20,
    limit: int = 12,
    debug_save_html: bool = True,
    debug_dir: str = "scraper_debug",
) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.coupang.com/",
        }
    )

    rows: list[dict[str, Any]] = []
    debug = {
        "requested_url": [],
        "http_status": [],
        "html_length": [],
        "valid_source_page_count": 0,
        "raw_candidates": 0,
        "fallback_candidates": 0,
        "filtered_candidates": 0,
        "items_extracted": 0,
        "failure_reason": "",
        "reasons": [],
    }

    for i, url in enumerate(_seed_urls()):
        debug["requested_url"].append(url)
        try:
            resp = session.get(url, timeout=timeout_seconds)
            html = resp.text or ""
            debug["http_status"].append(str(resp.status_code))
            debug["html_length"].append(str(len(html)))
            print(f"[coupang] requested_url={url}")
            print(f"[coupang] http_status={resp.status_code}")
            print(f"[coupang] html_length={len(html)}")

            if resp.status_code != 200:
                debug["reasons"].append(f"http_status_{resp.status_code}")
                if not debug["failure_reason"]:
                    debug["failure_reason"] = "all_seed_urls_failed"
                if debug_save_html:
                    _save_snapshot(debug_dir, "coupang", i, html)
                continue

            debug["valid_source_page_count"] += 1
            print(f"[coupang] valid_source_page_count={debug['valid_source_page_count']}")

            if not html.strip():
                debug["reasons"].append("empty_html")
                debug["failure_reason"] = "no_valid_source_page"
                if debug_save_html:
                    _save_snapshot(debug_dir, "coupang", i, html)
                continue

            soup = BeautifulSoup(html, "html.parser")
            selected = soup.select("a[href*='/p/'], a[href*='campaign'], a[href*='event'], a[href*='sale']")
            if not selected:
                debug["reasons"].append("selector_zero")
                fallback_selected = soup.select("a[href]")
                debug["fallback_candidates"] += len(fallback_selected)
                print(f"[coupang] fallback_candidates={len(fallback_selected)}")
                selected = fallback_selected

            extracted, pre_filter_count = _extract_rows(selected, url, max(1, limit - len(rows)))
            debug["raw_candidates"] += pre_filter_count
            debug["filtered_candidates"] += len(extracted)
            debug["items_extracted"] = len(rows) + len(extracted)
            print(f"[coupang] raw_candidates={debug['raw_candidates']}")
            print(f"[coupang] filtered_candidates={debug['filtered_candidates']}")
            print(f"[coupang] items_extracted={len(extracted)}")

            if not extracted and debug_save_html:
                _save_snapshot(debug_dir, "coupang", i, html)

            rows.extend(extracted)
            if len(rows) >= limit:
                break
        except requests.RequestException as exc:
            debug["http_status"].append("ERR")
            debug["html_length"].append("0")
            debug["reasons"].append(f"request_error:{type(exc).__name__}")
            debug["failure_reason"] = f"request_error:{type(exc).__name__}"
            print(f"[coupang] failure_reason={debug['failure_reason']}")
            continue

    if not rows:
        if debug["valid_source_page_count"] == 0:
            debug["failure_reason"] = "all_seed_urls_failed"
        elif debug["raw_candidates"] == 0:
            debug["failure_reason"] = "no_valid_source_page"
        elif debug["filtered_candidates"] == 0:
            debug["reasons"].append("filtered_all")
            debug["failure_reason"] = "filtered_all"
        elif not debug["failure_reason"]:
            debug["failure_reason"] = "no_event_candidates"
        print(f"[coupang] failure_reason={debug['failure_reason']}")

    debug["items_extracted"] = len(rows[:limit])
    return {"rows": rows[:limit], "debug": debug}
