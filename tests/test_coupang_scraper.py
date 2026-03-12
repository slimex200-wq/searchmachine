import unittest
from unittest.mock import MagicMock, patch

from scrapers.coupang import scrape_coupang


class TestCoupangScraper(unittest.TestCase):
    @patch("scrapers.coupang.requests.Session")
    def test_non_200_seed_urls_do_not_produce_candidates(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        response_403 = MagicMock(status_code=403, text="<html>denied</html>")
        session.get.side_effect = [response_404, response_404, response_403]

        result = scrape_coupang(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertEqual(0, debug["valid_source_page_count"])
        self.assertEqual(0, debug["raw_candidates"])
        self.assertEqual(0, debug["fallback_candidates"])
        self.assertEqual(0, debug["filtered_candidates"])
        self.assertEqual("all_seed_urls_failed", debug["failure_reason"])
        self.assertNotIn("selector_zero", debug["reasons"])


if __name__ == "__main__":
    unittest.main()
