from __future__ import annotations

import os
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from utils import normalize_link, normalize_space

KEYWORDS = ("sale", "event", "promotion", "plan", "special")


def _hub_urls() -> list[str]:
    return [
        "https://m.oliveyoung.co.kr/m/event/getEventList.do",
        "https://www.oliveyoung.co.kr/store/event/getEventList.do",
    ]


def _save_snapshot(debug_dir: str, source: str, idx: int, html: str) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{source}_{idx}.html")
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(html)


def _is_allowed_oliveyoung_link(link: str) -> bool:
    lowered = link.lower()
    return "oliveyoung.co.kr" in lowered and ("event" in lowered or "plan" in lowered)


def _extract_detail_links(soup: BeautifulSoup, hub_url: str, limit: int) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for a in soup.select("a[href*='event'], a[href*='plan']"):
        link = normalize_link(a.get("href", ""), hub_url)
        if not link or link in seen or not _is_allowed_oliveyoung_link(link):
            continue
        seen.add(link)
        links.append(link)
        if len(links) >= limit:
            break
    return links


def _extract_date_window(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"(20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2})\s*[~\-]\s*(20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2})", text)
    if not match:
        return None, None
    return tuple(x.replace(".", "-").replace("/", "-") for x in match.groups())  # type: ignore[return-value]


def _extract_candidate(soup: BeautifulSoup, detail_url: str) -> dict[str, Any] | None:
    title_node = soup.select_one("h1, .tit, .title, title")
    body_text = normalize_space(soup.get_text(" ", strip=True))
    title = normalize_space(title_node.get_text(" ", strip=True) if title_node else "")
    if not title:
        return None
    blob = f"{title} {body_text[:1000]}".lower()
    if not any(token in blob for token in KEYWORDS):
        return None
    start_date, end_date = _extract_date_window(body_text)
    return {
        "title": title,
        "link": detail_url,
        "start_date": start_date,
        "end_date": end_date,
        "context": body_text[:500],
        "content": body_text[:1000],
        "date_text": body_text[:300],
        "platform_hint": "올리브영",
        "category_hint": "뷰티",
        "source_url": detail_url,
    }


def scrape_oliveyoung(
    timeout_seconds: int = 20,
    limit: int = 12,
    debug_save_html: bool = True,
    debug_dir: str = "scraper_debug",
) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36",
            "Referer": "https://www.oliveyoung.co.kr/",
        }
    )

    rows: list[dict[str, Any]] = []
    debug = {
        "hub_url": "",
        "requested_url": [],
        "hub_http_status": "",
        "http_status": [],
        "hub_html_length": "",
        "html_length": [],
        "valid_source_page_count": 0,
        "detail_links_found": 0,
        "detail_pages_parsed": 0,
        "raw_candidates": 0,
        "fallback_candidates": 0,
        "filtered_candidates": 0,
        "items_extracted": 0,
        "parser_mode": "hub_selector",
        "failure_reason": "",
        "reasons": [],
    }

    detail_links: list[str] = []
    for i, url in enumerate(_hub_urls()):
        debug["hub_url"] = url
        debug["requested_url"].append(url)
        try:
            resp = session.get(url, timeout=timeout_seconds)
            html = resp.text or ""
            debug["hub_http_status"] = str(resp.status_code)
            debug["hub_html_length"] = str(len(html))
            debug["http_status"].append(str(resp.status_code))
            debug["html_length"].append(str(len(html)))
            print(f"[oliveyoung] hub_url={url}")
            print(f"[oliveyoung] hub_http_status={resp.status_code}")
            print(f"[oliveyoung] hub_html_length={len(html)}")
            if resp.status_code != 200:
                debug["reasons"].append(f"http_status_{resp.status_code}")
                if debug_save_html:
                    _save_snapshot(debug_dir, "oliveyoung_hub", i, html)
                continue
            debug["valid_source_page_count"] += 1
            if not html.strip():
                debug["failure_reason"] = "no_valid_source_page"
                continue
            soup = BeautifulSoup(html, "html.parser")
            detail_links = _extract_detail_links(soup, url, limit)
            debug["detail_links_found"] = len(detail_links)
            print(f"[oliveyoung] detail_links_found={len(detail_links)}")
            if not detail_links and debug_save_html:
                _save_snapshot(debug_dir, "oliveyoung_hub", i, html)
            break
        except requests.RequestException as exc:
            debug["reasons"].append(f"request_error:{type(exc).__name__}")
            debug["failure_reason"] = f"request_error:{type(exc).__name__}"

    for i, url in enumerate(detail_links):
        debug["requested_url"].append(url)
        try:
            resp = session.get(url, timeout=timeout_seconds)
            html = resp.text or ""
            debug["http_status"].append(str(resp.status_code))
            debug["html_length"].append(str(len(html)))
            print(f"[oliveyoung] requested_url={url}")
            print(f"[oliveyoung] http_status={resp.status_code}")
            print(f"[oliveyoung] html_length={len(html)}")
            if resp.status_code != 200:
                debug["reasons"].append(f"detail_http_status_{resp.status_code}")
                continue
            debug["detail_pages_parsed"] += 1
            debug["parser_mode"] = "detail_extract"
            print("[oliveyoung] parser_mode=detail_extract")
            candidate = _extract_candidate(BeautifulSoup(html, "html.parser"), url)
            debug["raw_candidates"] += 1
            if candidate:
                rows.append(candidate)
                debug["filtered_candidates"] += 1
                print("[oliveyoung] items_extracted=1")
            else:
                print("[oliveyoung] items_extracted=0")
                if debug_save_html:
                    _save_snapshot(debug_dir, "oliveyoung_detail", i, html)
            if len(rows) >= limit:
                break
        except requests.RequestException as exc:
            debug["reasons"].append(f"detail_request_error:{type(exc).__name__}")

    if not rows:
        if debug["valid_source_page_count"] == 0:
            debug["failure_reason"] = "all_seed_urls_failed"
        elif debug["detail_links_found"] == 0:
            debug["failure_reason"] = "no_valid_source_page"
        else:
            debug["failure_reason"] = "filtered_all"
        print(f"[oliveyoung] failure_reason={debug['failure_reason']}")

    debug["items_extracted"] = len(rows[:limit])
    return {"rows": rows[:limit], "debug": debug}
