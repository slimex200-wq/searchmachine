from __future__ import annotations

import os
from typing import Any

import requests
from bs4 import BeautifulSoup

from utils import estimate_relevance_score, infer_platform_from_text, normalize_link, normalize_space, should_keep_community_post

GENERIC_EXCLUDE_TITLES = {"알뜰구매", "오늘의유머", "문의", "잡담"}


def _seed_urls() -> list[str]:
    return [
        "https://www.clien.net/service/board/jirum",
        "https://www.clien.net/service/board/park",
    ]


def _is_low_quality_title(title: str) -> bool:
    text = normalize_space(title)
    if text in GENERIC_EXCLUDE_TITLES:
        return True
    if len(text) <= 6 and ("쿠폰" in text or "할인" in text):
        return True
    return False


def _extract_raw(html: str, source_url: str, limit: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    seen_links: set[str] = set()

    selectors = [
        ".list_item.symph_row",
        ".post-row",
        "div.list_item",
        "a.subject_fixed",
        "a.list_subject",
    ]

    candidate_nodes: list[Any] = []
    for selector in selectors:
        found = soup.select(selector)
        if found:
            candidate_nodes = found
            break

    if not candidate_nodes:
        candidate_nodes = soup.select("a[href]")

    for node in candidate_nodes:
        anchor = node if getattr(node, "name", "") == "a" else node.select_one("a[href]")
        if anchor is None:
            continue

        title = normalize_space(anchor.get_text(" ", strip=True))
        if len(title) < 4 or _is_low_quality_title(title):
            continue

        context = normalize_space(node.get_text(" ", strip=True))
        if not should_keep_community_post(title, context):
            continue

        link = normalize_link(anchor.get("href", ""), source_url)
        if not link or link in seen_links:
            continue
        seen_links.add(link)

        platform = infer_platform_from_text(f"{title} {context}")
        rows.append(
            {
                "title": title,
                "content": context,
                "link": link,
                "source_url": source_url,
                "source_site": "clien",
                "signal_type": "community",
                "confidence_score": 0.35,
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


def scrape_clien(
    timeout_seconds: int = 20,
    limit: int = 20,
    debug_save_html: bool = True,
    debug_dir: str = "scraper_debug",
) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    all_rows: list[dict[str, Any]] = []
    seen_links: set[str] = set()
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
            response = session.get(url, timeout=timeout_seconds)
            html = response.text or ""
            debug["http_status"].append(str(response.status_code))
            debug["html_length"].append(str(len(html)))
            if debug_save_html:
                _save_snapshot(debug_dir, "clien", i, html)
            if response.status_code >= 400:
                continue

            before = len(all_rows)
            extracted = _extract_raw(html, url, max(1, limit - len(all_rows)))
            for row in extracted:
                link = str(row.get("link", ""))
                if not link or link in seen_links:
                    continue
                seen_links.add(link)
                all_rows.append(row)
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
