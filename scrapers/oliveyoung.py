from __future__ import annotations

import os
import re
from datetime import date
from typing import Any

import requests
from bs4 import BeautifulSoup

from scrapers.browser_utils import collect_playwright_visible_links, fetch_playwright_page_html
from scrapers.scraper_utils import build_signal_row, init_debug_state
from utils import normalize_link, normalize_space

KEYWORDS = (
    "세일",
    "할인",
    "특가",
    "기획전",
    "프로모션",
    "promotion",
    "special",
    "올영세일",
    "페스타",
    "브랜드",
)

HUB_URLS = [
    "https://www.oliveyoung.co.kr/store/main/getStoreMain.do",
    "https://m.oliveyoung.co.kr/m/main/getMMain.do",
    "https://www.oliveyoung.co.kr/store/event/getEventList.do",
    "https://www.oliveyoung.co.kr/store/planshop/getPlanShopList.do",
    "https://m.oliveyoung.co.kr/m/event/getEventList.do",
    "https://m.oliveyoung.co.kr/m/planshop/getPlanShopList.do",
]

BROWSER_ENTRY_CONFIGS = [
    {
        "url": "https://www.oliveyoung.co.kr/store/main/getStoreMain.do",
        "viewport": {"width": 1440, "height": 2200},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    },
    {
        "url": "https://www.oliveyoung.co.kr/store/event/getEventList.do",
        "viewport": {"width": 1440, "height": 2200},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    },
    {
        "url": "https://m.oliveyoung.co.kr/m/main/getMMain.do",
        "viewport": {"width": 430, "height": 2200},
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    },
    {
        "url": "https://m.oliveyoung.co.kr/m/event/getEventList.do",
        "viewport": {"width": 430, "height": 2200},
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    },
]

