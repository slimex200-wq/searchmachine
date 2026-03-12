from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def clean_text(text: str, max_len: int = 300) -> str:
    cleaned = normalize_space(text)
    return cleaned[:max_len]


def normalize_link(href: str, base_url: str = "") -> str:
    if not href:
        return ""
    merged = urljoin(base_url, href.strip())
    parsed = urlparse(merged)
    # Keep query string; only remove fragment so duplicate comparison becomes more stable.
    return urlunparse(parsed._replace(fragment=""))
