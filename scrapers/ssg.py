from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.browser_utils import PlaywrightTimeoutError, collect_playwright_visible_links
from scrapers.scraper_utils import build_signal_row, init_debug_state
from utils import normalize_link, normalize_space, parse_date_range_to_iso

KEYWORDS = (
    "sale",
    "event",
    "promotion",
    "exhibition",
    "benefit",
    "plan",
    "discount",
    "festival",
    "할인",
    "세일",
    "특가",
    "혜택",
    "기획전",
    "행사",
    "프로모션",
    "이벤트",
    "페스타",
    "쿠폰",
)

CATEGORY_HINT = "general"
GENERIC_TITLES = {
    "ssg.com",
    "ssg",
    "event",
    "이벤트",
    "믿고 사는 즐거움",
    "믿고 사는 즐거움 ssg.com",
}
NOISE_TITLE_PATTERNS = (
    "쓱7클럽",
    "티빙",
    "출석체크",
    "초대하기",
    "시식회",
    "라이브",
    "grand open",
)


def _hub_urls() -> list[str]:
    return [
        "https://www.ssg.com/",
        "https://www.ssg.com/event/eventMain.ssg",
        "https://www.ssg.com/event/eventAll.ssg",
    ]


def _browser_entry_configs() -> list[dict[str, Any]]:
    return [
        {
            "url": "https://www.ssg.com/",
            "viewport": {"width": 1440, "height": 1200},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            ),
        },
        {
            "url": "https://www.ssg.com/event/eventMain.ssg",
            "viewport": {"width": 1440, "height": 1200},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            ),
        },
        {
            "url": "https://www.ssg.com/event/eventAll.ssg",
            "viewport": {"width": 1440, "height": 1200},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            ),
        },
    ]


def _save_snapshot(debug_dir: str, source: str, idx: int, html: str) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{source}_{idx}.html")
    with open(path, "w", encoding="utf-8", errors="ignore") as file:
        file.write(html)


def _is_allowed_ssg_link(link: str) -> bool:
    parsed = urlparse(link)
    return parsed.netloc.lower() == "event.ssg.com" and "eventdetail.ssg" in parsed.path.lower()


def _extract_detail_links(soup: BeautifulSoup, hub_url: str, limit: int) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href*='eventDetail.ssg']"):
        link = normalize_link(anchor.get("href", ""), hub_url)
        if not link or link in seen or not _is_allowed_ssg_link(link):
            continue
        seen.add(link)
        links.append(link)
        if len(links) >= limit:
            break
    return links


def _collect_playwright_detail_links(limit: int) -> tuple[list[str], list[str], str]:
    return collect_playwright_visible_links(
        entry_configs=_browser_entry_configs(),
        selector="a[href*='eventDetail.ssg']",
        limit=limit,
        normalize_href=normalize_link,
        is_allowed=_is_allowed_ssg_link,
    )


def _extract_date_window(text: str) -> tuple[str | None, str | None]:
    return parse_date_range_to_iso(text)


def _extract_image_url(soup: BeautifulSoup, source_url: str) -> str | None:
    candidates = [
        "meta[property='og:image']",
        "meta[name='og:image']",
        "meta[name='twitter:image']",
        "meta[property='twitter:image']",
        "img[src]",
    ]
    for selector in candidates:
        node = soup.select_one(selector)
        if not node:
            continue
        value = normalize_space(node.get("content", "") or node.get("src", ""))
        if not value:
            continue
        return normalize_link(value, source_url)
    return None


def _extract_date_window_from_parts(*parts: str) -> tuple[str | None, str | None]:
    for part in parts:
        start_date, end_date = _extract_date_window(part)
        if start_date or end_date:
            return start_date, end_date
    return None, None


def _extract_title_from_html(html: str) -> str:
    patterns = [
        r'Page_title\s*:\s*[\'"]([^\'"\r\n]+)',
        r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)',
        r'<meta\s+name=["\']title["\']\s+content=["\']([^"\']+)',
        r"<title>([^<]+)</title>",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if not match:
            continue
        value = normalize_space(match.group(1))
        value = value.replace("&gt;", ">").replace("&lt;", "<").replace("/title>", "")
        value = normalize_space(value.strip(" '\""))
        if value:
            return value
    return ""


