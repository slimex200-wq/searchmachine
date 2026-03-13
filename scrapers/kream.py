from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.browser_utils import fetch_cloudflare_rendered_html, fetch_playwright_page_html
from utils import normalize_link, normalize_space

KEYWORDS = (
    "kream week",
    "sale",
    "event",
    "promotion",
    "campaign",
    "benefit",
    "discount",
    "세일",
    "이벤트",
    "기획전",
    "혜택",
    "할인",
    "리셀",
    "한정판",
    "스니커즈",
)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
VIEWPORT = {"width": 1440, "height": 900}


def _seed_urls() -> list[str]:
    return [
        "https://kream.co.kr/",
        "https://kream.co.kr/exhibitions",
        "https://kream.co.kr/search?keyword=크림",
        "https://kream.co.kr/search?keyword=스니커즈",
    ]


def _save_snapshot(debug_dir: str, source: str, idx: int, html: str) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{source}_{idx}.html")
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(html)


def _is_allowed_kream_link(link: str) -> bool:
    parsed = urlparse(link)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if not host.endswith("kream.co.kr"):
        return False
    return any(token in path for token in ("/exhibitions", "/event", "/campaign", "/search"))


def _contains_keyword(*parts: str) -> bool:
    text = " ".join(part for part in parts if part).lower()
    return any(keyword in text for keyword in KEYWORDS)


def _extract_date_text(text: str) -> str:
    normalized = normalize_space(text)
    match = re.search(
        r"\d{4}-\d{2}-\d{2}|\d{4}\.\d{2}\.\d{2}|\d{1,2}/\d{1,2}|\d{1,2}\.\d{1,2}",
        normalized,
    )
    return match.group(0) if match else normalized


def _looks_like_kream_error_page(html: str) -> bool:
    lowered = html.lower()
    return any(
        marker in lowered
        for marker in (
            "<title>500",
            "internal server error",
            "something went wrong",
            "error occurred",
        )
    )


def _build_seed_row(soup: BeautifulSoup, source_url: str) -> dict[str, Any] | None:
    title = normalize_space((soup.find("meta", attrs={"property": "og:title"}) or {}).get("content", ""))
    if not title:
        title = normalize_space(soup.title.get_text(" ", strip=True) if soup.title else "")

    description = normalize_space(
        (
            soup.find("meta", attrs={"name": "description"})
            or soup.find("meta", attrs={"property": "og:description"})
            or {}
        ).get("content", "")
    )
    heading = normalize_space(" ".join(node.get_text(" ", strip=True) for node in soup.select("h1, h2")[:3]))
    context = normalize_space(" ".join(part for part in (title, heading, description) if part))

    if not title or not _contains_keyword(title, context):
        return None

    return {
        "title": title,
        "link": source_url,
        "context": context,
        "content": context,
        "date_text": _extract_date_text(context),
        "platform_hint": "KREAM",
        "category_hint": "fashion",
        "source_url": source_url,
    }


def _extract_rows(candidates: list[Any], source_url: str, limit: int) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    pre_filter_count = len(candidates)

    for anchor in candidates:
        title = normalize_space(anchor.get_text(" ", strip=True))
        context = normalize_space(anchor.parent.get_text(" ", strip=True) if anchor.parent else title)
        if not title or not _contains_keyword(title, context):
            continue

        link = normalize_link(anchor.get("href", ""), source_url)
        if not link or link in seen or not _is_allowed_kream_link(link):
            continue
        seen.add(link)

        rows.append(
            {
                "title": title,
                "link": link,
                "context": context,
                "content": context,
                "date_text": _extract_date_text(context),
                "platform_hint": "KREAM",
                "category_hint": "fashion",
                "source_url": source_url,
            }
        )
        if len(rows) >= limit:
            break

    return rows, pre_filter_count


