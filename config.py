from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from utils.filters import DEFAULT_TARGET_PLATFORMS


load_dotenv(override=True)


@dataclass(frozen=True)
class Settings:
    sales_api_url: str
    community_api_url: str
    api_key: str
    naver_client_id: str
    naver_client_secret: str
    request_timeout_seconds: int
    enable_google_news: bool
    enable_community_upload: bool
    enable_community_promotion: bool
    community_target_platforms: tuple[str, ...]
    debug_save_html: bool
    debug_dir: str


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_settings() -> Settings:
    sales_api_url = os.getenv("PICKSALE_SALES_API_URL", "").strip()
    community_api_url = os.getenv("PICKSALE_COMMUNITY_API_URL", "").strip()
    api_key = os.getenv("PICKSALE_API_KEY", "").strip()
    naver_client_id = (
        os.getenv("NAVER_CLIENT_ID", "").strip()
        or os.getenv("NAVER_SEARCH_CLIENT_ID", "").strip()
        or os.getenv("NAVER_API_CLIENT_ID", "").strip()
    )
    naver_client_secret = (
        os.getenv("NAVER_CLIENT_SECRET", "").strip()
        or os.getenv("NAVER_SEARCH_CLIENT_SECRET", "").strip()
        or os.getenv("NAVER_API_CLIENT_SECRET", "").strip()
    )
    timeout_raw = os.getenv("REQUEST_TIMEOUT_SECONDS", "").strip()
    enable_google_news = _to_bool(os.getenv("ENABLE_GOOGLE_NEWS", "true"))
    enable_community_upload = _to_bool(os.getenv("ENABLE_COMMUNITY_UPLOAD", "true"))
    enable_community_promotion = _to_bool(os.getenv("ENABLE_COMMUNITY_PROMOTION", "false"))
    debug_save_html = _to_bool(os.getenv("DEBUG_SAVE_HTML", "true"))
    debug_dir = os.getenv("DEBUG_DIR", "scraper_debug").strip() or "scraper_debug"

    target_platforms_raw = os.getenv(
        "COMMUNITY_TARGET_PLATFORMS",
        ",".join(DEFAULT_TARGET_PLATFORMS),
    ).strip()

    if not sales_api_url:
        raise ValueError("PICKSALE_SALES_API_URL is required in .env")
    if not community_api_url:
        raise ValueError("PICKSALE_COMMUNITY_API_URL is required in .env")
    if not api_key:
        raise ValueError("PICKSALE_API_KEY is required in .env")
    if not timeout_raw:
        raise ValueError("REQUEST_TIMEOUT_SECONDS is required in .env")

    try:
        timeout = int(timeout_raw)
    except ValueError as exc:
        raise ValueError("REQUEST_TIMEOUT_SECONDS must be an integer") from exc

    target_platforms = tuple([p.strip() for p in target_platforms_raw.split(",") if p.strip()])
    if not target_platforms:
        raise ValueError("COMMUNITY_TARGET_PLATFORMS must include at least one platform")

    return Settings(
        sales_api_url=sales_api_url,
        community_api_url=community_api_url,
        api_key=api_key,
        naver_client_id=naver_client_id,
        naver_client_secret=naver_client_secret,
        request_timeout_seconds=timeout,
        enable_google_news=enable_google_news,
        enable_community_upload=enable_community_upload,
        enable_community_promotion=enable_community_promotion,
        community_target_platforms=target_platforms,
        debug_save_html=debug_save_html,
        debug_dir=debug_dir,
    )
