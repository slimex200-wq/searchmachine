from __future__ import annotations

import os
from typing import Any

import requests
from bs4 import BeautifulSoup

from utils import estimate_relevance_score, infer_platform_from_text, normalize_link, normalize_space, should_keep_community_post

GENERIC_EXCLUDE_TITLES = {"쿠폰게시판", "다운로드 쿠폰", "직구쿠폰"}


def _seed_urls() -> list[str]:
    return [
        "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu",
        "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu4",
    ]


def _is_low_quality_title(title: str) -> bool:
    t = normalize_space(title)
    if t in GENERIC_EXCLUDE_TITLES:
        return True
    if len(t) <= 8 and ("쿠폰" in t or "할인" in t):
        return True
    return False


def _extract_raw(html: str, source_url: str, limit: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    seen_links: set[str] = set()

    for a in soup.select("a[href]"):
        title = normalize_space(a.get_text(" ", strip=True))
        if len(title) < 4:
            continue
        if _is_low_quality_title(title):
            continue
        if not should_keep_community_post(title):
            continue

        link = normalize_link(a.get("href", ""), source_url)
        if not link or link in seen_links:
            continue
        seen_links.add(link)

        context = normalize_space(a.parent.get_text(" ", strip=True) if a.parent else title)
        platform = infer_platform_from_text(f"{title} {context}")
        rows.append(
            {
                "title": title,
                "content": context,
                "link": link,
                "source_url": source_url,
                "source_site": "ppomppu",
                "platform_hint": platform,
                "relevance_score": estimate_relevance_score(title=title, body=context, platform=platform),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _save_snapshot(debug_dir: str, source: str, idx: int, html: str) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{source}_{idx}.html")
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(html)


def scrape_ppomppu(
    timeout_seconds: int = 20,
    limit: int = 20,
    debug_save_html: bool = True,
    debug_dir: str = "scraper_debug",
) -> dict[str, Any]:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    all_rows: list[dict[str, Any]] = []
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
            if debug_save_html:
                _save_snapshot(debug_dir, "ppomppu", i, html)
            if r.status_code >= 400:
                continue
            before = len(all_rows)
            all_rows.extend(_extract_raw(html, url, max(1, limit - len(all_rows))))
            debug["raw_candidates"] += max(0, len(all_rows) - before)
            debug["filtered_candidates"] = len(all_rows)
            if len(all_rows) >= limit:
                break
        except requests.RequestException:
            debug["http_status"].append("ERR")
            debug["html_length"].append("0")
            debug["reasons"].append("request_error")
            continue

    return {"rows": all_rows[:limit], "debug": debug}

