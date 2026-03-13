import unittest

from bs4 import BeautifulSoup

from scrapers.musinsa import _extract_campaign_image_url, _extract_date_window, _merge_detail_links


class TestMusinsaScraper(unittest.TestCase):
    def test_extract_date_window_from_calendar_style_listing(self) -> None:
        start_date, end_date = _extract_date_window(
            "브랜드데이 캘린더 03.09(월) 03.10(화) 03.11(수) 03.12(목) 03.13(금) 03.14(토) 03.15(일) 03.16(월) 03.17(화) 03.18(수)"
        )

        self.assertEqual("2026-03-09", start_date)
        self.assertEqual("2026-03-18", end_date)

    def test_extract_date_window_rejects_implausible_long_span(self) -> None:
        start_date, end_date = _extract_date_window(
            "부티크 주말특가 01.02 안내 이후 12.30 일정 공지와 26SS 신상 소개"
        )

        self.assertIsNone(start_date)
        self.assertIsNone(end_date)

    def test_extracts_video_poster_from_campaign_container(self) -> None:
        soup = BeautifulSoup(
            """
            <div class="CampaignDetail__CampaignContainer-abc">
                <video poster="/images/hero-poster.jpg" src="/videos/hero.mp4">
                    <source src="/videos/fallback.mp4" />
                </video>
            </div>
            """,
            "html.parser",
        )

        image_url = _extract_campaign_image_url(
            soup,
            "https://www.musinsa.com/campaign/2026beautyfesta1/0",
        )

        self.assertEqual("https://www.musinsa.com/images/hero-poster.jpg", image_url)

    def test_falls_back_to_video_src_when_poster_missing(self) -> None:
        soup = BeautifulSoup(
            """
            <div class="CampaignDetail__CampaignContainer-abc">
                <video src="/videos/hero.mp4"></video>
            </div>
            """,
            "html.parser",
        )

        image_url = _extract_campaign_image_url(
            soup,
            "https://www.musinsa.com/campaign/2026beautyfesta1/0",
        )

        self.assertEqual("https://www.musinsa.com/videos/hero.mp4", image_url)

    def test_allows_cdn_poster_url_for_campaign_image(self) -> None:
        soup = BeautifulSoup(
            """
            <div class="CampaignDetail__CampaignContainer-abc">
                <video poster="https://image.msscdn.net/images/campaign/beauty-poster.jpg"></video>
            </div>
            """,
            "html.parser",
        )

        image_url = _extract_campaign_image_url(
            soup,
            "https://www.musinsa.com/campaign/2026beautyfesta1/0",
        )

        self.assertEqual(
            "https://image.msscdn.net/images/campaign/beauty-poster.jpg",
            image_url,
        )

    def test_falls_back_to_key_visual_image(self) -> None:
        soup = BeautifulSoup(
            """
            <div class="CampaignDetail__CampaignContainer-abc">
                <div class="KeyVisual__Container-abc">
                    <img src="https://image.msscdn.net/campaign_service/images/cpcms/2026/beauty-kv.jpg" />
                </div>
            </div>
            """,
            "html.parser",
        )

        image_url = _extract_campaign_image_url(
            soup,
            "https://www.musinsa.com/campaign/2026beautyfesta1/0",
        )

        self.assertEqual(
            "https://image.msscdn.net/campaign_service/images/cpcms/2026/beauty-kv.jpg",
            image_url,
        )

    def test_falls_back_to_og_image_meta(self) -> None:
        soup = BeautifulSoup(
            """
            <html>
                <head>
                    <meta property="og:image" content="https://image.msscdn.net/campaign_service/images/cpcms/2026/beauty-og.jpg" />
                </head>
            </html>
            """,
            "html.parser",
        )

        image_url = _extract_campaign_image_url(
            soup,
            "https://www.musinsa.com/campaign/2026beautyfesta1/0",
        )

        self.assertEqual(
            "https://image.msscdn.net/campaign_service/images/cpcms/2026/beauty-og.jpg",
            image_url,
        )

    def test_merge_detail_links_keeps_unique_links_and_limit(self) -> None:
        merged = _merge_detail_links(
            [
                "https://www.musinsa.com/campaign/aaa/0",
                "https://www.musinsa.com/campaign/bbb/0",
            ],
            [
                "https://www.musinsa.com/campaign/bbb/0",
                "https://www.musinsa.com/campaign/ccc/0",
                "https://www.musinsa.com/campaign/ddd/0",
            ],
            limit=3,
        )

        self.assertEqual(
            [
                "https://www.musinsa.com/campaign/aaa/0",
                "https://www.musinsa.com/campaign/bbb/0",
                "https://www.musinsa.com/campaign/ccc/0",
            ],
            merged,
        )


if __name__ == "__main__":
    unittest.main()
