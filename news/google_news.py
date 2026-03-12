from __future__ import annotations

from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote, urlparse
from xml.etree import ElementTree

import requests

from news.keyword_config import PLATFORM_NEWS_QUERIES
from news.naver_news import (
    _contains_partnership_noise,
    _contains_roundup_noise,
    _is_major_sale_candidate,
    _is_recent_news,
    _platform_guess,
    _strip_html,
)
from utils import normalize_space

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"


def _parse_pub_date(value: str) -> str | None:
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except Exception:
        return None


def _strip_google_title(title: str) -> str:
    text = _strip_html(title)
    if " - " in text:
        text = text.rsplit(" - ", 1)[0]
    return text


def _is_clickable_google_news_link(link: str) -> bool:
    host = urlparse(link).netloc.lower()
    return bool(host) and host not in {"news.google.com", "www.news.google.com"}


def scrape_google_news(
    timeout_seconds: int = 20,
    limit: int = 30,
    debug_save_html: bool = False,
    debug_dir: str = "scraper_debug",
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
        "parser_mode": "rss_search",
        "failure_reason": "",
        "reasons": [],
        "error_detail": "",
    }
    rows: list[dict[str, Any]] = []
    session = requests.Session()
    seen_links: set[str] = set()
    query_limit = max(1, min(limit, 10))
    should_stop = False

    for platform_key, queries in PLATFORM_NEWS_QUERIES.items():
        for query in queries:
            if should_stop:
                break
            request_url = (
                f"{GOOGLE_NEWS_RSS_URL}?q={quote(query)}&hl=ko&gl=KR&ceid=KR%3Ako"
            )
            debug["requested_url"].append(request_url)
            try:
                response = session.get(request_url, timeout=timeout_seconds)
                body = response.text or ""
                debug["http_status"].append(str(response.status_code))
                debug["html_length"].append(str(len(body)))
                debug["response_preview"].append(body[:300])
                print(f'[google_news] query="{query}"')
                print(f"[google_news] requested_url={request_url}")
                print(f"[google_news] http_status={response.status_code}")
                print(f"[google_news] html_length={len(body)}")
                if body:
                    print(f"[google_news] response_preview={body[:300]}")
                if response.status_code != 200:
                    debug["reasons"].append(f"http_status_{response.status_code}")
                    continue

                root = ElementTree.fromstring(body)
                items = root.findall("./channel/item")
                print(f'[google_news] query="{query}" total_results={len(items)}')

                for item in items[:query_limit]:
                    debug["raw_candidates"] += 1
                    title = _strip_google_title(item.findtext("title", default=""))
                    description = _strip_html(item.findtext("description", default=""))
                    link = normalize_space(item.findtext("link", default=""))
                    pub_date = _parse_pub_date(item.findtext("pubDate", default=""))

                    combined_text = f"{title} {description}"
                    platform_guess = _platform_guess(combined_text)
                    keep, reason = _is_major_sale_candidate(title, description)

                    if not platform_guess:
                        keep = False
                        reason = "platform_unrecognized"
                    elif platform_guess != platform_key:
                        keep = False
                        reason = f"platform_mismatch:{platform_guess or 'unknown'}"
                    elif not _is_recent_news(pub_date):
                        keep = False
                        reason = f"stale_news:{pub_date or 'missing'}"
                    elif _contains_partnership_noise(title, description):
                        keep = False
                        reason = "partnership_noise"
                    elif _contains_roundup_noise(title, description):
                        keep = False
                        reason = "roundup_noise"

                    if not link or link in seen_links:
                        continue
                    if not _is_clickable_google_news_link(link):
                        debug["reasons"].append("google_redirect_link")
                        continue
                    if not keep:
                        debug["reasons"].append(reason)
                        continue

                    seen_links.add(link)
                    rows.append(
                        {
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
                            "publisher": "Google News",
                            "pub_date": pub_date,
                        }
                    )
                    debug["filtered_candidates"] += 1
                    if len(rows) >= limit:
                        should_stop = True
                        break

                print(f"[google_news] candidate_count={debug['filtered_candidates']}")
            except (requests.RequestException, ElementTree.ParseError) as exc:
                debug["http_status"].append("ERR")
                debug["html_length"].append("0")
                debug["reasons"].append(f"request_error:{type(exc).__name__}")
                debug["error_detail"] = str(exc)
                debug["failure_reason"] = f"request_error:{type(exc).__name__}"
                print(f"[google_news] skipped_reason=request_error:{type(exc).__name__}")
                if str(exc):
                    print(f"[google_news] error_detail={exc}")
                should_stop = True
        if len(rows) >= limit or should_stop:
            break

    if not rows and not debug["failure_reason"]:
        debug["failure_reason"] = "no_major_sale_news_candidates"
        print("[google_news] skipped_reason=no_major_sale_news_candidates")

    debug["items_extracted"] = len(rows)
    return {"rows": rows, "debug": debug}
