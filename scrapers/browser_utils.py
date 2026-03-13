from __future__ import annotations

from typing import Any, Callable

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None
    PlaywrightTimeoutError = Exception


def collect_locator_links(
    page: Any,
    selector: str,
    entry_url: str,
    limit: int,
    normalize_href: Callable[[str, str], str],
    is_allowed: Callable[[str], bool],
    seen: set[str] | None = None,
) -> tuple[list[str], int]:
    links: list[str] = []
    local_seen = seen if seen is not None else set()
    locator = page.locator(selector)
    count = locator.count()

    for idx in range(count):
        href = locator.nth(idx).get_attribute("href") or ""
        link = normalize_href(href, entry_url)
        if not link or link in local_seen or not is_allowed(link):
            continue
        local_seen.add(link)
        links.append(link)
        if len(links) >= limit:
            break

    return links, count


def _looks_like_cloudflare_challenge(html: str) -> bool:
    lowered = html.lower()
    return any(
        marker in lowered
        for marker in (
            "challenge-error-text",
            "enable javascript and cookies to continue",
            "/cdn-cgi/challenge-platform/",
            "window._cf_chl_opt",
            "cloudflare-branding",
            "cf_chl_opt",
            "cf-challenge-running",
        )
    )


def _wait_for_challenge_clear(page: Any, timeout_ms: int) -> tuple[str, list[str]]:
    reasons: list[str] = []
    html = page.content()
    if not _looks_like_cloudflare_challenge(html):
        return html, reasons

    reasons.append("cloudflare_challenge_detected")
    wait_slices_ms = (5000, 8000, 10000)
    elapsed_ms = 0

    for slice_ms in wait_slices_ms:
        if elapsed_ms >= timeout_ms:
            break
        page.wait_for_timeout(slice_ms)
        elapsed_ms += slice_ms
        try:
            page.wait_for_load_state("networkidle", timeout=min(5000, max(1000, timeout_ms - elapsed_ms)))
        except Exception:
            pass
        html = page.content()
        if not _looks_like_cloudflare_challenge(html):
            reasons.append("cloudflare_challenge_cleared")
            return html, reasons

    reasons.append("cloudflare_challenge_persisted")
    return html, reasons


def collect_playwright_visible_links(
    entry_configs: list[dict[str, Any]],
    selector: str,
    limit: int,
    normalize_href: Callable[[str, str], str],
    is_allowed: Callable[[str], bool],
) -> tuple[list[str], list[str], str]:
    if sync_playwright is None:
        raise RuntimeError("playwright_unavailable")

    detail_links: list[str] = []
    reasons: list[str] = []
    seen: set[str] = set()
    selected_hub_url = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for config in entry_configs:
                entry_url = str(config["url"])
                selected_hub_url = entry_url
                page = browser.new_page(
                    viewport=config["viewport"],
                    user_agent=config["user_agent"],
                )
                try:
                    page.goto(entry_url, wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(3000)
                    _, challenge_reasons = _wait_for_challenge_clear(page, timeout_ms=20000)
                    reasons.extend(challenge_reasons)

                    links, anchor_count = collect_locator_links(
                        page=page,
                        selector=selector,
                        entry_url=entry_url,
                        limit=limit,
                        normalize_href=normalize_href,
                        is_allowed=is_allowed,
                        seen=seen,
                    )
                    if anchor_count:
                        reasons.append(f"playwright_anchor_detected:{anchor_count}")
                    detail_links.extend(links)

                    if detail_links:
                        reasons.append("playwright_visible_link_extract")
                        break
                finally:
                    page.close()
        finally:
            browser.close()

    return detail_links[:limit], reasons, selected_hub_url


def fetch_playwright_page_html(
    url: str,
    viewport: dict[str, int],
    user_agent: str,
    timeout_ms: int = 60000,
) -> tuple[str, list[str]]:
    if sync_playwright is None:
        raise RuntimeError("playwright_unavailable")

    reasons: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport=viewport, user_agent=user_agent)
            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                page.wait_for_timeout(2000)
                _, challenge_reasons = _wait_for_challenge_clear(page, timeout_ms=min(20000, timeout_ms))
                reasons.extend(challenge_reasons)
                reasons.append("playwright_html_fetch")
                return page.content(), reasons
            finally:
                page.close()
        finally:
            browser.close()
