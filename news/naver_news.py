from __future__ import annotations

import html
import re
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import requests

from news.keyword_config import (
    EXCLUDE_PRIORITY_KEYWORDS,
    INCLUDE_PRIORITY_KEYWORDS,
    PLATFORM_HINTS,
    PLATFORM_NEWS_QUERIES,
)
from utils import normalize_space, safe_print

NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"
MAX_NEWS_AGE_DAYS = 30

PARTNERSHIP_KEYWORDS = (
    "콜라보",
    "협업",
    "맞손",
    "제휴",
    "공동 프로모션",
    "공동 회원",
)
ROUNDUP_BRAND_KEYWORDS = (
    "에이블리",
    "지그재그",
    "카카오스타일",
    "오늘의집",
    "nol",
    "야놀자",
    "무신사",
)
BRIEF_NOISE_KEYWORDS = (
    "[브리프]",
    "[브리핑]",
    "[오늘의 유통가]",
    "[daily new",
    "daily new",
    "외",
    "종합",
)
HIGH_SIGNAL_KEYWORDS = (
    "대규모 프로모션",
    "상반기 최대",
    "최대 할인 행사",
    "오는 19일까지",
    "오는 15일까지",
    "페스타 진행",
    "뷰티 페스타",
)
RESULT_NOISE_KEYWORDS = (
    "종료",
    "거래액",
    "급증",
    "품절",
    "성장",
    "기록",
    "역대 최대 성과",
    "브랜드데이",
)
CONTEXT_NOISE_KEYWORDS = (
    "외식",
    "야구",
    "호텔",
    "리빙",
)
ROUNDUP_TITLE_KEYWORDS = (
    "플랫폼 최대",
    "할인 경쟁",
    "총출동",
    "맞대결",
    "줄줄이 시작",
)
PRESS_RELEASE_NOISE_KEYWORDS = (
    "출시",
    "론칭",
    "입점",
    "참가",
    "접점",
    "매출",
    "성과",
    "성장",
    "확대",
    "강화",
    "본격화",
    "전년 동기 대비",
    "채널 내",
    "쇼케이스",
    "앙코르 입점회",
    "pb 전쟁",
)


