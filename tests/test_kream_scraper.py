import unittest
from unittest.mock import MagicMock, patch

import requests

from scrapers.kream import scrape_kream


class TestKreamScraper(unittest.TestCase):
    @patch("scrapers.kream.fetch_playwright_page_html")
    @patch("scrapers.kream.fetch_cloudflare_rendered_html")
    @patch("scrapers.kream.requests.Session")
    def test_non_200_seed_urls_do_not_produce_candidates(
        self,
        session_cls,
        cloudflare_fetch,
        browser_fetch,
    ) -> None:
        session = MagicMock()
        session_cls.return_value = session
        browser_fetch.return_value = ("", ["playwright_html_fetch"])
        cloudflare_fetch.return_value = ("", ["cloudflare_unconfigured"])

        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        response_403 = MagicMock(status_code=403, text="<html>denied</html>")
        session.get.side_effect = [response_404, response_404, response_403, response_403]

        result = scrape_kream(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertEqual(0, debug["valid_source_page_count"])
        self.assertEqual("all_seed_urls_failed", debug["failure_reason"])
        self.assertEqual(0, debug["filtered_candidates"])
        self.assertEqual(4, browser_fetch.call_count)
        self.assertEqual(4, cloudflare_fetch.call_count)

    @patch("scrapers.kream.requests.Session")
    def test_seed_page_metadata_can_create_sale_candidate(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        html = """
        <html>
          <head>
            <title>KREAM SALE EVENT</title>
            <meta name="description" content="KREAM WEEK 3/14 ~ 3/20 discount" />
          </head>
          <body>
            <h1>KREAM WEEK EVENT</h1>
          </body>
        </html>
        """
        response_ok = MagicMock(status_code=200, text=html)
        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        session.get.side_effect = [response_ok, response_404, response_404, response_404]

        result = scrape_kream(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("KREAM SALE EVENT", result["rows"][0]["title"])
        self.assertEqual("KREAM", result["rows"][0]["platform_hint"])
        self.assertEqual("3/14", result["rows"][0]["date_text"])
        self.assertEqual(1, debug["valid_source_page_count"])
        self.assertEqual("", debug["failure_reason"])

    @patch("scrapers.kream.fetch_playwright_page_html")
    @patch("scrapers.kream.fetch_cloudflare_rendered_html")
    @patch("scrapers.kream.requests.Session")
    def test_browser_fallback_can_recover_from_500_seed_url(
        self,
        session_cls,
        cloudflare_fetch,
        browser_fetch,
    ) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response_500 = MagicMock(status_code=500, text="")
        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        session.get.side_effect = [response_500, response_404, response_404, response_404]
        cloudflare_fetch.return_value = ("", ["cloudflare_unconfigured"])
        browser_fetch.return_value = (
            """
            <html>
              <head>
                <title>KREAM WEEK SALE</title>
                <meta name="description" content="스니커즈 3/18 ~ 3/24 할인 이벤트" />
              </head>
              <body><h1>KREAM WEEK</h1></body>
            </html>
            """,
            ["playwright_html_fetch"],
        )

        result = scrape_kream(timeout_seconds=1, limit=5, debug_save_html=False)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("KREAM WEEK SALE", result["rows"][0]["title"])
        self.assertIn("browser_seed_fallback", result["debug"]["reasons"])
        self.assertEqual("", result["debug"]["failure_reason"])

    @patch("scrapers.kream.fetch_playwright_page_html")
    @patch("scrapers.kream.fetch_cloudflare_rendered_html")
    @patch("scrapers.kream.requests.Session")
    def test_cloudflare_fallback_can_recover_when_browser_fails(
        self,
        session_cls,
        cloudflare_fetch,
        browser_fetch,
    ) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response_500 = MagicMock(status_code=500, text="")
        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        session.get.side_effect = [response_500, response_404, response_404, response_404]
        browser_fetch.return_value = ("<html><title>500</title></html>", ["playwright_html_fetch"])
        cloudflare_fetch.return_value = (
            """
            <html>
              <head>
                <title>KREAM WEEK SALE</title>
                <meta name="description" content="스니커즈 3/19 ~ 3/25 할인 행사" />
              </head>
              <body><h1>KREAM WEEK SALE</h1></body>
            </html>
            """,
            ["cloudflare_content_fetch"],
        )

        result = scrape_kream(timeout_seconds=1, limit=5, debug_save_html=False)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("KREAM WEEK SALE", result["rows"][0]["title"])
        self.assertIn("cloudflare_seed_fallback", result["debug"]["reasons"])
        self.assertEqual("", result["debug"]["failure_reason"])

    @patch("scrapers.kream.fetch_cloudflare_rendered_html")
    @patch("scrapers.kream.requests.Session")
    def test_cloudflare_fallback_can_recover_when_request_errors(
        self,
        session_cls,
        cloudflare_fetch,
    ) -> None:
        session = MagicMock()
        session_cls.return_value = session

        session.get.side_effect = requests.ConnectionError("blocked")
        cloudflare_fetch.return_value = (
            """
            <html>
              <head>
                <title>KREAM WEEK SALE</title>
                <meta name="description" content="스니커즈 3/20 ~ 3/26 할인 행사" />
              </head>
              <body><h1>KREAM WEEK SALE</h1></body>
            </html>
            """,
            ["cloudflare_content_fetch"],
        )

        result = scrape_kream(timeout_seconds=1, limit=5, debug_save_html=False)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("KREAM WEEK SALE", result["rows"][0]["title"])
        self.assertIn("request_error:ConnectionError", result["debug"]["reasons"])
        self.assertIn("cloudflare_seed_fallback", result["debug"]["reasons"])
        self.assertEqual("", result["debug"]["failure_reason"])


if __name__ == "__main__":
    unittest.main()
