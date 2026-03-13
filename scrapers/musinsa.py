from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.scraper_utils import build_signal_row, init_debug_state
from utils import normalize_link, normalize_space, parse_date_range_to_iso

KEYWORDS = (
    "sale",
    "event",
    "campaign",
    "plan",
    "special",
    "할인",
    "세일",
    "특가",
    "혜택",
    "기획전",
    "행사",
    "프로모션",
    "이벤트",
    "페스타",
)

GENERIC_TITLES = {
    "musinsa",
    "무신사",
    "무신사 콘텐츠",
    "musinsa content",
    "campaign",
    "content",
    "event",
    "이벤트",
}


def _hub_urls() -> list[str]:
    return [
        "https://www.musinsa.com/main/musinsa/sale",
        "https://www.musinsa.com/main/musinsa/beauty",
        "https://www.musinsa.com/content/list?contentCategoryCode=013",
        "https://www.musinsa.com/content/list?contentCategoryCode=014",
        "https://www.musinsa.com/events/main",
    ]


def _save_snapshot(debug_dir: str, source: str, idx: int, html: str) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{source}_{idx}.html")
    with open(path, "w", encoding="utf-8", errors="ignore") as file:
        file.write(html)


def _decode_response(response: requests.Response) -> str:
    content = response.content or b""
    for encoding in ("utf-8", response.encoding, response.apparent_encoding, "cp949"):
        if not encoding:
            continue
        try:
            return content.decode(encoding, errors="strict")
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("utf-8", errors="ignore")


def _normalize_musinsa_link(href: str, source_url: str) -> str:
    link = normalize_link(href, source_url)
    if not link or link.startswith("musinsa://"):
        return ""
    if link.startswith("https://www.musinsa.com/app/"):
        link = link.replace("https://www.musinsa.com/app/", "https://www.musinsa.com/")
    host = urlparse(link).netloc.lower()
    if host.endswith("musinsa.com") or host.endswith("link.musinsa.com"):
        return link
    return ""


def _normalize_musinsa_media_link(href: str, source_url: str) -> str:
    link = normalize_link(href, source_url)
    if not link or link.startswith("musinsa://"):
        return ""
    parsed = urlparse(link)
    if parsed.scheme not in {"http", "https"}:
        return ""
    return link


def _extract_campaign_image_url(soup: BeautifulSoup, detail_url: str) -> str:
    container = soup.select_one("[class^='CampaignDetail__CampaignContainer']")
    candidates: list[str] = []

    if container:
        video = container.select_one("video")
        if video:
            candidates.extend(
                [
                    video.get("poster", ""),
                    video.get("src", ""),
                ]
            )
            source = video.select_one("source[src]")
            if source:
                candidates.append(source.get("src", ""))

        # Campaign pages often expose the hero as a plain image instead of a video.
        key_visual = container.select_one("[class*='KeyVisual__Container']")
        if key_visual:
            image = key_visual.select_one("img[src]")
            if image:
                candidates.append(image.get("src", ""))

    for selector in (
        "meta[property='og:image']",
        "meta[name='twitter:image']",
    ):
        node = soup.select_one(selector)
        if node:
            candidates.append(node.get("content", ""))

    for candidate in candidates:
        normalized = _normalize_musinsa_media_link(str(candidate or ""), detail_url)
        if normalized:
            return normalized
    return ""


def _is_allowed_detail_link(link: str) -> bool:
    path = urlparse(link).path.lower()
    if any(token in path for token in ("/goods/", "/category/", "/used/", "/brand/")):
        return False
    return any(token in path for token in ("/campaign/", "/content/"))


