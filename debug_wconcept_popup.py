from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


DEBUG_DIR = Path("scraper_debug")
DEBUG_DIR.mkdir(exist_ok=True)

SCENARIOS = [
    {
        "name": "desktop_home",
        "url": "https://www.wconcept.co.kr/",
        "viewport": {"width": 1280, "height": 900},
        "user_agent": None,
    },
    {
        "name": "mobile_home",
        "url": "https://www.wconcept.co.kr/",
        "viewport": {"width": 430, "height": 932},
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    },
    {
        "name": "mobile_event",
        "url": "https://display.wconcept.co.kr/event",
        "viewport": {"width": 430, "height": 932},
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    },
]

POPUP_SELECTOR = (
    "div.layer.small.update_popup, "
    "div.layer a, "
    "[class*='popup'], "
    "[class*='layer'][style], "
    "[class*='layer']"
)


def main() -> None:
    summaries: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for scenario in SCENARIOS:
                page = browser.new_page(
                    viewport=scenario["viewport"],
                    user_agent=scenario["user_agent"],
                )
                try:
                    page.goto(scenario["url"], wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(5000)

                    screenshot_path = DEBUG_DIR / f"wconcept_{scenario['name']}.png"
                    html_path = DEBUG_DIR / f"wconcept_{scenario['name']}.html"
                    popup_path = DEBUG_DIR / f"wconcept_{scenario['name']}_popup.html"
                    meta_path = DEBUG_DIR / f"wconcept_{scenario['name']}_popup.json"

                    page.screenshot(path=str(screenshot_path), full_page=False)
                    html_path.write_text(page.content(), encoding="utf-8", errors="ignore")

                    popup = page.locator(POPUP_SELECTOR).first
                    popup_count = page.locator(POPUP_SELECTOR).count()

                    popup_html = ""
                    popup_meta: dict[str, str | list[str] | int] = {
                        "scenario": scenario["name"],
                        "url": scenario["url"],
                        "popup_count": popup_count,
                        "popup_links": [],
                        "popup_images": [],
                        "body_has_focus_day": int("FOCUS DAY" in page.content()),
                    }

                    if popup_count:
                        popup_html = popup.evaluate("(e) => e.outerHTML")
                        popup_path.write_text(popup_html, encoding="utf-8", errors="ignore")
                        popup_links = popup.locator("a")
                        popup_meta["popup_links"] = [
                            popup_links.nth(i).get_attribute("href") or "" for i in range(popup_links.count())
                        ]
                        popup_images = popup.locator("img")
                        popup_meta["popup_images"] = [
                            popup_images.nth(i).get_attribute("src") or "" for i in range(popup_images.count())
                        ]
                    else:
                        popup_path.write_text("", encoding="utf-8")

                    meta_path.write_text(
                        json.dumps(popup_meta, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    summaries.append(popup_meta)
                    print(f"[wconcept_popup] scenario={scenario['name']} popup_count={popup_count}")
                    print(f"[wconcept_popup] screenshot={screenshot_path}")
                    if popup_meta["popup_links"]:
                        print(f"[wconcept_popup] popup_links={popup_meta['popup_links']}")
                    if popup_meta["popup_images"]:
                        print(f"[wconcept_popup] popup_images={popup_meta['popup_images']}")
                finally:
                    page.close()
        finally:
            browser.close()

    summary_path = DEBUG_DIR / "wconcept_popup_summary.json"
    summary_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[wconcept_popup] summary={summary_path}")


if __name__ == "__main__":
    main()
