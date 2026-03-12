import unittest
from unittest.mock import MagicMock, patch

from scrapers.oliveyoung import scrape_oliveyoung


class TestOliveyoungScraper(unittest.TestCase):
    @patch("scrapers.oliveyoung.requests.Session")
    def test_non_200_hub_urls_do_not_produce_candidates(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        session.get.side_effect = [response_404, response_404]

        result = scrape_oliveyoung(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertEqual(0, debug["valid_source_page_count"])
        self.assertEqual(0, debug["detail_links_found"])
        self.assertEqual(0, debug["filtered_candidates"])
        self.assertEqual("all_seed_urls_failed", debug["failure_reason"])


if __name__ == "__main__":
    unittest.main()
