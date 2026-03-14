from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None


DEFAULT_URLS = [
    "https://m.oliveyoung.co.kr/m/main/getMMain.do",
    "https://m.oliveyoung.co.kr/m/event/getEventList.do",
    "https://m.oliveyoung.co.kr/m/planshop/getPlanShopList.do",
    "https://www.oliveyoung.co.kr/store/planshop/getPlanShopList.do",
]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Mobile Safari/537.36"
)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _parse_json_arg(raw: str) -> dict[str, str]:
    if not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return {str(k): str(v) for k, v in data.items()}


def _safe_name(url: str) -> str:
    return (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("/", "_")
        .replace("?", "_")
        .replace("&", "_")
        .replace("=", "_")
    )


def run_requests_probe(
    urls: list[str],
    headers: dict[str, str],
    cookies: dict[str, str],
    output_dir: Path,
    timeout_seconds: int,
) -> None:
    session = requests.Session()
    session.headers.update(headers)
    if cookies:
        session.cookies.update(cookies)

    for url in urls:
        name = _safe_name(url)
        meta_path = output_dir / f"{name}.json"
        body_path = output_dir / f"{name}.html"
        result: dict[str, Any] = {"url": url, "mode": "requests"}
        try:
            response = session.get(url, timeout=timeout_seconds, allow_redirects=True)
            result["status_code"] = response.status_code
            result["final_url"] = response.url
            result["headers"] = dict(response.headers)
            result["html_length"] = len(response.text or "")
            body_path.write_text(response.text or "", encoding="utf-8", errors="ignore")
        except requests.RequestException as exc:
            result["error"] = type(exc).__name__
        meta_path.write_text(
            json.dumps(result, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        print(f"[oliveyoung_probe] requests url={url} result={meta_path}")


def run_browser_probe(
    urls: list[str],
    user_agent: str,
    output_dir: Path,
    timeout_seconds: int,
) -> None:
    if sync_playwright is None:
        raise RuntimeError("playwright_unavailable")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                user_agent=user_agent,
                viewport={"width": 412, "height": 915},
            )
            for url in urls:
                name = _safe_name(url)
                meta_path = output_dir / f"{name}.browser.json"
                body_path = output_dir / f"{name}.browser.html"
                shot_path = output_dir / f"{name}.png"
                result: dict[str, Any] = {"url": url, "mode": "browser"}
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
                    page.wait_for_timeout(3000)
                    html = page.content()
                    result["final_url"] = page.url
                    result["title"] = page.title()
                    result["html_length"] = len(html)
                    body_path.write_text(html, encoding="utf-8", errors="ignore")
                    page.screenshot(path=str(shot_path), full_page=True)
                except Exception as exc:
                    result["error"] = type(exc).__name__
                meta_path.write_text(
                    json.dumps(result, ensure_ascii=True, indent=2),
                    encoding="utf-8",
                )
                print(f"[oliveyoung_probe] browser url={url} result={meta_path}")
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Olive Young phase 2 probe")
    parser.add_argument("--urls", nargs="*", default=DEFAULT_URLS)
    parser.add_argument("--headers-json", default="")
    parser.add_argument("--cookies-json", default="")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8"}
    headers.update(_parse_json_arg(args.headers_json))
    cookies = _parse_json_arg(args.cookies_json)

    output_dir = Path(args.output_dir) if args.output_dir else Path("scraper_debug") / f"oliveyoung_phase2_{_timestamp()}"
    output_dir.mkdir(parents=True, exist_ok=True)

    run_requests_probe(args.urls, headers, cookies, output_dir, args.timeout)
    if args.browser:
        run_browser_probe(args.urls, headers["User-Agent"], output_dir, args.timeout)


if __name__ == "__main__":
    main()