def _walk_json(node: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            out.append(cur)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return out


def _extract_next_data_json(soup: BeautifulSoup) -> dict[str, Any] | None:
    node = soup.find("script", id="__NEXT_DATA__")
    if not node or not node.string:
        return None
    try:
        return json.loads(node.string)
    except Exception:
        return None


def _extract_detail_links(soup: BeautifulSoup, hub_url: str, limit: int) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href*='/campaign/'], a[href*='/content/']"):
        link = _normalize_musinsa_link(anchor.get("href", ""), hub_url)
        if not link or link in seen or not _is_allowed_detail_link(link):
            continue
        seen.add(link)
        links.append(link)
        if len(links) >= limit:
            return links

    next_data = _extract_next_data_json(soup)
    if not next_data:
        return links

    for obj in _walk_json(next_data):
        link_raw = obj.get("url") or obj.get("link") or obj.get("path")
        title = normalize_space(str(obj.get("title") or obj.get("name") or ""))
        if not link_raw:
            continue
        link = _normalize_musinsa_link(str(link_raw), hub_url)
        if not link or link in seen or not _is_allowed_detail_link(link):
            continue
        if title and not any(keyword in title.lower() for keyword in KEYWORDS):
            title_type = str(obj.get("type") or "")
            if title_type != "custom_basic":
                continue
        seen.add(link)
        links.append(link)
        if len(links) >= limit:
            break

    return links


def _merge_detail_links(existing: list[str], new_links: list[str], limit: int) -> list[str]:
    merged = list(existing)
    seen = set(existing)
    for link in new_links:
        if link in seen:
            continue
        seen.add(link)
        merged.append(link)
        if len(merged) >= limit:
            break
    return merged


def _extract_date_window(text: str) -> tuple[str | None, str | None]:
    start_date, end_date = parse_date_range_to_iso(text)
    if start_date or end_date:
        return start_date, end_date

    month_day_matches = re.findall(r"(\d{1,2})[./](\d{1,2})(?:\([^)]*\))?", text)
    if len(month_day_matches) < 2:
        return None, None

    inferred_dates: list[date] = []
    current_year = date.today().year
    for month_value, day_value in month_day_matches:
        try:
            inferred_dates.append(date(current_year, int(month_value), int(day_value)))
        except ValueError:
            continue

    if len(inferred_dates) < 2:
        return None, None

    start = min(inferred_dates)
    end = max(inferred_dates)
    if (end - start).days > 45:
        return None, None

    return start.isoformat(), end.isoformat()


def _extract_json_title(next_data: dict[str, Any] | None) -> str:
    if not next_data:
        return ""
    candidates = [
        next_data.get("props", {}).get("pageProps", {}).get("initialData", {}).get("meta", {}).get("title"),
        next_data.get("props", {}).get("pageProps", {}).get("initialData", {}).get("meta", {}).get("name"),
        next_data.get("props", {}).get("pageProps", {}).get("initialData", {}).get("meta", {}).get("description"),
    ]
    for candidate in candidates:
        title = normalize_space(str(candidate or ""))
        if title and not _is_generic_title(title):
            return title
    return ""


def _extract_event_summary(next_data: dict[str, Any] | None) -> str:
    if not next_data:
        return ""
    modules = next_data.get("props", {}).get("pageProps", {}).get("initialData", {}).get("modules", [])
    if not isinstance(modules, list):
        return ""
    parts: list[str] = []
    for module in modules:
        if not isinstance(module, dict):
            continue
        contents = module.get("contents", {})
        if not isinstance(contents, dict):
            continue
        for key in ("title", "subTitle", "description"):
            value = contents.get(key)
            if isinstance(value, str):
                cleaned = normalize_space(value)
                if cleaned:
                    parts.append(cleaned)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        cleaned = normalize_space(str(item.get("value") or ""))
                        if cleaned:
                            parts.append(cleaned)
    return normalize_space(" ".join(parts))


def _is_generic_title(title: str) -> bool:
    return normalize_space(title).lower() in GENERIC_TITLES


def _extract_candidate(soup: BeautifulSoup, detail_url: str, html: str) -> dict[str, Any] | None:
    next_data = _extract_next_data_json(soup)
    title_node = soup.select_one("h1, .tit, .title")
    title_tag = soup.select_one("title")
    og_title = soup.select_one("meta[property='og:title']")
    body_text = normalize_space(soup.get_text(" ", strip=True))
    json_summary = _extract_event_summary(next_data)

    title = normalize_space(title_node.get_text(" ", strip=True) if title_node else "")
    if (not title or _is_generic_title(title)) and og_title:
        title = normalize_space(og_title.get("content", ""))
    if (not title or _is_generic_title(title)) and title_tag:
        title = normalize_space(title_tag.get_text(" ", strip=True))
    if not title or _is_generic_title(title):
        title = _extract_json_title(next_data)
    if not title:
        return None

    blob = normalize_space(f"{title} {json_summary} {body_text[:2000]}").lower()
    if not any(keyword in blob for keyword in KEYWORDS):
        return None

    start_date, end_date = _extract_date_window(blob)
    image_url = _extract_campaign_image_url(soup, detail_url)
    return build_signal_row(
        title=title,
        link=detail_url,
        body_text=json_summary or body_text,
        platform_hint="MUSINSA",
        category_hint="fashion",
        start_date=start_date,
        end_date=end_date,
        signal_type="detail",
        confidence_score=0.9,
        image_url=image_url,
    )


