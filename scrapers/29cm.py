from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.browser_utils import PlaywrightTimeoutError, collect_playwright_visible_links
from scrapers.scraper_utils import build_signal_row, init_debug_state
from utils import normalize_link, normalize_space, parse_date_range_to_iso
from utils.dates import _safe_parse_one

KEYWORDS = (
    "sale",
    "event",
    "promotion",
    "showcase",
    "exhibition",
    "special order",
    "discount",
    "benefit",
    "festival",
    "할인",
    "세일",
    "이벤트",
    "특가",
    "프로모션",
    "기획전",
)

GENERIC_TITLES = {
    "29cm",
    "감도 깊은 취향 셀렉트샵 29cm",
    "special order",
    "showcase",
    "event",
}

TITLE_SUFFIX_PATTERNS = (
    r"\s*-\s*감도 깊은 취향 셀렉트샵\s*29CM\s*$",
    r"\s*\|\s*29CM\s*$",
)

INLINE_DATE_PATTERNS = (
    r"\b\d{2}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*(?:~|-)\s*\d{1,2}\.\s*\d{1,2}\.?\b",
    r"\b20\d{2}[./-]\d{1,2}[./-]\d{1,2}\s*(?:~|-)\s*20?\d{0,2}[./-]?\d{1,2}[./-]\d{1,2}\b",
)

NEXT_LINK_KEYS = {
    "url",
    "href",
    "link",
    "linkvalue",
    "landingurl",
    "targeturl",
    "path",
    "deeplink",
}


def _hub_urls() -> list[str]:
    return [
        "https://www.29cm.co.kr/",
        "https://www.29cm.co.kr/event",
        "https://www.29cm.co.kr/store/showcase",
        "https://www.29cm.co.kr/store/exhibition",
    ]


