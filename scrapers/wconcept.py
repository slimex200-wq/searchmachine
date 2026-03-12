from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.browser_utils import PlaywrightTimeoutError, collect_locator_links
from scrapers.scraper_utils import build_signal_row, init_debug_state
from utils.dates import parse_date_range_to_iso
from utils import normalize_link, normalize_space
try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None

MAJOR_HINTS = (
    "w week",
    "double u week",
    "holiday",
    "season",
    "sale",
    "event",
    "promotion",
    "campaign",
    "showcase",
    "focus day",
    "popup",
)
NEGATIVE_HINTS = (
    "24h",
    "72h",
    "48h",
    "coupon",
    "first buy",
    "first purchase",
    "brand day",
    "single brand",
    "flash",
    "첫 구매",
    "time deal",
)


def _hub_urls() -> list[str]:
    return [
        "https://display.wconcept.co.kr/event",
    ]


def _browser_entry_configs() -> list[dict[str, Any]]:
    return [
        {
            "url": "https://display.wconcept.co.kr/rn/women",
            "viewport": {"width": 1920, "height": 969},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            ),
        },
    ]


def _save_snapshot(debug_dir: str, source: str, idx: int, html: str) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{source}_{idx}.html")
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(html)


def _is_allowed_wconcept_link(link: str) -> bool:
    parsed = urlparse(link)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    return host == "event.wconcept.co.kr" and path.startswith("/event/")


def _is_majorish_event(text: str) -> bool:
    lowered = text.lower()
    if any(token in lowered for token in NEGATIVE_HINTS):
        return False
    return any(token in lowered for token in MAJOR_HINTS)


def _extract_candidate(soup: BeautifulSoup, source_url: str, raw_html: str = "") -> dict[str, Any] | None:
    title_node = soup.select_one("h1, .tit, .title, title")
    body_text = normalize_space(soup.get_text(" ", strip=True))
    title = normalize_space(title_node.get_text(" ", strip=True) if title_node else "")
    if not title:
        return None

    event_blob = f"{title} {body_text[:1000]}"
    if not _is_majorish_event(event_blob):
        return None

    start_date, end_date = _extract_hidden_date_window(raw_html, source_url)
    if not start_date or not end_date:
        start_date, end_date = _extract_visible_date_window(event_blob)
    image_url = ""
    for selector in (
        "meta[property='og:image']",
        "meta[name='og:image']",
        "meta[property='twitter:image']",
        "meta[name='twitter:image']",
    ):
        node = soup.select_one(selector)
        if node and normalize_space(node.get("content", "")):
            image_url = normalize_space(node.get("content", ""))
            break
    if not image_url:
        image = soup.select_one("img[src]")
        if image:
            image_url = normalize_link(image.get("src", ""), source_url)

    return build_signal_row(
        title=title,
        link=source_url,
        body_text=body_text,
        platform_hint="WCONCEPT",
        category_hint="fashion",
        start_date=start_date,
        end_date=end_date,
        signal_type="detail",
        confidence_score=0.9,
        image_url=image_url or None,
    )


def _extract_event_links(soup: BeautifulSoup, hub_url: str, limit: int) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for a in soup.select("a[href*='/event/']"):
        link = normalize_link(a.get("href", ""), hub_url)
        if not link or not _is_allowed_wconcept_link(link) or link in seen:
            continue
        title = normalize_space(a.get_text(" ", strip=True))
        if title and any(token in title.lower() for token in NEGATIVE_HINTS):
            continue
        seen.add(link)
        links.append(link)
        if len(links) >= limit:
            break
    return links


def _parse_display_datetime(value: str) -> datetime | None:
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