def _strip_html(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_space(text)


def _parse_pub_date(value: str) -> str | None:
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except Exception:
        return None


def _is_recent_news(
    pub_date: str | None,
    *,
    today: date | None = None,
    max_age_days: int = MAX_NEWS_AGE_DAYS,
) -> bool:
    if not pub_date:
        return False
    today = today or date.today()
    try:
        published = date.fromisoformat(pub_date)
    except ValueError:
        return False
    age_days = (today - published).days
    return 0 <= age_days <= max_age_days


def _platform_guess(text: str) -> str | None:
    lowered = text.lower()
    for platform_key, aliases in PLATFORM_HINTS.items():
        if any(alias.lower() in lowered for alias in aliases):
            return platform_key
    return None


def _contains_partnership_noise(title: str, description: str) -> bool:
    text = normalize_space(f"{title} {description}").lower()
    return any(keyword.lower() in text for keyword in PARTNERSHIP_KEYWORDS)


def _has_multiple_platforms(text: str, primary_platform: str) -> bool:
    lowered = text.lower()
    hit_platforms = {
        platform_key
        for platform_key, aliases in PLATFORM_HINTS.items()
        if any(alias.lower() in lowered for alias in aliases)
    }
    return len(hit_platforms) >= 2 and primary_platform in hit_platforms


def _contains_roundup_noise(title: str, description: str) -> bool:
    text = normalize_space(f"{title} {description}")
    lowered = text.lower()
    has_brand_separator = any(separator in text for separator in ("·", "/", ","))
    has_external_brand = any(keyword.lower() in lowered for keyword in ROUNDUP_BRAND_KEYWORDS)
    return has_brand_separator and has_external_brand


def _contains_brief_noise(title: str, description: str) -> bool:
    text = normalize_space(f"{title} {description}").lower()
    if any(keyword.lower() in text for keyword in BRIEF_NOISE_KEYWORDS):
        return True
    return title.startswith("[") and ("브리" in title or "brief" in text)


def _contains_high_signal_news(title: str, description: str) -> bool:
    text = normalize_space(f"{title} {description}").lower()
    return any(keyword.lower() in text for keyword in HIGH_SIGNAL_KEYWORDS)


def _contains_result_noise(title: str, description: str) -> bool:
    text = normalize_space(f"{title} {description}").lower()
    return any(keyword.lower() in text for keyword in RESULT_NOISE_KEYWORDS)


def _contains_context_noise(title: str, description: str) -> bool:
    text = normalize_space(f"{title} {description}").lower()
    return any(keyword.lower() in text for keyword in CONTEXT_NOISE_KEYWORDS)


def _contains_roundup_title_noise(title: str) -> bool:
    text = normalize_space(title).lower()
    return any(keyword.lower() in text for keyword in ROUNDUP_TITLE_KEYWORDS)


def _contains_press_release_noise(title: str, description: str) -> bool:
    text = normalize_space(f"{title} {description}").lower()
    return any(keyword.lower() in text for keyword in PRESS_RELEASE_NOISE_KEYWORDS)


def _mentions_platform_in_title(title: str, platform_key: str) -> bool:
    lowered = normalize_space(title).lower()
    aliases = PLATFORM_HINTS.get(platform_key, ())
    return any(alias.lower() in lowered for alias in aliases)


def _is_source_mention_noise(title: str, description: str, platform_key: str) -> bool:
    if _mentions_platform_in_title(title, platform_key):
        return False
    combined = normalize_space(f"{title} {description}").lower()
    aliases = PLATFORM_HINTS.get(platform_key, ())
    if not any(alias.lower() in combined for alias in aliases):
        return False
    return _contains_press_release_noise(title, description)


def _is_major_sale_candidate(title: str, description: str) -> tuple[bool, str]:
    text = normalize_space(f"{title} {description}")
    include_hits = [kw for kw in INCLUDE_PRIORITY_KEYWORDS if kw.lower() in text.lower()]
    exclude_hits = [kw for kw in EXCLUDE_PRIORITY_KEYWORDS if kw.lower() in text.lower()]
    if exclude_hits:
        return False, f"exclude_keyword:{exclude_hits[0]}"
    if not include_hits:
        return False, "missing_major_sale_keyword"
    return True, f"include_keyword:{include_hits[0]}"


def scrape_naver_news(
    timeout_seconds: int = 20,
    limit: int = 30,
    debug_save_html: bool = False,
    debug_dir: str = "scraper_debug",
    client_id: str = "",
    client_secret: str = "",
) -> dict[str, Any]:
    debug = {
        "requested_url": [],
        "http_status": [],
        "html_length": [],
        "response_preview": [],
        "raw_candidates": 0,
        "fallback_candidates": 0,
        "filtered_candidates": 0,
        "items_extracted": 0,
        "parser_mode": "api_search",
        "failure_reason": "",
        "reasons": [],
        "error_detail": "",
    }
    rows: list[dict[str, Any]] = []

    if not client_id or not client_secret:
        debug["failure_reason"] = "missing_naver_credentials"
        debug["reasons"].append("missing_naver_credentials")
        safe_print("[naver_news] skipped_reason=missing_naver_credentials")
        return {"rows": rows, "debug": debug}

    session = requests.Session()
    session.headers.update(
        {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
            "Accept": "application/json",
        }
    )

    seen_links: set[str] = set()
    query_limit = max(1, min(limit, 10))
    should_stop = False

    for platform_key, queries in PLATFORM_NEWS_QUERIES.items():
        for query in queries:
            if should_stop:
                break
            request_url = f"{NAVER_NEWS_API_URL}?query={quote(query)}&display={query_limit}&sort=date"
            debug["requested_url"].append(request_url)
            try:
                response = session.get(request_url, timeout=timeout_seconds)
                body = response.text or ""
                debug["http_status"].append(str(response.status_code))
                debug["html_length"].append(str(len(body)))
                debug["response_preview"].append(body[:300])
                safe_print(f'[naver_news] query="{query}"')
                safe_print(f"[naver_news] requested_url={request_url}")
                safe_print(f"[naver_news] http_status={response.status_code}")
                safe_print(f"[naver_news] html_length={len(body)}")
                if body:
                    safe_print(f"[naver_news] response_preview={body[:300]}")
                if response.status_code != 200:
                    debug["reasons"].append(f"http_status_{response.status_code}")
                    if response.status_code == 401:
                        debug["failure_reason"] = "naver_api_auth_failed"
                        safe_print("[naver_news] skipped_reason=naver_api_auth_failed")
                        should_stop = True
                    elif response.status_code == 429:
                        debug["failure_reason"] = "naver_api_rate_limited"
                        safe_print("[naver_news] skipped_reason=naver_api_rate_limited")
                        should_stop = True
                    continue

                data = response.json()
                items = data.get("items", []) if isinstance(data, dict) else []
                total_results = min(
                    len(items),
                    int(data.get("total", len(items)) if isinstance(data, dict) else len(items)),
                )
                safe_print(f'[naver_news] query="{query}" total_results={total_results}')

                for item in items:
                    debug["raw_candidates"] += 1
                    title = _strip_html(str(item.get("title", "")))
                    description = _strip_html(str(item.get("description", "")))
                    link = str(item.get("originallink") or item.get("link") or "").strip()
                    publisher = _strip_html(str(item.get("publisher", "")))
                    pub_date = _parse_pub_date(str(item.get("pubDate", "")))

                    combined_text = f"{title} {description}"
                    platform_guess = _platform_guess(combined_text) or platform_key
                    keep, reason = _is_major_sale_candidate(title, description)
                    if platform_guess != platform_key:
                        keep = False
                        reason = f"platform_mismatch:{platform_guess or 'unknown'}"
                    elif not _is_recent_news(pub_date):
                        keep = False
                        reason = f"stale_news:{pub_date or 'missing'}"
                    elif _contains_brief_noise(title, description):
                        keep = False
                        reason = "brief_noise"
                    elif _contains_partnership_noise(title, description):
                        keep = False
                        reason = "partnership_noise"
                    elif _contains_context_noise(title, description):
                        keep = False
                        reason = "context_noise"
                    elif _contains_result_noise(title, description) and not _contains_high_signal_news(title, description):
                        keep = False
                        reason = "result_noise"
                    elif _is_source_mention_noise(title, description, platform_key) and not _contains_high_signal_news(title, description):
                        keep = False
                        reason = "source_mention_noise"
                    elif _has_multiple_platforms(combined_text, platform_key):
                        keep = False
                        reason = "multi_platform_roundup"
                    elif _contains_roundup_noise(title, description):
                        keep = False
                        reason = "roundup_noise"
                    elif _contains_roundup_title_noise(title):
                        keep = False
                        reason = "roundup_title_noise"
                    elif "플랫폼" in combined_text and not _contains_high_signal_news(title, description):
                        keep = False
                        reason = "platform_roundup_noise"

                    if not link or link in seen_links:
                        continue
                    if not keep:
                        debug["reasons"].append(reason)
                        continue

                    seen_links.add(link)
                    row = {
                        "title": title,
                        "link": link,
                        "source_url": link,
                        "description": description,
                        "content": description,
                        "context": description,
                        "date_text": normalize_space(f"{title} {description}"),
                        "start_date": None,
                        "end_date": None,
                        "platform_hint": platform_guess,
                        "platform_guess": platform_guess,
                        "category_hint": "news",
                        "source_type": "news",
                        "status": "draft",
                        "publish_status": "draft",
                        "review_status": "pending",
                        "publisher": publisher,
                        "pub_date": pub_date,
                    }
                    rows.append(row)
                    debug["filtered_candidates"] += 1
                    if len(rows) >= limit:
                        break

                safe_print(f"[naver_news] candidate_count={debug['filtered_candidates']}")
                if len(rows) >= limit:
                    break
            except requests.RequestException as exc:
                debug["http_status"].append("ERR")
                debug["html_length"].append("0")
                debug["reasons"].append(f"request_error:{type(exc).__name__}")
                debug["error_detail"] = str(exc)
                safe_print(f"[naver_news] skipped_reason=request_error:{type(exc).__name__}")
                if str(exc):
                    safe_print(f"[naver_news] error_detail={exc}")
                should_stop = True
                debug["failure_reason"] = f"request_error:{type(exc).__name__}"
        if len(rows) >= limit:
            break
        if should_stop:
            break

    if not rows and not debug["failure_reason"]:
        debug["failure_reason"] = "no_major_sale_news_candidates"
        safe_print("[naver_news] skipped_reason=no_major_sale_news_candidates")

    debug["items_extracted"] = len(rows)
    return {"rows": rows, "debug": debug}
