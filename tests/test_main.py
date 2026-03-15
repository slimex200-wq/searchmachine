import unittest
from unittest.mock import MagicMock, patch

import main


class MainEntryPointTest(unittest.TestCase):
    @patch("main.print_summary")
    @patch("main.print_source_report")
    @patch("main.print_source_header")
    @patch("main.normalize_community_rows")
    @patch("main.scrape_clien")
    @patch("main.scrape_ppomppu")
    @patch("main.scrape_naver_news")
    @patch("main.scrape_oliveyoung")
    @patch("main.scrape_ohouse")
    @patch("main.scrape_coupang")
    @patch("main.scrape_musinsa")
    @patch("main.scrape_ssg")
    @patch("main.scrape_wconcept")
    @patch("main.scrape_29cm")
    @patch("main.PickSaleApiClient")
    @patch("main.SaleDiscoveryEngine")
    @patch("main.get_settings")
    def test_main_skips_kream_official_source(
        self,
        get_settings,
        engine_cls,
        client_cls,
        scrape_29cm,
        scrape_wconcept,
        scrape_ssg,
        scrape_musinsa,
        scrape_coupang,
        scrape_ohouse,
        scrape_oliveyoung,
        scrape_naver_news,
        scrape_ppomppu,
        scrape_clien,
        normalize_community_rows,
        print_source_header,
        print_source_report,
        print_summary,
    ) -> None:
        settings = MagicMock()
        settings.sales_api_url = "https://example.com/sales"
        settings.community_api_url = "https://example.com/community"
        settings.api_key = "secret"
        settings.request_timeout_seconds = 5
        settings.debug_save_html = False
        settings.debug_dir = "scraper_debug"
        settings.naver_client_id = "id"
        settings.naver_client_secret = "secret"
        settings.enable_google_news = False
        settings.enable_community_upload = False
        get_settings.return_value = settings

        engine = MagicMock()
        engine.run_official_source.return_value = MagicMock(stats=MagicMock())
        engine.run_community_source.return_value = MagicMock(stats=MagicMock())
        engine_cls.return_value = engine

        main.main()

        official_sources = [
            call.kwargs["source"]
            for call in engine.run_official_source.call_args_list
        ]
        self.assertNotIn("KreamScraper", official_sources)


if __name__ == "__main__":
    unittest.main()
