import unittest
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from scrapers.oliveyoung import _extract_candidate, _extract_detail_links, scrape_oliveyoung


class TestOliveyoungScraper(unittest.TestCase):
    @patch("scrapers.oliveyoung.requests.Session")
    def test_non_200_hub_urls_do_not_produce_candidates(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        session.get.return_value = response_404

        result = scrape_oliveyoung(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertEqual(0, debug["valid_source_page_count"])
        self.assertEqual(0, debug["detail_links_found"])
        self.assertEqual(0, debug["filtered_candidates"])
        self.assertEqual("all_seed_urls_failed", debug["failure_reason"])

    def test_extract_detail_links_from_hub_html(self) -> None:
        soup = BeautifulSoup(
            """
            <html><body>
                <a href="/store/event/getEventDetail.do?evtNo=123">올영세일</a>
                <a href="/store/planshop/getPlanShopDetail.do?dispCatNo=9000001001">브랜드 기획전</a>
                <a href="/store/goods/getGoodsDetail.do?goodsNo=A0001">상품</a>
            </body></html>
            """,
            "html.parser",
        )

        links = _extract_detail_links(soup, "https://www.oliveyoung.co.kr/store/event/getEventList.do", limit=5)

        self.assertEqual(2, len(links))
        self.assertTrue(any("geteventdetail.do" in link.lower() for link in links))
        self.assertTrue(any("getplanshopdetail.do" in link.lower() for link in links))

    def test_extract_candidate_parses_title_dates_and_image(self) -> None:
        soup = BeautifulSoup(
            """
            <html>
                <head>
                    <meta property="og:title" content="올영세일 | 올리브영" />
                    <meta property="og:image" content="https://image.example.com/oliveyoung.jpg" />
                </head>
                <body>
                    <h1>올영세일</h1>
                    <div>03.01 ~ 03.07 최대 70% 할인</div>
                </body>
            </html>
            """,
            "html.parser",
        )

        candidate = _extract_candidate(soup, "https://www.oliveyoung.co.kr/store/event/getEventDetail.do?evtNo=123")

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual("올영세일", candidate["title"])
        self.assertEqual("2026-03-01", candidate["start_date"])
        self.assertEqual("2026-03-07", candidate["end_date"])
        self.assertEqual("https://image.example.com/oliveyoung.jpg", candidate["image_url"])
        self.assertEqual("올리브영", candidate["platform_hint"])


if __name__ == "__main__":
    unittest.main()
