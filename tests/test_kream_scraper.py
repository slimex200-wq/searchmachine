import unittest
from unittest.mock import MagicMock, patch

from scrapers.kream import scrape_kream


class TestKreamScraper(unittest.TestCase):
    @patch("scrapers.kream.requests.Session")
    def test_non_200_seed_urls_do_not_produce_candidates(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        response_403 = MagicMock(status_code=403, text="<html>denied</html>")
        session.get.side_effect = [response_404, response_404, response_403, response_403]

        result = scrape_kream(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertEqual(0, debug["valid_source_page_count"])
        self.assertEqual("all_seed_urls_failed", debug["failure_reason"])
        self.assertEqual(0, debug["filtered_candidates"])

    @patch("scrapers.kream.requests.Session")
    def test_seed_page_metadata_can_create_sale_candidate(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        html = """
        <html>
          <head>
            <title>KREAM 스니커즈 세일</title>
            <meta name="description" content="리셀 인기 모델 대상 3/14 ~ 3/20 할인 혜택" />
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
        self.assertEqual("KREAM 스니커즈 세일", result["rows"][0]["title"])
        self.assertEqual("KREAM", result["rows"][0]["platform_hint"])
        self.assertEqual("3/14", result["rows"][0]["date_text"])
        self.assertEqual(1, debug["valid_source_page_count"])
        self.assertEqual("", debug["failure_reason"])

    @patch("scrapers.kream.fetch_playwright_page_html")
    @patch("scrapers.kream.requests.Session")
    def test_browser_fallback_can_recover_from_500_seed_url(self, session_cls, browser_fetch) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response_500 = MagicMock(status_code=500, text="")
        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        session.get.side_effect = [response_500, response_404, response_404, response_404]
        browser_fetch.return_value = (
            """
            <html>
              <head>
                <title>KREAM 한정판 위크</title>
                <meta name="description" content="한정판 스니커즈 3/18 ~ 3/24 할인 이벤트" />
              </head>
              <body><h1>KREAM WEEK</h1></body>
            </html>
            """,
            ["playwright_html_fetch"],
        )

        result = scrape_kream(timeout_seconds=1, limit=5, debug_save_html=False)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("KREAM 한정판 위크", result["rows"][0]["title"])
        self.assertIn("browser_seed_fallback", result["debug"]["reasons"])
        self.assertEqual("", result["debug"]["failure_reason"])


if __name__ == "__main__":
    unittest.main()