def _extract_breadcrumb_title(text: str) -> str:
    normalized = normalize_space(text)
    patterns = [
        r"이벤트/쿠폰\s*>\s*([^>\n]+?)\s*믿고 사는 즐거움 SSG\.COM",
        r"이벤트/쿠폰\s*>\s*([^>\n]+?)\s*SSG\.COM",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if not match:
            continue
        title = normalize_space(match.group(1))
        if title and not _is_generic_title(title):
            return title
    return ""


def _looks_like_sale_event(text: str) -> bool:
    lowered = text.lower()
    if any(token in lowered for token in KEYWORDS):
        return True
    return bool(re.search(r"\b[1-9]\d?%\b", lowered))


def _is_generic_title(title: str) -> bool:
    lowered = normalize_space(title).lower()
    return lowered in GENERIC_TITLES


def _is_noise_title(title: str, body_text: str) -> bool:
    combined = f"{normalize_space(title)} {normalize_space(body_text[:400])}".lower()
    return any(pattern in combined for pattern in NOISE_TITLE_PATTERNS)


def _extract_home_candidate(soup: BeautifulSoup, source_url: str) -> dict[str, Any] | None:
    body_text = normalize_space(soup.get_text(" ", strip=True))
    if not _looks_like_sale_event(body_text):
        return None
    if not re.search(r"\b(?:1[5-9]|[2-9]\d)%\b", body_text.lower()) and not any(
        token in body_text.lower() for token in ("혜택", "기획전", "행사", "festival")
    ):
        return None

    title = "SSG Home Promotion"
    image_url = _extract_image_url(soup, source_url)
    start_date, end_date = _extract_date_window_from_parts(title, body_text)
    return build_signal_row(
        title=title,
        link=source_url,
        body_text=body_text,
        platform_hint="SSG",
        category_hint=CATEGORY_HINT,
        start_date=start_date,
        end_date=end_date,
        signal_type="homepage",
        confidence_score=0.6,
        image_url=image_url,
    )


def _extract_candidate(soup: BeautifulSoup, detail_url: str, html: str) -> dict[str, Any] | None:
    title_node = soup.select_one("h1, .tit, .title")
    meta_title = soup.select_one("meta[property='og:title'], meta[name='og:title']")
    title_tag = soup.select_one("title")
    img_node = soup.select_one("meta[property='og:image:alt'], img[alt]")
    body_text = normalize_space(soup.get_text(" ", strip=True))

    title = normalize_space(title_node.get_text(" ", strip=True) if title_node else "")
    if not title or _is_generic_title(title):
        title = _extract_breadcrumb_title(body_text)
    if (not title or _is_generic_title(title)) and meta_title:
        title = normalize_space(meta_title.get("content", ""))
    if (not title or _is_generic_title(title)) and title_tag:
        title = normalize_space(title_tag.get_text(" ", strip=True))
    if (not title or _is_generic_title(title)) and img_node:
        title = normalize_space(img_node.get("content", "") or img_node.get("alt", ""))
    if not title or _is_generic_title(title):
        title = _extract_title_from_html(html)
    if not title or _is_generic_title(title):
        title = _extract_breadcrumb_title(body_text)
    if not title:
        return None

    if _is_noise_title(title, body_text):
        return None

    if not _looks_like_sale_event(f"{title} {body_text[:1500]}"):
        return None

    image_url = _extract_image_url(soup, detail_url)
    meta_text = " ".join(
        normalize_space(value)
        for value in (
            meta_title.get("content", "") if meta_title else "",
            title_tag.get_text(" ", strip=True) if title_tag else "",
        )
        if normalize_space(value)
    )
    start_date, end_date = _extract_date_window_from_parts(title, meta_text, body_text)
    return build_signal_row(
        title=title,
        link=detail_url,
        body_text=body_text,
        platform_hint="SSG",
        category_hint=CATEGORY_HINT,
        start_date=start_date,
        end_date=end_date,
        signal_type="detail",
        confidence_score=0.9,
        image_url=image_url,
    )


def scrape_ssg(
    timeout_seconds: int = 20,
    limit: int = 12,
    debug_save_html: bool = True,
    debug_dir: str = "scraper_debug",
    enable_browser: bool = False,
) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.ssg.com/"})

    rows: list[dict[str, Any]] = []
    debug = init_debug_state(link_key="detail_links_found")
    detail_links: list[str] = []

    if enable_browser:
        try:
            detail_links, browser_reasons, browser_hub_url = _collect_playwright_detail_links(limit)
            if detail_links:
                debug["parser_mode"] = "playwright_visible_links"
                debug["detail_links_found"] = len(detail_links)
                debug["reasons"].extend(browser_reasons)
                debug["requested_url"].append(browser_hub_url)
                debug["hub_url"] = browser_hub_url
                debug["valid_source_page_count"] = 1
                print("[ssg] parser_mode=playwright_visible_links")
                print(f"[ssg] hub_url={debug['hub_url']}")
                print(f"[ssg] detail_links_found={len(detail_links)}")
            else:
                debug["reasons"].append("playwright_no_visible_links")
        except (RuntimeError, PlaywrightTimeoutError, Exception) as exc:
            debug["reasons"].append(f"playwright_error:{type(exc).__name__}")

    for idx, url in enumerate(_hub_urls()):
        if detail_links:
            break
        debug["hub_url"] = url
        debug["requested_url"].append(url)
        try:
            response = session.get(url, timeout=timeout_seconds)
            html = response.text or ""
            debug["hub_http_status"] = str(response.status_code)
            debug["hub_html_length"] = str(len(html))
            debug["http_status"].append(str(response.status_code))
            debug["html_length"].append(str(len(html)))
            print(f"[ssg] hub_url={url}")
            print(f"[ssg] hub_http_status={response.status_code}")
            print(f"[ssg] hub_html_length={len(html)}")

            if response.status_code != 200:
                debug["reasons"].append(f"http_status_{response.status_code}")
                if debug_save_html:
                    _save_snapshot(debug_dir, "ssg_hub", idx, html)
                continue

            debug["valid_source_page_count"] += 1
            if not html.strip():
                debug["failure_reason"] = "no_valid_source_page"
                continue

            soup = BeautifulSoup(html, "html.parser")
            if url == "https://www.ssg.com/":
                candidate = _extract_home_candidate(soup, url)
                if candidate:
                    rows.append(candidate)
                    debug["raw_candidates"] += 1
                    debug["filtered_candidates"] += 1
                    debug["items_extracted"] = len(rows)
                    debug["parser_mode"] = "home_direct_extract"
                    print("[ssg] parser_mode=home_direct_extract")
                    print("[ssg] items_extracted=1")
                    break

            detail_links = _extract_detail_links(soup, url, limit)
            debug["detail_links_found"] = len(detail_links)
            print(f"[ssg] detail_links_found={len(detail_links)}")
            if not detail_links and debug_save_html:
                _save_snapshot(debug_dir, "ssg_hub", idx, html)
            break
        except requests.RequestException as exc:
            debug["reasons"].append(f"request_error:{type(exc).__name__}")
            debug["failure_reason"] = f"request_error:{type(exc).__name__}"

    for idx, url in enumerate(detail_links):
        debug["requested_url"].append(url)
        try:
            response = session.get(url, timeout=timeout_seconds)
            html = response.text or ""
            debug["http_status"].append(str(response.status_code))
            debug["html_length"].append(str(len(html)))
            print(f"[ssg] requested_url={url}")
            print(f"[ssg] http_status={response.status_code}")
            print(f"[ssg] html_length={len(html)}")

            if response.status_code != 200:
                debug["reasons"].append(f"detail_http_status_{response.status_code}")
                continue

            debug["detail_pages_parsed"] += 1
            if debug["parser_mode"] == "playwright_visible_links":
                print("[ssg] parser_mode=playwright_visible_links")
            else:
                debug["parser_mode"] = "detail_extract"
                print("[ssg] parser_mode=detail_extract")

            candidate = _extract_candidate(BeautifulSoup(html, "html.parser"), url, html)
            debug["raw_candidates"] += 1
            if candidate:
                rows.append(candidate)
                debug["filtered_candidates"] += 1
                print("[ssg] items_extracted=1")
            else:
                print("[ssg] items_extracted=0")
                if debug_save_html:
                    _save_snapshot(debug_dir, "ssg_detail", idx, html)

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
        print(f"[ssg] failure_reason={debug['failure_reason']}")

    debug["items_extracted"] = len(rows[:limit])
    return {"rows": rows[:limit], "debug": debug}
