import unittest
from unittest.mock import MagicMock, patch

from community.clien import scrape_clien


class TestClienScraper(unittest.TestCase):
    @patch("community.clien.requests.Session")
    def test_non_200_seed_urls_do_not_produce_candidates(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        session.get.side_effect = [
            MagicMock(status_code=404, text="<html>not found</html>"),
            MagicMock(status_code=403, text="<html>denied</html>"),
        ]

        result = scrape_clien(timeout_seconds=1, limit=5, debug_save_html=False)

        self.assertEqual([], result["rows"])
        self.assertEqual(0, result["debug"]["raw_candidates"])
        self.assertEqual(0, result["debug"]["filtered_candidates"])

    @patch("community.clien.requests.Session")
    def test_extracts_sale_signal_posts_from_listing(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        html = """
        <html><body>
        <div class="list_item symph_row">
          <a class="subject_fixed" href="/service/board/jirum/20000001">SSG 봄 혜택 기획전 최대 20% 할인</a>
          <span>SSG 행사 기간 2026-03-09 ~ 2026-03-12</span>
        </div>
        <div class="list_item symph_row">
          <a class="subject_fixed" href="/service/board/jirum/20000002">쿠폰</a>
        </div>
        </body></html>
        """
        session.get.return_value = MagicMock(status_code=200, text=html)

        result = scrape_clien(timeout_seconds=1, limit=5, debug_save_html=False)
        row = result["rows"][0]

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("community", row["signal_type"])
        self.assertEqual("clien", row["source_site"])
        self.assertTrue(row["link"].startswith("https://www.clien.net/service/board/jirum/20000001"))


if __name__ == "__main__":
    unittest.main()