def scrape_musinsa(
    timeout_seconds: int = 20,
    limit: int = 12,
    debug_save_html: bool = True,
    debug_dir: str = "scraper_debug",
) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.musinsa.com/"})

    rows: list[dict[str, Any]] = []
    debug = init_debug_state(link_key="detail_links_found")
    detail_links: list[str] = []

    for idx, url in enumerate(_hub_urls()):
        debug["hub_url"] = url
        debug["requested_url"].append(url)
        try:
            response = session.get(url, timeout=timeout_seconds)
            html = _decode_response(response)
            debug["hub_http_status"] = str(response.status_code)
            debug["hub_html_length"] = str(len(html))
            debug["http_status"].append(str(response.status_code))
            debug["html_length"].append(str(len(html)))
            print(f"[musinsa] hub_url={url}")
            print(f"[musinsa] hub_http_status={response.status_code}")
            print(f"[musinsa] hub_html_length={len(html)}")

            if response.status_code != 200:
                debug["reasons"].append(f"http_status_{response.status_code}")
                if debug_save_html:
                    _save_snapshot(debug_dir, "musinsa_hub", idx, html)
                continue

            debug["valid_source_page_count"] += 1
            if not html.strip():
                debug["failure_reason"] = "no_valid_source_page"
                continue

            soup = BeautifulSoup(html, "html.parser")
            hub_detail_links = _extract_detail_links(soup, url, limit)
            detail_links = _merge_detail_links(detail_links, hub_detail_links, limit)
            if hub_detail_links:
                debug["reasons"].append("next_data_hub_links")
            debug["detail_links_found"] = len(detail_links)
            print(f"[musinsa] detail_links_found={len(detail_links)}")
            if not hub_detail_links and debug_save_html:
                _save_snapshot(debug_dir, "musinsa_hub", idx, html)
            if len(detail_links) >= limit:
                break
        except requests.RequestException as exc:
            debug["reasons"].append(f"request_error:{type(exc).__name__}")
            debug["failure_reason"] = f"request_error:{type(exc).__name__}"

    for idx, url in enumerate(detail_links):
        debug["requested_url"].append(url)
        try:
            response = session.get(url, timeout=timeout_seconds)
            html = _decode_response(response)
            debug["http_status"].append(str(response.status_code))
            debug["html_length"].append(str(len(html)))
            print(f"[musinsa] requested_url={url}")
            print(f"[musinsa] http_status={response.status_code}")
            print(f"[musinsa] html_length={len(html)}")

            if response.status_code != 200:
                debug["reasons"].append(f"detail_http_status_{response.status_code}")
                if debug_save_html:
                    _save_snapshot(debug_dir, "musinsa_detail", idx, html)
                continue

            debug["detail_pages_parsed"] += 1
            debug["parser_mode"] = "detail_extract"
            print("[musinsa] parser_mode=detail_extract")
            candidate = _extract_candidate(BeautifulSoup(html, "html.parser"), url, html)
            debug["raw_candidates"] += 1
            if candidate:
                rows.append(candidate)
                debug["filtered_candidates"] += 1
                print("[musinsa] items_extracted=1")
            else:
                print("[musinsa] items_extracted=0")
                if debug_save_html:
                    _save_snapshot(debug_dir, "musinsa_detail", idx, html)
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
        print(f"[musinsa] failure_reason={debug['failure_reason']}")

    debug["items_extracted"] = len(rows[:limit])
    return {"rows": rows[:limit], "debug": debug}