def _browser_entry_configs() -> list[dict[str, Any]]:
    return [
        {
            "url": "https://www.29cm.co.kr/",
            "viewport": {"width": 1440, "height": 1200},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            ),
        },
        {
            "url": "https://www.29cm.co.kr/event",
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


def _decode_response_text(response: requests.Response) -> str:
    text = getattr(response, "text", "")
    content = getattr(response, "content", b"")
    if not isinstance(content, (bytes, bytearray)):
        return text or ""
    if not content:
        return text or ""
    for encoding in ("utf-8", response.encoding, getattr(response, "apparent_encoding", None)):
        if not encoding:
            continue
        try:
            return content.decode(encoding, errors="ignore")
        except (LookupError, UnicodeDecodeError):
            continue
    return text or ""


def _is_generic_29cm_title(title: str) -> bool:
    cleaned = normalize_space(title).lower()
    if not cleaned:
        return True
    return (
        cleaned in GENERIC_TITLES
        or cleaned == "focus"
        or cleaned == "감도 깊은 취향 셀렉트샵 29cm"
        or cleaned.startswith("감도 깊은 취향 셀렉트샵 29cm")
        or cleaned.startswith("감도 깊은 취향 셀렉트샵 29cm")
    )


def _is_generic_29cm_link(link: str) -> bool:
    parsed = urlparse(link)
    path = parsed.path.rstrip("/").lower()
    return path in {
        "",
        "/event",
        "/store/showcase",
        "/store/exhibition",
        "/store/special-order",
        "/content/promotion/benefit-guide",
    }


def _is_generic_29cm_title(title: str) -> bool:
    cleaned = normalize_space(title).lower()
    if not cleaned:
        return True
    return (
        cleaned in GENERIC_TITLES
        or cleaned == "focus"
        or cleaned.startswith("감도 깊은 취향 셀렉트샵 29cm")
    )


def _is_allowed_29cm_link(link: str) -> bool:
    parsed = urlparse(link)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host != "www.29cm.co.kr":
        return False
    if _is_generic_29cm_link(link):
        return False
    if "/catalog/" in path or "/product/" in path or "/products/" in path:
        return False
    return path.startswith(
        (
            "/store/event/",
            "/store/showcase/",
            "/store/exhibition/",
            "/store/special-order/",
            "/content/brand-news/",
            "/content/brand-event/",
            "/content/campaign/",
            "/content/29-limited-order/",
            "/content/collection/",
            "/content/promotion/",
            "/event/",
        )
    )


def _collect_playwright_detail_links(limit: int) -> tuple[list[str], list[str], str]:
    return collect_playwright_visible_links(
        entry_configs=_browser_entry_configs(),
        selector=(
            "a[href*='/store/event/'], "
            "a[href*='/store/showcase/'], "
            "a[href*='/store/exhibition/'], "
            "a[href*='/content/brand-news/'], "
            "a[href*='/content/brand-event/'], "
            "a[href*='/content/campaign/'], "
            "a[href*='/content/29-limited-order/'], "
            "a[href*='/content/collection/'], "
            "a[href*='/content/promotion/'], "
            "a[href*='/event/']"
        ),
        limit=limit,
        normalize_href=normalize_link,
        is_allowed=_is_allowed_29cm_link,
    )


def _extract_build_id(html: str) -> str | None:
    match = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
    if match:
        return normalize_space(match.group(1))
    return None


def _build_next_data_url(hub_url: str, build_id: str) -> str:
    parsed = urlparse(hub_url)
    path = parsed.path.rstrip("/")
    suffix = "/index.json" if path in ("", "/") else f"{path}.json"
    return f"{parsed.scheme}://{parsed.netloc}/_next/data/{build_id}{suffix}"


def _extract_links_from_json_payload(payload: Any, hub_url: str, limit: int) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()

    def _visit(node: Any, parent_key: str | None = None) -> None:
        if len(links) >= limit:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                _visit(value, str(key).lower())
        elif isinstance(node, list):
            for item in node:
                _visit(item, parent_key)
        elif isinstance(node, str):
            text = normalize_space(node)
            if not text:
                return

            candidates: list[str] = []
            if parent_key in NEXT_LINK_KEYS:
                candidates.append(text)
            for found in re.findall(r"https://www\.29cm\.co\.kr[^\s\"'<>\\]+", text):
                candidates.append(found)
            for found in re.findall(
                r"(?<![A-Za-z0-9])/(?:store/event|store/showcase|store/exhibition|store/special-order|content/brand-news|content/brand-event|content/campaign|content/29-limited-order|content/collection|content/promotion|event)/[A-Za-z0-9._~/%-]+",
                text,
            ):
                candidates.append(found)

            for candidate in candidates:
                link = normalize_link(candidate, hub_url)
                if not link or link in seen or not _is_allowed_29cm_link(link):
                    continue
                seen.add(link)
                links.append(link)
                if len(links) >= limit:
                    return

    _visit(payload)
    return links


def _extract_detail_links_from_html(html: str, hub_url: str, limit: int) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.select(
        "a[href*='/store/event/'], "
        "a[href*='/store/showcase/'], "
        "a[href*='/store/exhibition/'], "
        "a[href*='/content/brand-news/'], "
        "a[href*='/content/brand-event/'], "
        "a[href*='/content/campaign/'], "
        "a[href*='/content/29-limited-order/'], "
        "a[href*='/content/collection/'], "
        "a[href*='/content/promotion/'], "
        "a[href*='/event/']"
    ):
        link = normalize_link(anchor.get("href", ""), hub_url)
        if not link or link in seen or not _is_allowed_29cm_link(link):
            continue
        seen.add(link)
        links.append(link)
        if len(links) >= limit:
            return links

    for found in re.findall(
        r"https://www\.29cm\.co\.kr[^\s\"'<>\\]+|(?<![A-Za-z0-9])/(?:store/event|store/showcase|store/exhibition|store/special-order|content/brand-news|content/brand-event|content/campaign|content/29-limited-order|content/collection|content/promotion|event)/[A-Za-z0-9._~/%-]+",
        html,
    ):
        link = normalize_link(found, hub_url)
        if not link or link in seen or not _is_allowed_29cm_link(link):
            continue
        seen.add(link)
        links.append(link)
        if len(links) >= limit:
            break
    return links


def _looks_like_sale_event(text: str) -> bool:
    lowered = text.lower()
    if any(token in lowered for token in KEYWORDS):
        return True
    return bool(re.search(r"(?:^|[^0-9A-Za-z])(?:~?\d{1,2}(?:\+\d{1,2})?)%(?:[^0-9A-Za-z]|$)", lowered))


def _extract_image_url(soup: BeautifulSoup, source_url: str) -> str | None:
    for selector in (
        "meta[property='og:image']",
        "meta[name='og:image']",
        "meta[property='twitter:image']",
        "meta[name='twitter:image']",
    ):
        node = soup.select_one(selector)
        if not node:
            continue
        value = normalize_space(node.get("content", ""))
        if value:
            return normalize_link(value, source_url)

    image = soup.select_one("img[src]")
    if image:
        value = normalize_space(image.get("src", ""))
        if value:
            return normalize_link(value, source_url)
    return None


def _extract_meta_content(soup: BeautifulSoup, selector: str) -> str:
    node = soup.select_one(selector)
    if not node:
        return ""
    return normalize_space(node.get("content", ""))


def _clean_29cm_title(title: str) -> str:
    cleaned = normalize_space(title)
    for pattern in TITLE_SUFFIX_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return normalize_space(cleaned)


def _extract_inline_date_text(html: str) -> str:
    snippets: list[str] = []
    for pattern in INLINE_DATE_PATTERNS:
        for match in re.findall(pattern, html, flags=re.IGNORECASE):
            cleaned = normalize_space(match)
            if cleaned and cleaned not in snippets:
                snippets.append(cleaned)
    return " ".join(snippets)


def _extract_brand_event_title_from_body(body_text: str) -> str:
    cleaned = normalize_space(body_text)
    if not cleaned:
        return ""

    cleaned = re.sub(r"^감도\s*깊은\s*취향\s*셀렉트샵\s*29CM\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^감도 깊은 취향 셀렉트샵\s*29CM\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^NEW PRODUCT\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[0-9+%]+\s*", "", cleaned)

    # Fallback to the sentence immediately preceding the inline date.
    date_match = re.search(r"(?:20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}|\d{2}\.\s*\d{1,2}\.\s*\d{1,2})\.\s*(?:-|~)", cleaned)
    if date_match:
        prefix = cleaned[: date_match.start()].strip()
        parts = re.split(r"(?<=[.!?])\s+", prefix)
        if parts:
            candidate = normalize_space(parts[-1])
            candidate = re.sub(r"\s+\d{2}년\s+.+$", "", candidate)
            return normalize_space(candidate)
    return ""


def _extract_brand_event_title_from_body(body_text: str) -> str:
    cleaned = normalize_space(body_text)
    if not cleaned:
        return ""

    cleaned = re.sub(r"^감도\s+깊은\s+취향\s+셀렉트샵\s*29CM\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^NEW PRODUCT\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[0-9+%~]+\s*", "", cleaned)

    date_match = re.search(r"(?:20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}|\d{2}\.\s*\d{1,2}\.\s*\d{1,2})\.\s*(?:-|~)", cleaned)
    if not date_match:
        return ""

    prefix = cleaned[: date_match.start()].strip()
    parts = re.split(r"(?<=[.!?])\s+", prefix)
    if not parts:
        return ""

    candidate = normalize_space(parts[-1])
    candidate = re.sub(r"\s+\d{2}년\s+.+$", "", candidate)
    return normalize_space(candidate)


def _extract_brand_event_title_from_body(body_text: str) -> str:
    cleaned = normalize_space(body_text)
    if not cleaned:
        return ""

    cleaned = re.sub(r"^감도\s*깊은\s*취향\s*셀렉트샵\s*29CM\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^媛먮룄\s+源딆?\s+痍⑦뼢\s+??됲듃??s*29CM\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^NEW PRODUCT\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[~0-9+%]+\s*", "", cleaned)

    date_match = re.search(r"(?:20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}|\d{2}\.\s*\d{1,2}\.\s*\d{1,2})\.\s*(?:-|~)", cleaned)
    if not date_match:
        return ""

    prefix = cleaned[: date_match.start()].strip()
    parts = re.split(r"(?<=[.!?])\s+", prefix)
    if not parts:
        return ""

    candidate = normalize_space(parts[-1])
    candidate = re.sub(r"\s+\d{2}년\s+.+$", "", candidate)
    return normalize_space(candidate)


def _extract_brand_event_title_from_body(body_text: str) -> str:
    cleaned = normalize_space(body_text)
    if not cleaned:
        return ""

    cleaned = re.sub(r"^(?:.*?29CM\s*)+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^NEW PRODUCT\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[~0-9+%]+\s*", "", cleaned)

    date_match = re.search(r"(?:20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}|\d{2}\.\s*\d{1,2}\.\s*\d{1,2})\.\s*(?:-|~)", cleaned)
    if not date_match:
        return ""

    prefix = cleaned[: date_match.start()].strip()
    parts = re.split(r"(?<=[.!?])\s+", prefix)
    if not parts:
        return ""

    candidate = normalize_space(parts[-1])
    candidate = re.sub(r"\s+\d{2}년\s+.+$", "", candidate)
    return normalize_space(candidate)


def _extract_next_data_payload(soup: BeautifulSoup) -> dict[str, Any] | None:
    script = soup.select_one("script#__NEXT_DATA__")
    if not script:
        return None
    raw = script.string or script.get_text()
    raw = raw.strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _extract_collection_candidate_from_next_data(
    payload: dict[str, Any],
    detail_url: str,
) -> dict[str, Any] | None:
    try:
        queries = payload["props"]["pageProps"]["dehydratedState"]["queries"]
    except (KeyError, TypeError):
        return None

    collection_data: dict[str, Any] | None = None
    coupon_data: dict[str, Any] | None = None
    if not isinstance(queries, list):
        return None

    for query in queries:
        if not isinstance(query, dict):
            continue
        data = (((query.get("state") or {}).get("data")))
        if not isinstance(data, dict):
            continue
        if {"title", "description", "displayStartAt", "displayEndAt"} & set(data.keys()):
            collection_data = data
        if "couponName" in data:
            coupon_data = data

    if not collection_data:
        return None

    title = _clean_29cm_title(normalize_space(str(collection_data.get("title", ""))))
    description = normalize_space(str(collection_data.get("description", "")))
    coupon_name = normalize_space(str((coupon_data or {}).get("couponName", "")))
    image_url = normalize_link(normalize_space(str(collection_data.get("coverImageUrl", ""))), detail_url)

    start_candidates = [
        _safe_parse_one(str(collection_data.get("displayStartAt", "")), 2026),
        _safe_parse_one(str((coupon_data or {}).get("couponIssueStartAt", "")), 2026),
    ]
    end_candidates = [
        _safe_parse_one(str(collection_data.get("displayEndAt", "")), 2026),
        _safe_parse_one(str((coupon_data or {}).get("couponIssueEndAt", "")), 2026),
    ]
    valid_starts = [item for item in start_candidates if item]
    valid_ends = [item for item in end_candidates if item]
    start_date = min(valid_starts).isoformat() if valid_starts else None
    end_date = max(valid_ends).isoformat() if valid_ends else None

    body_text = normalize_space(f"{title} {description} {coupon_name}")
    if _is_generic_29cm_title(title):
        return None
    if not (start_date or end_date or _looks_like_sale_event(body_text)):
        return None

    return build_signal_row(
        title=title,
        link=detail_url,
        body_text=body_text,
        platform_hint="29CM",
        category_hint="fashion",
        start_date=start_date,
        end_date=end_date,
        signal_type="detail",
        confidence_score=0.92,
        image_url=image_url,
    )


def _extract_brand_news_candidate_from_next_data(
    payload: dict[str, Any],
    detail_url: str,
) -> dict[str, Any] | None:
    try:
        queries = payload["props"]["pageProps"]["dehydratedState"]["queries"]
    except (KeyError, TypeError):
        return None

    if not isinstance(queries, list):
        return None

    content_data: dict[str, Any] | None = None
    for query in queries:
        if not isinstance(query, dict):
            continue
        data = ((query.get("state") or {}).get("data"))
        if not isinstance(data, dict):
            continue
        if {"title", "description", "displayStartAt", "displayEndAt"} <= set(data.keys()):
            content_data = data
            break

    if not content_data:
        return None

    title = _clean_29cm_title(normalize_space(str(content_data.get("title", ""))))
    description = normalize_space(str(content_data.get("description", "")))
    start_at = _safe_parse_one(str(content_data.get("displayStartAt", "")), 2026)
    end_at = _safe_parse_one(str(content_data.get("displayEndAt", "")), 2026)
    start_date = start_at.isoformat() if start_at else None
    end_date = end_at.isoformat() if end_at else None

    cover_image = content_data.get("coverImage") or {}
    image_url = normalize_link(normalize_space(str(cover_image.get("url", ""))), detail_url)
    body_text = normalize_space(
        f"{title} {description} {content_data.get('promotionRelease', '')} {content_data.get('promotionDiscount', '')}"
    )
    if _is_generic_29cm_title(title):
        return None
    if not (start_date or end_date or _looks_like_sale_event(body_text)):
        return None

    return build_signal_row(
        title=title,
        link=detail_url,
        body_text=body_text,
        platform_hint="29CM",
        category_hint="fashion",
        start_date=start_date,
        end_date=end_date,
        signal_type="detail",
        confidence_score=0.93,
        image_url=image_url,
    )


def _extract_candidate(soup: BeautifulSoup, detail_url: str, html: str) -> dict[str, Any] | None:
    next_data_payload = _extract_next_data_payload(soup)
    if next_data_payload and "/content/collection/" in detail_url:
        next_data_candidate = _extract_collection_candidate_from_next_data(next_data_payload, detail_url)
        if next_data_candidate:
            return next_data_candidate
    if next_data_payload and "/content/brand-news/" in detail_url:
        next_data_candidate = _extract_brand_news_candidate_from_next_data(next_data_payload, detail_url)
        if next_data_candidate:
            return next_data_candidate

    body_text = normalize_space(soup.get_text(" ", strip=True))
    if not body_text:
        return None

    title = ""
    for selector in (
        "h1",
        "meta[property='og:title']",
        "meta[name='og:title']",
        "title",
    ):
        node = soup.select_one(selector)
        if not node:
            continue
        if node.name == "meta":
            title = normalize_space(node.get("content", ""))
        else:
            title = normalize_space(node.get_text(" ", strip=True))
        if title:
            break

    title = _clean_29cm_title(title)
    if _is_generic_29cm_title(title) and "/content/brand-event/" in detail_url:
        title = _extract_brand_event_title_from_body(body_text)
    if _is_generic_29cm_title(title):
        return None

    meta_description = _extract_meta_content(soup, "meta[property='og:description'], meta[name='description']")
    inline_date_text = _extract_inline_date_text(html)
    date_text = normalize_space(f"{title} {meta_description} {inline_date_text} {body_text[:4000]}")
    start_date, end_date = parse_date_range_to_iso(date_text)
    if not _looks_like_sale_event(f"{title} {body_text[:1200]}"):
        if "/content/brand-event/" not in detail_url or not (start_date or end_date):
            return None
    image_url = _extract_image_url(soup, detail_url)
    return build_signal_row(
        title=title,
        link=detail_url,
        body_text=body_text,
        platform_hint="29CM",
        category_hint="fashion",
        start_date=start_date,
        end_date=end_date,
        signal_type="detail",
        confidence_score=0.9,
        image_url=image_url,
    )


def _merge_detail_links(existing: list[str], fresh: list[str], limit: int) -> list[str]:
    merged = list(existing)
    seen = set(existing)
    for link in fresh:
        if link in seen:
            continue
        seen.add(link)
        merged.append(link)
        if len(merged) >= limit:
            break
    return merged[:limit]


def scrape_29cm(
    timeout_seconds: int = 20,
    limit: int = 12,
    debug_save_html: bool = True,
    debug_dir: str = "scraper_debug",
    enable_browser: bool = False,
) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.29cm.co.kr/"})

    rows: list[dict[str, Any]] = []
    debug = init_debug_state(link_key="detail_links_found")
    detail_links: list[str] = []

    if enable_browser:
        try:
            browser_links, browser_reasons, browser_hub_url = _collect_playwright_detail_links(limit)
            if browser_links:
                detail_links = browser_links
                debug["parser_mode"] = "playwright_visible_links"
                debug["detail_links_found"] = len(detail_links)
                debug["reasons"].extend(browser_reasons)
                debug["requested_url"].append(browser_hub_url)
                debug["hub_url"] = browser_hub_url
                debug["valid_source_page_count"] = 1
                print("[29cm] parser_mode=playwright_visible_links")
                print(f"[29cm] hub_url={browser_hub_url}")
                print(f"[29cm] detail_links_found={len(detail_links)}")
            else:
                debug["reasons"].append("playwright_no_visible_links")
        except (RuntimeError, PlaywrightTimeoutError, Exception) as exc:
            debug["reasons"].append(f"playwright_error:{type(exc).__name__}")

    for idx, url in enumerate(_hub_urls()):
        if len(detail_links) >= limit:
            break

        debug["hub_url"] = url
        debug["requested_url"].append(url)
        try:
            response = session.get(url, timeout=timeout_seconds)
            html = _decode_response_text(response)
            debug["hub_http_status"] = str(response.status_code)
            debug["hub_html_length"] = str(len(html))
            debug["http_status"].append(str(response.status_code))
            debug["html_length"].append(str(len(html)))
            print(f"[29cm] requested_url={url}")
            print(f"[29cm] http_status={response.status_code}")
            print(f"[29cm] html_length={len(html)}")

            if response.status_code != 200:
                debug["reasons"].append(f"http_status_{response.status_code}")
                if debug_save_html:
                    _save_snapshot(debug_dir, "29cm_hub", idx, html)
                continue

            debug["valid_source_page_count"] += 1
            html_links = _extract_detail_links_from_html(html, url, limit)
            detail_links = _merge_detail_links(detail_links, html_links, limit)

            build_id = _extract_build_id(html)
            if build_id:
                next_data_url = _build_next_data_url(url, build_id)
                try:
                    next_response = session.get(next_data_url, timeout=timeout_seconds)
                    next_text = _decode_response_text(next_response)
                    debug["requested_url"].append(next_data_url)
                    debug["http_status"].append(str(next_response.status_code))
                    debug["html_length"].append(str(len(next_text)))
                    if next_response.status_code == 200 and next_text.strip():
                        payload = json.loads(next_text)
                        next_links = _extract_links_from_json_payload(payload, url, limit)
                        if next_links:
                            debug["reasons"].append("next_data_link_extract")
                        detail_links = _merge_detail_links(detail_links, next_links, limit)
                except (requests.RequestException, json.JSONDecodeError):
                    debug["reasons"].append("next_data_unavailable")

            debug["detail_links_found"] = len(detail_links)
            print(f"[29cm] detail_links_found={len(detail_links)}")
            if not html_links and debug_save_html:
                _save_snapshot(debug_dir, "29cm_hub", idx, html)
        except requests.RequestException as exc:
            debug["reasons"].append(f"request_error:{type(exc).__name__}")

    for idx, url in enumerate(detail_links):
        debug["requested_url"].append(url)
        try:
            response = session.get(url, timeout=timeout_seconds)
            html = _decode_response_text(response)
            debug["http_status"].append(str(response.status_code))
            debug["html_length"].append(str(len(html)))
            print(f"[29cm] requested_url={url}")
            print(f"[29cm] http_status={response.status_code}")
            print(f"[29cm] html_length={len(html)}")

            if response.status_code != 200:
                debug["reasons"].append(f"detail_http_status_{response.status_code}")
                if debug_save_html:
                    _save_snapshot(debug_dir, "29cm_detail", idx, html)
                continue

            debug["detail_pages_parsed"] += 1
            if debug["parser_mode"] != "playwright_visible_links":
                debug["parser_mode"] = "detail_extract"
            print(f"[29cm] parser_mode={debug['parser_mode']}")

            candidate = _extract_candidate(BeautifulSoup(html, "html.parser"), url, html)
            debug["raw_candidates"] += 1
            if candidate:
                rows.append(candidate)
                debug["filtered_candidates"] += 1
                print("[29cm] items_extracted=1")
            else:
                print("[29cm] items_extracted=0")
                if debug_save_html:
                    _save_snapshot(debug_dir, "29cm_detail", idx, html)

            if len(rows) >= limit:
                break
        except requests.RequestException as exc:
            debug["reasons"].append(f"detail_request_error:{type(exc).__name__}")

    if not rows:
        if debug["valid_source_page_count"] == 0:
            debug["failure_reason"] = "all_seed_urls_failed"
        elif debug["detail_links_found"] == 0:
            debug["failure_reason"] = "no_detail_links_found"
        else:
            debug["failure_reason"] = "filtered_all"
        print(f"[29cm] failure_reason={debug['failure_reason']}")

    debug["items_extracted"] = len(rows[:limit])
    return {"rows": rows[:limit], "debug": debug}
