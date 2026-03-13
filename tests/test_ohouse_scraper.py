import unittest
from unittest.mock import MagicMock, patch

from scrapers.ohouse import scrape_ohouse


class TestOhouseScraper(unittest.TestCase):
    @patch("scrapers.ohouse.requests.Session")
    def test_access_denied_pages_are_reported(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        denied_html = """
        <html>
          <head><title>Access Denied</title></head>
          <body>
            <h1>Access Denied</h1>
            You don't have permission to access this server.
            https://errors.edgesuite.net/example
          </body>
        </html>
        """
        response = MagicMock(status_code=403, text=denied_html)
        session.get.side_effect = [response, response, response, response]

        result = scrape_ohouse(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertIn("access_denied_403", debug["reasons"])
        self.assertIn("akamai_access_denied", debug["reasons"])

    @patch("scrapers.ohouse.fetch_playwright_page_html")
    @patch("scrapers.ohouse.requests.Session")
    def test_browser_fallback_reports_denied_result(self, session_cls, fetch_html) -> None:
        session = MagicMock()
        session_cls.return_value = session
        denied_html = """
        <html>
          <head><title>Access Denied</title></head>
          <body>
            <h1>Access Denied</h1>
            You don't have permission to access this server.
            https://errors.edgesuite.net/example
          </body>
        </html>
        """
        response = MagicMock(status_code=403, text=denied_html)
        session.get.side_effect = [response, response, response, response]
        fetch_html.return_value = (denied_html, ["playwright_html_fetch"])

        result = scrape_ohouse(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertIn("playwright_html_fetch", debug["reasons"])
        self.assertIn("browser_access_denied", debug["reasons"])


if __name__ == "__main__":
    unittest.main()