def _canonical_event_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _extract_hidden_date_window(html: str, source_url: str) -> tuple[str | None, str | None]:
    canonical_url = re.escape(_canonical_event_url(source_url))
    patterns = (
        rf'(?s)(?:landingUrl|webViewUrl|newTargetUrl)":"{canonical_url}[^"]*?".*?"displayStartDate":"([^"]+)".*?"displayEndDate":"([^"]+)"',
        rf'(?s)"displayStartDate":"([^"]+)".*?"displayEndDate":"([^"]+)".*?(?:landingUrl|webViewUrl|newTargetUrl)":"{canonical_url}[^"]*?"',
        rf'(?s)\[\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"{canonical_url}[^"]*?"\s*\]',
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if not match:
            continue
        start = _parse_display_datetime(match.group(1))
        end = _parse_display_datetime(match.group(2))
        if start and end:
            return start.date().isoformat(), end.date().isoformat()
    return _extract_page_schedule_window(html)


def _extract_page_schedule_window(html: str) -> tuple[str | None, str | None]:
    block_match = re.search(r"var\s+dateSchedule\s*=\s*\[(?P<body>.*?)\]\s*;", html, re.DOTALL)
    if not block_match:
        return None, None

    starts: list[datetime] = []
    ends: list[datetime] = []
    for start_raw, end_raw in re.findall(r'\[\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"https://event\.wconcept\.co\.kr/event/\d+', block_match.group("body")):
        start = _parse_display_datetime(start_raw)
        end = _parse_display_datetime(end_raw)
        if start and end:
            starts.append(start)
            ends.append(end)

    if not starts or not ends:
        return None, None
    return min(starts).date().isoformat(), max(ends).date().isoformat()


def _extract_visible_date_window(text: str) -> tuple[str | None, str | None]:
    normalized = normalize_space(text)

    timed_range = re.search(
        r"(?P<a>\d{1,2}/\d{1,2})(?:\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM))?\s*[-~]\s*"
        r"(?P<b>\d{1,2}/\d{1,2})(?:\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM))?",
        normalized,
        re.IGNORECASE,
    )
    if timed_range:
        return parse_date_range_to_iso(f"{timed_range.group('a')} - {timed_range.group('b')}")

    return parse_date_range_to_iso(normalized)


def _extract_timed_event_links_from_html(html: str) -> tuple[set[str], set[str]]:
    active_links: set[str] = set()
    inactive_links: set[str] = set()
    now = datetime.now()
    pattern = re.compile(
        r'"displayStartDate":"([^"]+)".*?"displayEndDate":"([^"]+)".*?"(?:webViewUrl|newTargetUrl)":"(https://event\.wconcept\.co\.kr/event/\d+)',
        re.DOTALL,
    )
    for start_raw, end_raw, link in pattern.findall(html):
        start = _parse_display_datetime(start_raw)
        end = _parse_display_datetime(end_raw)
        if not start or not end:
            continue
        if start <= now <= end:
            active_links.add(link)
        else:
            inactive_links.add(link)
    return active_links, inactive_links


def _extract_event_links_from_html(html: str, limit: int) -> list[str]:
    active_timed_links, inactive_timed_links = _extract_timed_event_links_from_html(html)
    links: list[str] = []
    seen: set[str] = set()

    for link in active_timed_links:
        if link not in seen and _is_allowed_wconcept_link(link):
            seen.add(link)
            links.append(link)
            if len(links) >= limit:
                return links

    for link in re.findall(r"https://event\.wconcept\.co\.kr/event/\d+[^\s\"'\\<]*", html):
        clean_link = link.rstrip("',")
        if clean_link in inactive_timed_links:
            continue
        if clean_link in seen or not _is_allowed_wconcept_link(clean_link):
            continue
        seen.add(clean_link)
        links.append(clean_link)
        if len(links) >= limit:
            break
    return links


def _extract_date_window(text: str) -> tuple[str | None, str | None]:
    return parse_date_range_to_iso(text)


def _click_button_and_collect_target(
    browser: Any,
    entry_url: str,
    config: dict[str, Any],
    selector: str,
    idx: int,
) -> str | None:
    modal_page = browser.new_page(
        viewport=config["viewport"],
        user_agent=config["user_agent"],
    )
    try:
        modal_page.goto(entry_url, wait_until="networkidle", timeout=60000)
        modal_page.wait_for_timeout(3000)
        buttons = modal_page.locator(selector)
        if idx >= buttons.count():
            return None
        buttons.nth(idx).click(timeout=10000)
        modal_page.wait_for_timeout(3000)
        href = modal_page.url
        if href and _is_allowed_wconcept_link(href):
            return href
        return None
    finally:
        modal_page.close()


def _collect_playwright_detail_links(limit: int) -> tuple[list[str], list[str], str]:
    if sync_playwright is None:
        raise RuntimeError("playwright_unavailable")

    detail_links: list[str] = []
    reasons: list[str] = []
    seen: set[str] = set()
    selected_hub_url = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for config in _browser_entry_configs():
                entry_url = str(config["url"])
                selected_hub_url = entry_url
                page = browser.new_page(
                    viewport=config["viewport"],
                    user_agent=config["user_agent"],
                )
                try:
                    page.goto(entry_url, wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(3000)

                    modal_buttons = page.locator("div.modal-wrap.active.type-modal button")
                    if modal_buttons.count():
                        reasons.append(f"playwright_modal_button_detected:{modal_buttons.count()}")
                        for idx in range(min(modal_buttons.count(), limit)):
                            href = _click_button_and_collect_target(
                                browser,
                                entry_url,
                                config,
                                "div.modal-wrap.active.type-modal button",
                                idx,
                            )
                            if href and href not in seen:
                                seen.add(href)
                                detail_links.append(href)
                                reasons.append("playwright_modal_click_navigation")
                                if len(detail_links) >= limit:
                                    break
                    if len(detail_links) >= limit:
                        break

                    nonmodal_buttons = page.locator(
                        "div.modal-wrap.active.type-nonModal .swiper-slide button"
                    )
                    if nonmodal_buttons.count():
                        reasons.append(f"playwright_nonmodal_button_detected:{nonmodal_buttons.count()}")
                        for idx in range(min(nonmodal_buttons.count(), limit)):
                            href = _click_button_and_collect_target(
                                browser,
                                entry_url,
                                config,
                                "div.modal-wrap.active.type-nonModal .swiper-slide button",
                                idx,
                            )
                            if href and href not in seen:
                                seen.add(href)
                                detail_links.append(href)
                                reasons.append("playwright_nonmodal_click_navigation")
                                if len(detail_links) >= limit:
                                    break
                    if len(detail_links) >= limit:
                        break

                    popup_links = page.locator(
                        "div.layer a[href*='event.wconcept.co.kr/event/'], "
                        "[class*='popup'] a[href*='event.wconcept.co.kr/event/'], "
                        "[class*='layer'] a[href*='event.wconcept.co.kr/event/']"
                    )
                    popup_count = popup_links.count()
                    if popup_count:
                        reasons.append(f"playwright_popup_detected:{popup_count}")
                    popup_found, _ = collect_locator_links(
                        page=page,
                        selector=(
                            "div.layer a[href*='event.wconcept.co.kr/event/'], "
                            "[class*='popup'] a[href*='event.wconcept.co.kr/event/'], "
                            "[class*='layer'] a[href*='event.wconcept.co.kr/event/']"
                        ),
                        entry_url=entry_url,
                        limit=limit - len(detail_links),
                        normalize_href=normalize_link,
                        is_allowed=_is_allowed_wconcept_link,
                        seen=seen,
                    )
                    detail_links.extend(popup_found)
                    if len(detail_links) >= limit:
                        break

                    anchor_found, _ = collect_locator_links(
                        page=page,
                        selector="a[href*='event.wconcept.co.kr/event/']",
                        entry_url=entry_url,
                        limit=limit - len(detail_links),
                        normalize_href=normalize_link,
                        is_allowed=_is_allowed_wconcept_link,
                        seen=seen,
                    )
                    detail_links.extend(anchor_found)
                    if detail_links:
                        reasons.append("playwright_visible_link_extract")
                        break
                finally:
                    page.close()
        finally:
            browser.close()

    return detail_links[:limit], reasons, selected_hub_url


def scrape_wconcept(
    timeout_seconds: int = 20,
    limit: int = 12,
    debug_save_html: bool = True,
    debug_dir: str = "scraper_debug",
    enable_browser: bool = False,
) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://event.wconcept.co.kr/"})

    rows: list[dict[str, Any]] = []
    debug = init_debug_state(link_key="event_links_found")

    detail_urls: list[str] = []

    if enable_browser:
        try:
            detail_urls, browser_reasons, browser_hub_url = _collect_playwright_detail_links(limit)
            if detail_urls:
                debug["parser_mode"] = "playwright_popup"
                debug["event_links_found"] = len(detail_urls)
                debug["reasons"].extend(browser_reasons)
                debug["requested_url"].append(browser_hub_url)
                debug["hub_url"] = browser_hub_url
                debug["valid_source_page_count"] = 1
                print("[wconcept] parser_mode=playwright_popup")
                print(f"[wconcept] hub_url={debug['hub_url']}")
                print(f"[wconcept] event_links_found={len(detail_urls)}")
            else:
                debug["reasons"].append("playwright_no_popup_links")
        except (RuntimeError, PlaywrightTimeoutError, Exception) as exc:
            debug["reasons"].append(f"playwright_error:{type(exc).__name__}")

    if not detail_urls:
        for i, url in enumerate(_hub_urls()):
            debug["requested_url"].append(url)
            debug["hub_url"] = url
            try:
                resp = session.get(url, timeout=timeout_seconds)
                html = resp.text or ""
                debug["hub_http_status"] = str(resp.status_code)
                debug["hub_html_length"] = str(len(html))
                debug["http_status"].append(str(resp.status_code))
                debug["html_length"].append(str(len(html)))
                print(f"[wconcept] requested_url={url}")
                print(f"[wconcept] http_status={resp.status_code}")
                print(f"[wconcept] html_length={len(html)}")

                if resp.status_code != 200:
                    debug["reasons"].append(f"http_status_{resp.status_code}")
                    if not debug["failure_reason"]:
                        debug["failure_reason"] = "all_seed_urls_failed"
                    if debug_save_html:
                        _save_snapshot(debug_dir, "wconcept", i, html)
                    continue

                debug["valid_source_page_count"] += 1
                if not html.strip():
                    debug["reasons"].append("empty_html")
                    debug["failure_reason"] = "no_valid_source_page"
                    if debug_save_html:
                        _save_snapshot(debug_dir, "wconcept", i, html)
                    continue

                soup = BeautifulSoup(html, "html.parser")
                parser_mode = "hub_selector"
                debug["parser_mode"] = parser_mode
                print(f"[wconcept] parser_mode={parser_mode}")
                detail_urls = _extract_event_links(soup, url, limit)
                if not detail_urls:
                    detail_urls = _extract_event_links_from_html(html, limit)
                    if detail_urls:
                        debug["reasons"].append("regex_event_link_fallback")
                debug["event_links_found"] = len(detail_urls)
                print(f"[wconcept] hub_url={url}")
                print(f"[wconcept] event_links_found={len(detail_urls)}")
                if not detail_urls and debug_save_html:
                    _save_snapshot(debug_dir, "wconcept_hub", i, html)
                break
            except requests.RequestException as exc:
                debug["http_status"].append("ERR")
                debug["html_length"].append("0")
                debug["reasons"].append(f"request_error:{type(exc).__name__}")
                debug["failure_reason"] = f"request_error:{type(exc).__name__}"
                print(f"[wconcept] failure_reason={debug['failure_reason']}")
                continue

    for i, url in enumerate(detail_urls):
        debug["requested_url"].append(url)
        try:
            resp = session.get(url, timeout=timeout_seconds)
            html = resp.text or ""
            debug["http_status"].append(str(resp.status_code))
            debug["html_length"].append(str(len(html)))
            print(f"[wconcept] requested_url={url}")
            print(f"[wconcept] http_status={resp.status_code}")
            print(f"[wconcept] html_length={len(html)}")

            if resp.status_code != 200:
                debug["reasons"].append(f"detail_http_status_{resp.status_code}")
                if debug_save_html:
                    _save_snapshot(debug_dir, "wconcept_detail", i, html)
                continue

            debug["detail_pages_parsed"] += 1
            if debug["parser_mode"] == "playwright_popup":
                print("[wconcept] parser_mode=playwright_popup")
            else:
                debug["parser_mode"] = "detail_extract"
                print("[wconcept] parser_mode=detail_extract")

            soup = BeautifulSoup(html, "html.parser")
            candidate = _extract_candidate(soup, url, html)
            debug["raw_candidates"] += 1
            if candidate:
                if not candidate.get("start_date") or not candidate.get("end_date"):
                    start_date, end_date = _extract_date_window(candidate.get("content", ""))
                    candidate["start_date"] = candidate.get("start_date") or start_date
                    candidate["end_date"] = candidate.get("end_date") or end_date
                debug["filtered_candidates"] += 1
                rows.append(candidate)
                print("[wconcept] items_extracted=1")
                print(f"[wconcept] extracted_titles={[candidate['title']]}")
            else:
                print("[wconcept] items_extracted=0")
                if debug_save_html:
                    _save_snapshot(debug_dir, "wconcept_detail", i, html)

            if len(rows) >= limit:
                break
        except requests.RequestException as exc:
            debug["http_status"].append("ERR")
            debug["html_length"].append("0")
            debug["reasons"].append(f"detail_request_error:{type(exc).__name__}")
            print(f"[wconcept] failure_reason=detail_request_error:{type(exc).__name__}")
            continue

    if not rows:
        if debug["valid_source_page_count"] == 0 and debug["event_links_found"] == 0:
            debug["failure_reason"] = "all_seed_urls_failed"
        elif debug["event_links_found"] == 0:
            debug["failure_reason"] = "no_valid_source_page"
        elif debug["filtered_candidates"] == 0:
            debug["failure_reason"] = "no_major_event_page"
        elif not debug["failure_reason"]:
            debug["failure_reason"] = "no_event_candidates"
        print(f"[wconcept] failure_reason={debug['failure_reason']}")

    debug["items_extracted"] = len(rows[:limit])
    return {"rows": rows[:limit], "debug": debug}
