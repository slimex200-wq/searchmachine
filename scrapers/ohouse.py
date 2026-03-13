from __future__ import annotations

import os
from urllib.parse import urlparse
from typing import Any

import requests
from bs4 import BeautifulSoup

from scrapers.browser_utils import fetch_playwright_page_html
from utils import normalize_link, normalize_space

KEYWORDS = ("세일", "이벤트", "기획전", "특가", "페어", "할인", "o!sale", "집요한세일", "전시", "페스타")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"


def _seed_urls() -> list[str]:
    return [
        "https://ohou.se/",
        "https://contents.ohou.se/",
        "https://contents.ohou.se/projects",
        "https://ohou.se/store",
    ]


def _save_snapshot(debug_dir: str, source: str, idx: int, html: str) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{source}_{idx}.html")
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(html)


def _is_allowed_ohouse_link(link: str) -> bool:
    host = urlparse(link).netloc.lower()
    parsed = urlparse(link)
    path = parsed.path.lower()
    if host.endswith("contents.ohou.se"):
        return any(token in path for token in ("/projects/", "/magazines/", "/cards/"))
    return host.endswith("ohou.se") or host.endswith("store.ohou.se") or host.endswith("todayhouse.com")


def _looks_like_access_denied(html: str) -> bool:
    lowered = html.lower()
    return "access denied" in lowered and (
        "errors.edgesuite.net" in lowered or "you don't have permission" in lowered
    )


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
    s.headers.update({"User-Agent": USER_AGENT, "Referer": "https://ohou.se/"})

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
            if _looks_like_access_denied(html):
                debug["reasons"].append("akamai_access_denied")

            should_try_browser = r.status_code == 403 or _looks_like_access_denied(html)

            if not html.strip():
                debug["reasons"].append("empty_html")
                continue

            soup = BeautifulSoup(html, "html.parser")
            selected = soup.select(
                "a[href*='exhibitions'], a[href*='events'], a[href*='sale'], a[href*='store'], "
                "a[href*='contents.ohou.se/projects'], a[href*='contents.ohou.se/magazines'], a[href*='contents.ohou.se/cards']"
            )
            print(f"[ohouse] selector_count={len(selected)}")

            if not selected:
                debug["reasons"].append("selector_zero")
                if should_try_browser:
                    try:
                        browser_html, browser_reasons = fetch_playwright_page_html(
                            url,
                            viewport={"width": 1440, "height": 2200},
                            user_agent=USER_AGENT,
                        )
                        debug["reasons"].extend(browser_reasons)
                        print(f"[ohouse] browser_html_len={len(browser_html)}")
                        if debug_save_html:
                            _save_snapshot(debug_dir, "ohouse_browser", i, browser_html)
                        if _looks_like_access_denied(browser_html):
                            debug["reasons"].append("browser_access_denied")
                            continue
                        soup = BeautifulSoup(browser_html, "html.parser")
                    except Exception as exc:
                        debug["reasons"].append(f"browser_fallback_error:{type(exc).__name__}")
                        continue

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
