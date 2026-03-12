import unittest
from importlib import import_module
from unittest.mock import MagicMock, patch

from scrapers import scrape_29cm
from utils import parse_date_range_to_iso

scraper_29cm_module = import_module("scrapers.29cm")


class Test29cmScraper(unittest.TestCase):
    def test_placeholder(self) -> None:
        self.assertTrue(callable(scrape_29cm))

    @patch.object(scraper_29cm_module.requests, "Session")
    def test_non_200_seed_urls_do_not_produce_candidates(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        response_404 = MagicMock(status_code=404, text="<html>not found</html>")
        session.get.side_effect = [response_404, response_404, response_404, response_404]

        result = scrape_29cm(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual([], result["rows"])
        self.assertEqual(0, debug["valid_source_page_count"])
        self.assertEqual(0, debug["raw_candidates"])
        self.assertEqual(0, debug["detail_links_found"])
        self.assertEqual("all_seed_urls_failed", debug["failure_reason"])

    @patch.object(scraper_29cm_module.requests, "Session")
    def test_next_data_can_supply_detail_links_and_parse_image_and_date(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        hub_html = """
        <html>
        <head><script id="__NEXT_DATA__" type="application/json">{"buildId":"build-123","page":"/event"}</script></head>
        <body><ul class="grid"></ul></body>
        </html>
        """
        next_json = """
        {
          "pageProps": {
            "items": [
              {"landingUrl": "/store/event/777"},
              {"url": "https://www.29cm.co.kr/content/promotion/benefit-guide"}
            ]
          }
        }
        """
        empty_hub = "<html><body></body></html>"
        detail_html = """
        <html>
          <head>
            <title>29CM Spring Event</title>
            <meta property="og:image" content="https://cdn.example.com/29-event.jpg" />
          </head>
          <body>
            <h1>29CM Spring Event</h1>
            <div>2026-03-09 ~ 2026-03-15 promotion</div>
          </body>
        </html>
        """

        def fake_get(url, timeout=1):
            mapping = {
                "https://www.29cm.co.kr/": MagicMock(status_code=200, text=hub_html),
                "https://www.29cm.co.kr/_next/data/build-123/index.json": MagicMock(status_code=200, text='{"pageProps":{}}'),
                "https://www.29cm.co.kr/event": MagicMock(status_code=200, text=hub_html),
                "https://www.29cm.co.kr/_next/data/build-123/event.json": MagicMock(status_code=200, text=next_json),
                "https://www.29cm.co.kr/store/showcase": MagicMock(status_code=200, text=empty_hub),
                "https://www.29cm.co.kr/store/exhibition": MagicMock(status_code=200, text=empty_hub),
                "https://www.29cm.co.kr/store/event/777": MagicMock(status_code=200, text=detail_html),
            }
            fallback_json = MagicMock(status_code=200, text='{"pageProps":{}}')
            return mapping.get(url, fallback_json)

        session.get.side_effect = fake_get

        result = scrape_29cm(timeout_seconds=1, limit=3, debug_save_html=False)
        debug = result["debug"]
        row = result["rows"][0]

        self.assertEqual(1, debug["detail_links_found"])
        self.assertIn("next_data_link_extract", debug["reasons"])
        self.assertEqual("2026-03-09", row["start_date"])
        self.assertEqual("2026-03-15", row["end_date"])
        self.assertEqual("https://cdn.example.com/29-event.jpg", row["image_url"])
        self.assertEqual("https://www.29cm.co.kr/store/event/777", row["link"])

    @patch.object(scraper_29cm_module, "_collect_playwright_detail_links")
    @patch.object(scraper_29cm_module.requests, "Session")
    def test_playwright_visible_links_use_browser_links(self, session_cls, collect_links_mock) -> None:
        session = MagicMock()
        session_cls.return_value = session
        collect_links_mock.return_value = (
            ["https://www.29cm.co.kr/store/event/12345"],
            ["playwright_visible_link_extract"],
            "https://www.29cm.co.kr/event",
        )

        empty_hub = "<html><body></body></html>"
        detail_html = """
        <html><head><title>Special Order Event</title></head>
        <body><h1>Special Order Event</h1><div>2026-03-09 ~ 2026-03-12 promotion</div></body></html>
        """
        def fake_get(url, timeout=1):
            mapping = {
                "https://www.29cm.co.kr/": MagicMock(status_code=200, text=empty_hub),
                "https://www.29cm.co.kr/event": MagicMock(status_code=200, text=empty_hub),
                "https://www.29cm.co.kr/store/showcase": MagicMock(status_code=200, text=empty_hub),
                "https://www.29cm.co.kr/store/exhibition": MagicMock(status_code=200, text=empty_hub),
                "https://www.29cm.co.kr/store/event/12345": MagicMock(status_code=200, text=detail_html),
            }
            return mapping.get(url, MagicMock(status_code=200, text='{"pageProps":{}}'))

        session.get.side_effect = fake_get

        result = scrape_29cm(timeout_seconds=1, limit=3, debug_save_html=False, enable_browser=True)
        debug = result["debug"]

        self.assertEqual("playwright_visible_links", debug["parser_mode"])
        self.assertIn("https://www.29cm.co.kr/event", debug["requested_url"])
        self.assertIn("https://www.29cm.co.kr/event", debug["requested_url"])
        self.assertIn("https://www.29cm.co.kr/store/event/12345", debug["requested_url"])
        self.assertEqual(1, debug["detail_links_found"])
        self.assertEqual(1, len(result["rows"]))

    def test_benefit_guide_link_is_excluded(self) -> None:
        self.assertFalse(
            scraper_29cm_module._is_allowed_29cm_link("https://www.29cm.co.kr/content/promotion/benefit-guide")
        )

    def test_brand_news_link_is_allowed(self) -> None:
        self.assertTrue(
            scraper_29cm_module._is_allowed_29cm_link("https://www.29cm.co.kr/content/brand-news/62881")
        )

    def test_title_suffix_is_removed(self) -> None:
        self.assertEqual(
            "봄과 함께 온 신상",
            scraper_29cm_module._clean_29cm_title("봄과 함께 온 신상 - 감도 깊은 취향 셀렉트샵 29CM"),
        )

    def test_collection_link_is_allowed(self) -> None:
        self.assertTrue(
            scraper_29cm_module._is_allowed_29cm_link("https://www.29cm.co.kr/content/collection/19447")
        )

    def test_focus_link_is_excluded(self) -> None:
        self.assertFalse(
            scraper_29cm_module._is_allowed_29cm_link("https://www.29cm.co.kr/content/focus/2026/03/09/umer")
        )

    def test_two_digit_year_range_is_parsed(self) -> None:
        start_date, end_date = parse_date_range_to_iso("26. 3. 9. - 3. 23.")
        self.assertEqual("2026-03-09", start_date)
        self.assertEqual("2026-03-23", end_date)

    def test_collection_next_data_candidate_extracts_dates(self) -> None:
        payload = {
            "props": {
                "pageProps": {
                    "dehydratedState": {
                        "queries": [
                            {
                                "state": {
                                    "data": {
                                        "title": "마음을 전하는 센스 있는 선택",
                                        "description": "화이트데이부터 새학기까지 선물세트 큐레이션",
                                        "coverImageUrl": "https://img.29cm.co.kr/item/test.jpg",
                                        "displayStartAt": "2026-03-09T10:00:00.000+09:00",
                                        "displayEndAt": "2026-03-15T23:59:00.000+09:00",
                                    }
                                }
                            },
                            {
                                "state": {
                                    "data": {
                                        "couponName": "뷰티 선물세트 셀렉션 15% 쿠폰",
                                        "couponIssueStartAt": "2026-03-09T10:00:00+09:00",
                                        "couponIssueEndAt": "2026-03-15T23:59:59.999999+09:00",
                                    }
                                }
                            },
                        ]
                    }
                }
            }
        }

        row = scraper_29cm_module._extract_collection_candidate_from_next_data(
            payload,
            "https://www.29cm.co.kr/content/collection/19447",
        )

        self.assertIsNotNone(row)
        self.assertEqual("마음을 전하는 센스 있는 선택", row["title"])
        self.assertEqual("2026-03-09", row["start_date"])
        self.assertEqual("2026-03-15", row["end_date"])

    def test_brand_news_next_data_candidate_extracts_dates(self) -> None:
        payload = {
            "props": {
                "pageProps": {
                    "dehydratedState": {
                        "queries": [
                            {
                                "state": {
                                    "data": {
                                        "id": 62346,
                                        "title": "화이트데이 마음 전하기",
                                        "description": "정샘물이 준비한 화이트데이 단독 구성.",
                                        "displayStartAt": "2026-03-09T10:00:00.000+09:00",
                                        "displayEndAt": "2026-03-15T23:59:00.000+09:00",
                                        "promotionRelease": "NONE",
                                        "promotionDiscount": "DISCOUNT",
                                        "coverImage": {"url": "https://img.29cm.co.kr/cms/test.jpg"},
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }

        row = scraper_29cm_module._extract_brand_news_candidate_from_next_data(
            payload,
            "https://www.29cm.co.kr/content/brand-news/62346",
        )

        self.assertIsNotNone(row)
        self.assertEqual("화이트데이 마음 전하기", row["title"])
        self.assertEqual("2026-03-09", row["start_date"])
        self.assertEqual("2026-03-15", row["end_date"])

    def test_brand_event_title_can_be_extracted_from_body(self) -> None:
        title = scraper_29cm_module._extract_brand_event_title_from_body(
            "감도 깊은 취향 셀렉트샵 29CM NEW PRODUCT 10+12% 디렉터가 직접 입고 소개해요 오디에스 "
            "오디에스 디렉터의 SNS 속 포착된 26년 봄 신상을 소개해요. 2026. 3. 10. - 3. 16. 쿠폰 혜택"
        )
        self.assertEqual("디렉터가 직접 입고 소개해요 오디에스 오디에스 디렉터의 SNS 속 포착된", title)

    def test_marketing_title_is_shortened_for_brand_event(self) -> None:
        self.assertEqual(
            "인플루언서 왕밤빵이 제안하는 봄 스타일 사비에",
            scraper_29cm_module._shorten_29cm_title(
                "인플루언서 왕밤빵이 제안하는 봄 스타일 사비에 유튜버 왕밤빵이 제안하는 사비에의 신상품을 만나보세요."
            ),
        )

    def test_brand_event_can_replace_overlong_meta_title(self) -> None:
        html = """
        <html>
          <head>
            <title>인플루언서 왕밤빵이 제안하는 봄 스타일 사비에 유튜버 왕밤빵이 제안하는 사비에의 신상품을 만나보세요.</title>
          </head>
          <body>
            감도 깊은 취향 셀렉트샵 29CM NEW PRODUCT 10%
            인플루언서 왕밤빵이 제안하는 봄 스타일 사비에 유튜버 왕밤빵이 제안하는 사비에의 신상품을 만나보세요.
            2026. 3. 12. - 3. 18.
          </body>
        </html>
        """
        soup = scraper_29cm_module.BeautifulSoup(html, "html.parser")

        row = scraper_29cm_module._extract_candidate(
            soup,
            "https://www.29cm.co.kr/content/brand-event/2026/03/12/savier?cache=true",
            html,
        )

        self.assertIsNotNone(row)
        self.assertEqual("인플루언서 왕밤빵이 제안하는 봄 스타일 사비에", row["title"])

    @patch.object(scraper_29cm_module.requests, "Session")
    def test_collects_links_across_multiple_hubs(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        home_html = """
        <html><body>
        <a href="/store/showcase/spring-curation">Showcase</a>
        </body></html>
        """
        event_html = """
        <html><body>
        <a href="/store/event/777">Event 777</a>
        </body></html>
        """
        empty_hub = "<html><body></body></html>"
        detail_one = """
        <html><head><title>Spring Showcase</title></head>
        <body><h1>Spring Showcase</h1><div>2026-03-09 ~ 2026-03-12 promotion</div></body></html>
        """
        detail_two = """
        <html><head><title>Event 777</title></head>
        <body><h1>Event 777</h1><div>2026-03-11 ~ 2026-03-15 event</div></body></html>
        """

        def fake_get(url, timeout=1):
            mapping = {
                "https://www.29cm.co.kr/": MagicMock(status_code=200, text=home_html),
                "https://www.29cm.co.kr/event": MagicMock(status_code=200, text=event_html),
                "https://www.29cm.co.kr/store/showcase": MagicMock(status_code=200, text=empty_hub),
                "https://www.29cm.co.kr/store/exhibition": MagicMock(status_code=200, text=empty_hub),
                "https://www.29cm.co.kr/store/showcase/spring-curation": MagicMock(status_code=200, text=detail_one),
                "https://www.29cm.co.kr/store/event/777": MagicMock(status_code=200, text=detail_two),
            }
            return mapping.get(url, MagicMock(status_code=200, text='{"pageProps":{}}'))

        session.get.side_effect = fake_get

        result = scrape_29cm(timeout_seconds=1, limit=5, debug_save_html=False)
        debug = result["debug"]

        self.assertEqual(2, debug["detail_links_found"])
        self.assertEqual(2, debug["detail_pages_parsed"])
        self.assertEqual(2, len(result["rows"]))
        self.assertIn("https://www.29cm.co.kr/store/showcase/spring-curation", debug["requested_url"])
        self.assertIn("https://www.29cm.co.kr/store/event/777", debug["requested_url"])

    def test_sale_signal_detects_tilde_plus_percent_pattern(self) -> None:
        self.assertTrue(scraper_29cm_module._looks_like_sale_event("NEW PRODUCT ~55+14% coupon"))

    def test_brand_event_candidate_can_use_fallback_title_and_dates(self) -> None:
        html = """
        <html>
          <head><title>감도 깊은 취향 셀렉트샵 29CM</title></head>
          <body>
            감도 깊은 취향 셀렉트샵 29CM NEW PRODUCT ~55+14%
            따라입고 싶은 브랜드 온앤온
            따라하고 싶은 셀렙들이 선택한 온앤온의 상품을 단독 혜택으로 소개해요.
            2026. 3. 9. - 3. 15. 쿠폰 혜택
          </body>
        </html>
        """
        soup = scraper_29cm_module.BeautifulSoup(html, "html.parser")

        row = scraper_29cm_module._extract_candidate(
            soup,
            "https://www.29cm.co.kr/content/brand-event/2026/03/09/onnon?cache=true",
            html,
        )

        self.assertIsNotNone(row)
        self.assertEqual("2026-03-09", row["start_date"])
        self.assertEqual("2026-03-15", row["end_date"])


if __name__ == "__main__":
    unittest.main()
