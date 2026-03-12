import unittest
from unittest.mock import MagicMock, patch

from scrapers.ssg import _extract_date_window, scrape_ssg


class TestSsgScraper(unittest.TestCase):
    def test_extract_date_window_supports_short_month_day_range(self) -> None:
        start_date, end_date = _extract_date_window("2026 SS COLLECTION 패션명품 쓱세일 3.9 - 15")

        self.assertEqual("2026-03-09", start_date)
        self.assertEqual("2026-03-15", end_date)

    def test_extract_date_window_supports_weekday_and_time_noise(self) -> None:
        start_date, end_date = _extract_date_window("발급 및 사용 기간 : 3.9(월) 09:00 - 15(일) 23:59")

        self.assertEqual("2026-03-09", start_date)
        self.assertEqual("2026-03-15", end_date)

    def test_extract_date_window_supports_multiple_phase_ranges(self) -> None:
        start_date, end_date = _extract_date_window("발급 및 사용기간 1차 3/5(목)-11(수), 2차 3/12(목)-15(일)")

        self.assertEqual("2026-03-05", start_date)
        self.assertEqual("2026-03-15", end_date)

    @patch("scrapers.ssg.requests.Session")
    def test_detail_page_extracts_image_url_from_og_image(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="https://event.ssg.com/eventDetail.ssg?nevntId=1000000021660">detail</a>
        </body></html>
        """
        detail_html = """
        <html>
        <head>
          <meta property="og:title" content="패션명품 쓱세일" />
          <meta property="og:image" content="https://image.ssgcdn.com/banner/ssg-sale.jpg" />
        </head>
        <body>
          <h1>패션명품 쓱세일</h1>
          <div>3.9 - 15 최대 60% 할인</div>
        </body>
        </html>
        """
        session.get.side_effect = [
            MagicMock(status_code=200, text=hub_html),
            MagicMock(status_code=200, text=detail_html),
        ]

        result = scrape_ssg(timeout_seconds=1, limit=3, debug_save_html=False)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("https://image.ssgcdn.com/banner/ssg-sale.jpg", result["rows"][0].get("image_url"))
        self.assertEqual("2026-03-09", result["rows"][0].get("start_date"))
        self.assertEqual("2026-03-15", result["rows"][0].get("end_date"))

    @patch("scrapers.ssg.requests.Session")
    def test_non_200_hub_urls_do_not_produce_candidates(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        response_403 = MagicMock(status_code=403, text="<html>denied</html>")
        session.get.side_effect = [response_404, response_404, response_403]

        result = scrape_ssg(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertEqual(0, debug["valid_source_page_count"])
        self.assertEqual(0, debug["detail_links_found"])
        self.assertEqual(0, debug["filtered_candidates"])
        self.assertEqual("all_seed_urls_failed", debug["failure_reason"])

    @patch("scrapers.ssg.requests.Session")
    def test_homepage_direct_extract_can_capture_large_promo(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        home_html = """
        <html><body>
        <section>SSG 기획전 최대 20% 할인 2026-03-09 ~ 2026-03-12</section>
        </body></html>
        """
        session.get.return_value = MagicMock(status_code=200, text=home_html)

        result = scrape_ssg(timeout_seconds=1, limit=3, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual("home_direct_extract", debug["parser_mode"])
        self.assertEqual(1, debug["filtered_candidates"])
        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("https://www.ssg.com/", result["rows"][0]["link"])

    @patch("scrapers.ssg.requests.Session")
    def test_hub_page_prefers_event_detail_links(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="/event/eventMain.ssg">main</a>
        <a href="/event/winnerList.ssg">winner</a>
        <a href="https://event.ssg.com/eventDetail.ssg?nevntId=1000000021642">detail</a>
        </body></html>
        """
        detail_html = """
        <html><head><meta property="og:title" content="12th 해피버쓱데이!" /></head>
        <body><h1>12th 해피버쓱데이!</h1><div>2026-03-09 ~ 2026-03-12 event</div></body></html>
        """
        hub_resp = MagicMock(status_code=200, text=hub_html)
        detail_resp = MagicMock(status_code=200, text=detail_html)
        session.get.side_effect = [hub_resp, detail_resp]

        result = scrape_ssg(timeout_seconds=1, limit=3, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual(1, debug["detail_links_found"])
        self.assertEqual(1, debug["detail_pages_parsed"])
        self.assertEqual(1, debug["filtered_candidates"])
        self.assertEqual("https://event.ssg.com/eventDetail.ssg?nevntId=1000000021642", result["rows"][0]["link"])
        self.assertEqual("12th 해피버쓱데이!", result["rows"][0]["title"])

    @patch("scrapers.ssg._collect_playwright_detail_links")
    @patch("scrapers.ssg.requests.Session")
    def test_playwright_visible_links_use_browser_hub_and_detail_links(self, session_cls, collect_links_mock) -> None:
        session = MagicMock()
        session_cls.return_value = session
        collect_links_mock.return_value = (
            ["https://event.ssg.com/eventDetail.ssg?nevntId=1000000021642"],
            ["playwright_visible_link_extract"],
            "https://www.ssg.com/event/eventMain.ssg",
        )

        detail_html = """
        <html><head><meta property="og:title" content="Big Event Benefit" /></head>
        <body><h1>Big Event Benefit</h1><div>2026-03-09 ~ 2026-03-12 event</div></body></html>
        """
        session.get.return_value = MagicMock(status_code=200, text=detail_html)

        result = scrape_ssg(timeout_seconds=1, limit=3, debug_save_html=False, enable_browser=True)
        debug = result["debug"]

        self.assertEqual("playwright_visible_links", debug["parser_mode"])
        self.assertEqual("https://www.ssg.com/event/eventMain.ssg", debug["hub_url"])
        self.assertEqual(
            ["https://www.ssg.com/event/eventMain.ssg", "https://event.ssg.com/eventDetail.ssg?nevntId=1000000021642"],
            debug["requested_url"],
        )
        self.assertEqual(1, debug["detail_links_found"])
        self.assertEqual(1, debug["filtered_candidates"])
        self.assertEqual(1, len(result["rows"]))

    @patch("scrapers.ssg.requests.Session")
    def test_detail_page_can_use_page_title_script_and_korean_keywords(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="https://event.ssg.com/eventDetail.ssg?nevntId=1000000021710">detail</a>
        </body></html>
        """
        detail_html = """
        <html><head>
        <title>SSG.COM</title>
        <script>
        window.GA4_dataLayer = window.GA4_dataLayer || [];
        window.GA4_dataLayer.push({
            Page_title : '기획전',
            Page_url : window.location.href
        });
        </script>
        </head>
        <body><div>최대 20% 할인 2026-03-09 ~ 2026-03-12</div></body></html>
        """
        session.get.side_effect = [
            MagicMock(status_code=200, text=hub_html),
            MagicMock(status_code=200, text=detail_html),
        ]

        result = scrape_ssg(timeout_seconds=1, limit=3, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual(1, debug["filtered_candidates"])
        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("기획전", result["rows"][0]["title"])

    @patch("scrapers.ssg.requests.Session")
    def test_ssg_club_promo_is_filtered_as_noise(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="https://event.ssg.com/eventDetail.ssg?nevntId=1000000021654">detail</a>
        </body></html>
        """
        detail_html = """
        <html>
        <head><meta property="og:title" content="쓱7클럽은 티빙도 무료" /></head>
        <body>
          <h1>쓱7클럽은 티빙도 무료</h1>
          <div>2026-03-05 ~ 2026-03-15 이벤트</div>
        </body>
        </html>
        """
        session.get.side_effect = [
            MagicMock(status_code=200, text=hub_html),
            MagicMock(status_code=200, text=detail_html),
        ]

        result = scrape_ssg(timeout_seconds=1, limit=3, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertEqual(1, debug["raw_candidates"])
        self.assertEqual(0, debug["filtered_candidates"])

    @patch("scrapers.ssg.requests.Session")
    def test_ssg_live_event_is_filtered_as_noise(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="https://event.ssg.com/eventDetail.ssg?nevntId=1000000021589">detail</a>
        </body></html>
        """
        detail_html = """
        <html>
        <head><meta property="og:title" content="3/13 LG렌탈 라이브" /></head>
        <body>
          <h1>3/13 LG렌탈 라이브</h1>
          <div>2026-03-13 단 하루 이벤트</div>
        </body>
        </html>
        """
        session.get.side_effect = [
            MagicMock(status_code=200, text=hub_html),
            MagicMock(status_code=200, text=detail_html),
        ]

        result = scrape_ssg(timeout_seconds=1, limit=3, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertEqual(1, debug["raw_candidates"])
        self.assertEqual(0, debug["filtered_candidates"])


if __name__ == "__main__":
    unittest.main()