def scrape_kream(
    timeout_seconds: int = 20,
    limit: int = 12,
    debug_save_html: bool = True,
    debug_dir: str = "scraper_debug",
) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Referer": "https://kream.co.kr/",
        }
    )

    rows: list[dict[str, Any]] = []
    seen_seed_titles: set[str] = set()
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
            print(f"[kream] requested_url={url}")
            print(f"[kream] http_status={resp.status_code}")
            print(f"[kream] html_length={len(html)}")

            if resp.status_code != 200 or not html.strip():
                if resp.status_code != 200:
                    debug["reasons"].append(f"http_status_{resp.status_code}")
                if not html.strip():
                    debug["reasons"].append("empty_html")
                try:
                    browser_html, browser_reasons = fetch_playwright_page_html(
                        url=url,
                        viewport=VIEWPORT,
                        user_agent=USER_AGENT,
                        timeout_ms=timeout_seconds * 1000,
                    )
                except Exception as exc:
                    browser_html = ""
                    browser_reasons = [f"browser_fallback_error:{type(exc).__name__}"]
                debug["reasons"].extend(browser_reasons)
                if browser_html.strip() and not _looks_like_kream_error_page(browser_html):
                    html = browser_html
                    debug["reasons"].append("browser_seed_fallback")
                    print(f"[kream] browser_html_length={len(html)}")
                else:
                    if browser_html.strip():
                        debug["reasons"].append("kream_browser_error_page")
                    cloudflare_html, cloudflare_reasons = fetch_cloudflare_rendered_html(
                        url=url,
                        user_agent=USER_AGENT,
                        timeout_seconds=timeout_seconds,
                    )
                    debug["reasons"].extend(cloudflare_reasons)
                    if cloudflare_html.strip() and not _looks_like_kream_error_page(cloudflare_html):
                        html = cloudflare_html
                        debug["reasons"].append("cloudflare_seed_fallback")
                        print(f"[kream] cloudflare_html_length={len(html)}")
                    else:
                        if cloudflare_html.strip():
                            debug["reasons"].append("kream_cloudflare_error_page")
                        if debug["valid_source_page_count"] == 0 and not debug["failure_reason"]:
                            debug["failure_reason"] = "all_seed_urls_failed"
                        if debug_save_html:
                            _save_snapshot(debug_dir, "kream", i, cloudflare_html or browser_html or html)
                        continue

            debug["valid_source_page_count"] += 1
            if debug["failure_reason"] == "all_seed_urls_failed":
                debug["failure_reason"] = ""

            soup = BeautifulSoup(html, "html.parser")
            seed_row = _build_seed_row(soup, url)
            seed_title_key = normalize_space(seed_row["title"]).lower() if seed_row else ""
            if seed_row and seed_title_key not in seen_seed_titles and len(rows) < limit:
                seen_seed_titles.add(seed_title_key)
                rows.append(seed_row)
                debug["filtered_candidates"] += 1
                print(f"[kream] seed_candidate={seed_row['title']}")

            selected = soup.select("a[href*='exhibitions'], a[href*='event'], a[href*='campaign'], a[href*='search']")
            if not selected:
                debug["reasons"].append("selector_zero")
                fallback_selected = soup.select("a[href]")
                debug["fallback_candidates"] += len(fallback_selected)
                selected = fallback_selected

            extracted, pre_filter_count = _extract_rows(selected, url, max(0, limit - len(rows)))
            debug["raw_candidates"] += pre_filter_count
            debug["filtered_candidates"] += len(extracted)
            rows.extend(extracted)
            debug["items_extracted"] = len(rows)
            print(f"[kream] raw_candidates={debug['raw_candidates']}")
            print(f"[kream] filtered_candidates={debug['filtered_candidates']}")

            if not extracted and debug_save_html:
                _save_snapshot(debug_dir, "kream", i, html)

            if len(rows) >= limit:
                break
        except requests.RequestException as exc:
            debug["http_status"].append("ERR")
            debug["html_length"].append("0")
            debug["reasons"].append(f"request_error:{type(exc).__name__}")
            debug["failure_reason"] = f"request_error:{type(exc).__name__}"
            print(f"[kream] failure_reason={debug['failure_reason']}")
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
        print(f"[kream] failure_reason={debug['failure_reason']}")

    debug["items_extracted"] = len(rows[:limit])
    return {"rows": rows[:limit], "debug": debug}
