import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from scrapers.wconcept import scrape_wconcept


class TestWconceptScraper(unittest.TestCase):
    @patch("scrapers.wconcept.requests.Session")
    def test_non_200_seed_urls_do_not_produce_candidates(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        response_403 = MagicMock(status_code=403, text="<html>denied</html>")
        session.get.side_effect = [response_404, response_404, response_403]

        result = scrape_wconcept(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertEqual(0, debug["valid_source_page_count"])
        self.assertEqual(0, debug["filtered_candidates"])
        self.assertEqual("all_seed_urls_failed", debug["failure_reason"])

    @patch("scrapers.wconcept.requests.Session")
    def test_hub_page_collects_event_links_before_detail_parse(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="https://event.wconcept.co.kr/event/100001">W WEEK EVENT</a>
        <a href="https://event.wconcept.co.kr/event/100002">Holiday Campaign</a>
        </body></html>
        """
        detail_html = """
        <html><head><title>W WEEK EVENT</title><meta property="og:image" content="https://cdn.example.com/w-week.jpg" /></head>
        <body><h1>W WEEK EVENT</h1><div>3/9~3/12 season sale</div></body></html>
        """
        hub_resp = MagicMock(status_code=200, text=hub_html)
        detail_resp = MagicMock(status_code=200, text=detail_html)
        session.get.side_effect = [hub_resp, detail_resp, detail_resp]

        result = scrape_wconcept(timeout_seconds=1, limit=2, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual("https://display.wconcept.co.kr/event", debug["hub_url"])
        self.assertEqual(2, debug["event_links_found"])
        self.assertEqual(2, debug["detail_pages_parsed"])
        self.assertEqual(2, debug["filtered_candidates"])
        self.assertEqual(2, len(result["rows"]))
        self.assertEqual("2026-03-09", result["rows"][0]["start_date"])
        self.assertEqual("2026-03-12", result["rows"][0]["end_date"])
        self.assertEqual("https://cdn.example.com/w-week.jpg", result["rows"][0]["image_url"])

    @patch("scrapers.wconcept.requests.Session")
    def test_hub_page_can_extract_event_links_from_embedded_html(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <script>
        window.__DATA__ = {
          "mainBannerList": [
            {"webViewUrl":"https://event.wconcept.co.kr/event/127012"},
            {"webViewUrl":"https://event.wconcept.co.kr/event/128199"}
          ]
        };
        </script>
        </body></html>
        """
        detail_html = """
        <html><head><title>W WEEK EVENT</title></head>
        <body><h1>W WEEK EVENT</h1><div>2026-03-09 ~ 2026-03-12 season sale</div></body></html>
        """
        hub_resp = MagicMock(status_code=200, text=hub_html)
        detail_resp = MagicMock(status_code=200, text=detail_html)
        session.get.side_effect = [hub_resp, detail_resp, detail_resp]

        result = scrape_wconcept(timeout_seconds=1, limit=2, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual(2, debug["event_links_found"])
        self.assertIn("regex_event_link_fallback", debug["reasons"])
        self.assertEqual(2, len(result["rows"]))

    @patch("scrapers.wconcept.datetime")
    @patch("scrapers.wconcept.requests.Session")
    def test_regex_fallback_excludes_inactive_popup_links(self, session_cls, datetime_mock) -> None:
        session = MagicMock()
        session_cls.return_value = session
        datetime_mock.now.return_value = datetime(2026, 3, 9, 12, 0, 0)
        datetime_mock.strptime.side_effect = lambda *args, **kwargs: datetime.strptime(*args, **kwargs)

        hub_html = """
        <html><body><script>
        {
          "bottomPopup":[
            {
              "displayStartDate":"2026-03-01 10:00:00",
              "displayEndDate":"2026-03-12 10:00:00",
              "webViewUrl":"https://event.wconcept.co.kr/event/127012"
            },
            {
              "displayStartDate":"2026-02-01 10:00:00",
              "displayEndDate":"2026-02-05 10:00:00",
              "webViewUrl":"https://event.wconcept.co.kr/event/118357"
            }
          ]
        }
        </script></body></html>
        """
        detail_html = """
        <html><head><title>W WEEK EVENT</title></head>
        <body><h1>W WEEK EVENT</h1><div>2026-03-09 ~ 2026-03-12 season sale</div></body></html>
        """
        hub_resp = MagicMock(status_code=200, text=hub_html)
        detail_resp = MagicMock(status_code=200, text=detail_html)
        session.get.side_effect = [hub_resp, detail_resp]

        result = scrape_wconcept(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual(1, debug["event_links_found"])
        self.assertEqual(["https://display.wconcept.co.kr/event", "https://event.wconcept.co.kr/event/127012"], debug["requested_url"])

    @patch("scrapers.wconcept._collect_playwright_detail_links")
    @patch("scrapers.wconcept.requests.Session")
    def test_playwright_popup_uses_browser_hub_and_detail_links(self, session_cls, collect_links_mock) -> None:
        session = MagicMock()
        session_cls.return_value = session
        collect_links_mock.return_value = (
            ["https://event.wconcept.co.kr/event/128290"],
            ["playwright_modal_click_navigation"],
            "https://display.wconcept.co.kr/rn/women",
        )

        detail_html = """
        <html><head><title>시티브리즈 | W컨셉(W CONCEPT)</title></head>
        <body><h1>시티브리즈 | W컨셉(W CONCEPT)</h1><div>2026-03-09 ~ 2026-03-10 focus day sale</div></body></html>
        """
        session.get.return_value = MagicMock(status_code=200, text=detail_html)

        result = scrape_wconcept(timeout_seconds=1, limit=3, debug_save_html=False, enable_browser=True)
        debug = result["debug"]

        self.assertEqual("playwright_popup", debug["parser_mode"])
        self.assertEqual("https://display.wconcept.co.kr/rn/women", debug["hub_url"])
        self.assertEqual(
            ["https://display.wconcept.co.kr/rn/women", "https://event.wconcept.co.kr/event/128290"],
            debug["requested_url"],
        )
        self.assertEqual(1, debug["filtered_candidates"])
        self.assertEqual(1, len(result["rows"]))

    @patch("scrapers.wconcept.requests.Session")
    def test_non_event_host_detail_links_are_ignored(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="https://www.wconcept.co.kr/event/FirstBuyEvent">첫 구매 이벤트</a>
        <a href="https://event.wconcept.co.kr/event/128290">FOCUS DAY</a>
        </body></html>
        """
        detail_html = """
        <html><head><title>시티브리즈 | W컨셉(W CONCEPT)</title></head>
        <body><h1>시티브리즈 | W컨셉(W CONCEPT)</h1><div>2026-03-09 ~ 2026-03-10 focus day sale</div></body></html>
        """
        session.get.side_effect = [MagicMock(status_code=200, text=hub_html), MagicMock(status_code=200, text=detail_html)]

        result = scrape_wconcept(timeout_seconds=1, limit=3, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual(1, debug["event_links_found"])
        self.assertEqual(
            ["https://display.wconcept.co.kr/event", "https://event.wconcept.co.kr/event/128290"],
            debug["requested_url"],
        )

    @patch("scrapers.wconcept.requests.Session")
    def test_short_term_popup_titles_are_filtered(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="https://event.wconcept.co.kr/event/127235">72H POPUP</a>
        </body></html>
        """
        detail_html = """
        <html><head><title>프론트로우 26SS 72H 팝업 | W컨셉(W CONCEPT)</title></head>
        <body><h1>프론트로우 26SS 72H 팝업 | W컨셉(W CONCEPT)</h1><div>2026-03-09 ~ 2026-03-10 event</div></body></html>
        """
        session.get.side_effect = [MagicMock(status_code=200, text=hub_html), MagicMock(status_code=200, text=detail_html)]

        result = scrape_wconcept(timeout_seconds=1, limit=3, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertEqual(0, debug["filtered_candidates"])
        self.assertEqual("no_major_event_page", debug["failure_reason"])

    @patch("scrapers.wconcept.requests.Session")
    def test_detail_page_uses_hidden_display_dates_for_matching_landing_url(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="https://event.wconcept.co.kr/event/128380?gnbType=Y">SPRING SHOES WEEK</a>
        </body></html>
        """
        detail_html = """
        <html>
          <head><title>SPRING SHOES WEEK | W컨셉(W CONCEPT)</title></head>
          <body>
            <script>
            window.__DATA__ = {
              "banners": [
                {
                  "landingUrl":"https://event.wconcept.co.kr/event/128380",
                  "displayStartDate":"2026-03-09 00:00:00",
                  "displayEndDate":"2026-03-15 23:59:59"
                }
              ]
            };
            </script>
            <h1>SPRING SHOES WEEK | W컨셉(W CONCEPT)</h1>
            <div>season sale</div>
          </body>
        </html>
        """
        session.get.side_effect = [
            MagicMock(status_code=200, text=hub_html),
            MagicMock(status_code=200, text=detail_html),
        ]

        result = scrape_wconcept(timeout_seconds=1, limit=3, debug_save_html=False)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("2026-03-09", result["rows"][0]["start_date"])
        self.assertEqual("2026-03-15", result["rows"][0]["end_date"])

    @patch("scrapers.wconcept.requests.Session")
    def test_detail_page_uses_hidden_iso_array_dates_for_matching_landing_url(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="https://event.wconcept.co.kr/event/128316">SPRING BAG EDIT</a>
        </body></html>
        """
        detail_html = """
        <html>
          <head><title>SPRING BAG EDIT | W컨셉(W CONCEPT)</title></head>
          <body>
            <script>
            const schedule = [
              ["2026-03-09T10:00:00", "2026-03-11T10:00:00", "https://event.wconcept.co.kr/event/128316"]
            ];
            </script>
            <h1>SPRING BAG EDIT | W컨셉(W CONCEPT)</h1>
            <div>season sale</div>
          </body>
        </html>
        """
        session.get.side_effect = [
            MagicMock(status_code=200, text=hub_html),
            MagicMock(status_code=200, text=detail_html),
        ]

        result = scrape_wconcept(timeout_seconds=1, limit=3, debug_save_html=False)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("2026-03-09", result["rows"][0]["start_date"])
        self.assertEqual("2026-03-11", result["rows"][0]["end_date"])

    @patch("scrapers.wconcept.requests.Session")
    def test_detail_page_uses_visible_timed_range_when_hidden_dates_missing(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="https://event.wconcept.co.kr/event/128501">SPRING BAG EVENT</a>
        </body></html>
        """
        detail_html = """
        <html>
          <head><title>SPRING BAG EVENT | W컨셉(W CONCEPT)</title></head>
          <body>
            <h1>SPRING BAG EVENT | W컨셉(W CONCEPT)</h1>
            <div>BEST ITEM 3/9 10AM - 3/11 10AM</div>
          </body>
        </html>
        """
        session.get.side_effect = [
            MagicMock(status_code=200, text=hub_html),
            MagicMock(status_code=200, text=detail_html),
        ]

        result = scrape_wconcept(timeout_seconds=1, limit=3, debug_save_html=False)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("2026-03-09", result["rows"][0]["start_date"])
        self.assertEqual("2026-03-11", result["rows"][0]["end_date"])

    @patch("scrapers.wconcept.requests.Session")
    def test_detail_page_uses_page_dateschedule_window_when_url_match_missing(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html><body>
        <a href="https://event.wconcept.co.kr/event/128002">SPRING BAG EDIT</a>
        </body></html>
        """
        detail_html = """
        <html>
          <head><title>SPRING BAG EDIT | W而⑥뀎(W CONCEPT)</title></head>
          <body>
            <script>
            var dateSchedule = [
              ["2026-03-09T10:00:00", "2026-03-10T10:00:00", "https://event.wconcept.co.kr/event/128501"],
              ["2026-03-10T10:00:00", "2026-03-11T10:00:00", "https://event.wconcept.co.kr/event/128408"],
              ["2026-03-11T10:00:00", "2026-03-12T10:00:00", "https://event.wconcept.co.kr/event/128471"]
            ];
            </script>
            <h1>SPRING BAG EDIT | W而⑥뀎(W CONCEPT)</h1>
            <div>season sale</div>
          </body>
        </html>
        """
        session.get.side_effect = [
            MagicMock(status_code=200, text=hub_html),
            MagicMock(status_code=200, text=detail_html),
        ]

        result = scrape_wconcept(timeout_seconds=1, limit=3, debug_save_html=False)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("2026-03-09", result["rows"][0]["start_date"])
        self.assertEqual("2026-03-12", result["rows"][0]["end_date"])


if __name__ == "__main__":
    unittest.main()