DETAIL_BROWSER_CONFIG = {
    "viewport": {"width": 1440, "height": 2200},
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _save_snapshot(debug_dir: str, source: str, idx: int, html: str) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{source}_{idx}.html")
    with open(path, "w", encoding="utf-8", errors="ignore") as file:
        file.write(html)


def _is_allowed_oliveyoung_link(link: str) -> bool:
    lowered = link.lower()
    if "oliveyoung.co.kr" not in lowered:
        return False
    return any(
        token in lowered
        for token in (
            "geteventdetail.do",
            "getplanshopdetail.do",
            "/event/",
            "/planshop/",
        )
    )


def _clean_title(raw_title: str) -> str:
    title = normalize_space(raw_title)
    title = re.sub(r"\s*\|\s*w?올리브영.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\|\s*olive\s*young.*$", "", title, flags=re.IGNORECASE)
    return normalize_space(title)


def _extract_detail_links(soup: BeautifulSoup, hub_url: str, limit: int) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()

    selectors = (
        "a[href*='getEventDetail.do']",
        "a[href*='getPlanShopDetail.do']",
        "a[href*='/event/']",
        "a[href*='/planshop/']",
    )
    for selector in selectors:
        for anchor in soup.select(selector):
            href = anchor.get("href", "")
            link = normalize_link(href, hub_url)
            if not link or link in seen or not _is_allowed_oliveyoung_link(link):
                continue
            seen.add(link)
            links.append(link)
            if len(links) >= limit:
                return links
    return links


def _extract_detail_links_from_html(html: str, hub_url: str, limit: int) -> list[str]:
    return _extract_detail_links(BeautifulSoup(html, "html.parser"), hub_url, limit)


def _looks_like_oliveyoung_error_page(html: str) -> bool:
    lowered = html.lower()
    return any(
        marker in lowered
        for marker in (
            'class="error-page"',
            'class="error-wrap"',
            "common.link.movemainhome",
            "location.href='/'",
        )
    )


def _extract_date_window(text: str) -> tuple[str | None, str | None]:
    year_pattern = re.search(
        r"(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})\s*[~\-]\s*(?:(20\d{2})[.\-/]\s*)?(\d{1,2})[.\-/]\s*(\d{1,2})",
        text,
    )
    if year_pattern:
        start_year, start_month, start_day, end_year, end_month, end_day = year_pattern.groups()
        end_year = end_year or start_year
        return (
            f"{int(start_year):04d}-{int(start_month):02d}-{int(start_day):02d}",
            f"{int(end_year):04d}-{int(end_month):02d}-{int(end_day):02d}",
        )
    short_pattern = re.search(r"(\d{1,2})[.\-/]\s*(\d{1,2})\s*[~\-]\s*(\d{1,2})[.\-/]\s*(\d{1,2})", text)
    if short_pattern:
        start_month, start_day, end_month, end_day = short_pattern.groups()
        current_year = date.today().year
        end_year = current_year + 1 if int(end_month) < int(start_month) else current_year
        return (
            f"{current_year:04d}-{int(start_month):02d}-{int(start_day):02d}",
            f"{end_year:04d}-{int(end_month):02d}-{int(end_day):02d}",
        )
    return None, None


def _pick_meta_content(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        tag = soup.select_one(f'meta[property="{key}"], meta[name="{key}"]')
        if tag and tag.get("content"):
            return normalize_space(tag.get("content", ""))
    return ""


def _extract_candidate(soup: BeautifulSoup, detail_url: str) -> dict[str, Any] | None:
    meta_title = _pick_meta_content(soup, "og:title", "twitter:title")
    title_node = soup.select_one("h1, .tit, .title, .evt_tit, .pr_title, title")
    raw_title = meta_title or (title_node.get_text(" ", strip=True) if title_node else "")
    title = _clean_title(raw_title)

    body_text = normalize_space(soup.get_text(" ", strip=True))
    combined = normalize_space(f"{title} {body_text[:1200]}").lower()
    if not title or not any(keyword.lower() in combined for keyword in KEYWORDS):
        return None

    start_date, end_date = _extract_date_window(body_text)
    image_url = _pick_meta_content(soup, "og:image", "twitter:image") or None

    return build_signal_row(
        title=title,
        link=detail_url,
        body_text=body_text,
        platform_hint="올리브영",
        category_hint="beauty",
        start_date=start_date,
        end_date=end_date,
        signal_type="detail",
        confidence_score=0.9 if start_date and end_date else 0.82,
        image_url=image_url,
    )


def scrape_oliveyoung(
    timeout_seconds: int = 20,
    limit: int = 12,
    debug_save_html: bool = True,
    debug_dir: str = "scraper_debug",
    enable_browser: bool = False,
) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.oliveyoung.co.kr/",
        }
    )

    rows: list[dict[str, Any]] = []
    detail_links: list[str] = []
    debug = init_debug_state(link_key="detail_links_found")

    for index, hub_url in enumerate(HUB_URLS):
        debug["hub_url"] = hub_url
        debug["requested_url"].append(hub_url)
        try:
            response = session.get(hub_url, timeout=timeout_seconds)
            html = response.text or ""
            debug["http_status"].append(str(response.status_code))
            debug["html_length"].append(str(len(html)))
            if not debug["hub_http_status"]:
                debug["hub_http_status"] = str(response.status_code)
            if not debug["hub_html_length"]:
                debug["hub_html_length"] = str(len(html))

            print(f"[oliveyoung] hub_url={hub_url}")
            print(f"[oliveyoung] hub_http_status={response.status_code}")
            print(f"[oliveyoung] hub_html_length={len(html)}")

            if response.status_code != 200:
                debug["reasons"].append(f"http_status_{response.status_code}")
                if debug_save_html:
                    _save_snapshot(debug_dir, "oliveyoung_hub", index, html)
                continue

            debug["valid_source_page_count"] += 1
            if not html.strip():
                debug["reasons"].append("empty_html")
                continue
            if _looks_like_oliveyoung_error_page(html):
                debug["reasons"].append("oliveyoung_error_page")
                if debug_save_html:
                    _save_snapshot(debug_dir, "oliveyoung_hub", index, html)
                continue

            soup = BeautifulSoup(html, "html.parser")
            extracted_links = _extract_detail_links(soup, hub_url, limit)
            debug["detail_links_found"] = max(debug["detail_links_found"], len(extracted_links))
            print(f"[oliveyoung] detail_links_found={len(extracted_links)}")

            if extracted_links:
                detail_links = extracted_links
                debug["parser_mode"] = "hub_selector"
                break

            fallback_anchors = soup.select("a[href]")
            debug["fallback_candidates"] += len(fallback_anchors)
            debug["reasons"].append("selector_zero")
            print(f"[oliveyoung] fallback_candidates={len(fallback_anchors)}")

            fallback_links = _extract_detail_links(BeautifulSoup(str(fallback_anchors), "html.parser"), hub_url, limit)
            debug["detail_links_found"] = max(debug["detail_links_found"], len(fallback_links))
            if fallback_links:
                detail_links = fallback_links
                debug["parser_mode"] = "fallback_selector"
                break

            if debug_save_html:
                _save_snapshot(debug_dir, "oliveyoung_hub", index, html)
        except requests.RequestException as exc:
            debug["http_status"].append("ERR")
            debug["html_length"].append("0")
            debug["reasons"].append(f"request_error:{type(exc).__name__}")

    if not detail_links and enable_browser:
        try:
            browser_links, reasons, selected_hub_url = collect_playwright_visible_links(
                entry_configs=BROWSER_ENTRY_CONFIGS,
                selector="a[href*='getEventDetail.do'], a[href*='getPlanShopDetail.do'], a[href*='/event/'], a[href*='/planshop/']",
                limit=limit,
                normalize_href=normalize_link,
                is_allowed=_is_allowed_oliveyoung_link,
            )
            debug["reasons"].extend(reasons)
            if selected_hub_url:
                debug["hub_url"] = selected_hub_url
            if browser_links:
                detail_links = browser_links
                debug["detail_links_found"] = len(browser_links)
                debug["parser_mode"] = "playwright_visible_links"
        except Exception as exc:  # pragma: no cover
            debug["reasons"].append(f"playwright_error:{type(exc).__name__}")

    if not detail_links and enable_browser:
        for index, config in enumerate(BROWSER_ENTRY_CONFIGS):
            entry_url = str(config["url"])
            try:
                html, browser_reasons = fetch_playwright_page_html(
                    url=entry_url,
                    viewport=config["viewport"],
                    user_agent=config["user_agent"],
                )
                debug["reasons"].extend(browser_reasons)
                debug["requested_url"].append(entry_url)
                if _looks_like_oliveyoung_error_page(html):
                    debug["reasons"].append("oliveyoung_browser_error_page")
                    if debug_save_html:
                        _save_snapshot(debug_dir, "oliveyoung_browser_hub", index, html)
                    continue
                browser_links = _extract_detail_links_from_html(html, entry_url, limit)
                debug["detail_links_found"] = max(debug["detail_links_found"], len(browser_links))
                if browser_links:
                    detail_links = browser_links
                    debug["hub_url"] = entry_url
                    debug["parser_mode"] = "playwright_html_hub_extract"
                    break
                if debug_save_html:
                    _save_snapshot(debug_dir, "oliveyoung_browser_hub", index, html)
            except Exception as exc:  # pragma: no cover
                debug["reasons"].append(f"playwright_html_hub_error:{type(exc).__name__}")

    for index, detail_url in enumerate(detail_links[:limit]):
        debug["requested_url"].append(detail_url)
        try:
            response = session.get(detail_url, timeout=timeout_seconds)
            html = response.text or ""
            debug["http_status"].append(str(response.status_code))
            debug["html_length"].append(str(len(html)))

            print(f"[oliveyoung] requested_url={detail_url}")
            print(f"[oliveyoung] http_status={response.status_code}")
            print(f"[oliveyoung] html_length={len(html)}")

            if response.status_code != 200:
                debug["reasons"].append(f"detail_http_status_{response.status_code}")
                if not enable_browser:
                    continue
                try:
                    html, browser_reasons = fetch_playwright_page_html(
                        url=detail_url,
                        viewport=DETAIL_BROWSER_CONFIG["viewport"],
                        user_agent=DETAIL_BROWSER_CONFIG["user_agent"],
                    )
                    debug["reasons"].extend(browser_reasons)
                    debug["parser_mode"] = "detail_extract_browser"
                    print("[oliveyoung] parser_mode=detail_extract_browser")
                    print(f"[oliveyoung] browser_html_length={len(html)}")
                    if not html.strip():
                        continue
                    if _looks_like_oliveyoung_error_page(html):
                        debug["reasons"].append("oliveyoung_browser_detail_error_page")
                        continue
                except Exception as exc:  # pragma: no cover
                    debug["reasons"].append(f"detail_playwright_error:{type(exc).__name__}")
                    continue

            debug["detail_pages_parsed"] += 1
            debug["raw_candidates"] += 1
            if _looks_like_oliveyoung_error_page(html):
                debug["reasons"].append("oliveyoung_detail_error_page")
                continue
            if debug["parser_mode"] != "detail_extract_browser":
                debug["parser_mode"] = "detail_extract"
                print("[oliveyoung] parser_mode=detail_extract")

            candidate = _extract_candidate(BeautifulSoup(html, "html.parser"), detail_url)
            if candidate:
                rows.append(candidate)
                debug["filtered_candidates"] += 1
                print("[oliveyoung] items_extracted=1")
            else:
                print("[oliveyoung] items_extracted=0")
                if debug_save_html:
                    _save_snapshot(debug_dir, "oliveyoung_detail", index, html)

            if len(rows) >= limit:
                break
        except requests.RequestException as exc:
            debug["reasons"].append(f"detail_request_error:{type(exc).__name__}")

    if not rows:
        if debug["valid_source_page_count"] == 0 and debug["detail_links_found"] == 0:
            debug["failure_reason"] = "all_seed_urls_failed"
        elif debug["detail_links_found"] == 0:
            debug["failure_reason"] = "no_valid_source_page"
        else:
            debug["failure_reason"] = "filtered_all"
        print(f"[oliveyoung] failure_reason={debug['failure_reason']}")

    debug["items_extracted"] = len(rows[:limit])
    return {"rows": rows[:limit], "debug": debug}
