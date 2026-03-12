import unittest
from unittest.mock import MagicMock, patch

from app.core.pipeline import SaleDiscoveryEngine


class TestSaleDiscoveryEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.client = MagicMock()
        self.engine = SaleDiscoveryEngine(
            client=self.client,
            timeout_seconds=5,
            debug_save_html=False,
            debug_dir="scraper_debug",
        )

    def test_run_official_source_uploads_grouped_major_events(self) -> None:
        def scrape_fn(**kwargs):
            return {
                "rows": [{"title": "ignored"}],
                "debug": {
                    "requested_url": ["https://example.com/events"],
                    "http_status": ["200"],
                    "html_length": ["1024"],
                    "raw_candidates": 2,
                    "reasons": [],
                },
            }

        normalized_rows = [
            {
                "platform": "musinsa",
                "sale_name": "Mega Sale Week",
                "start_date": "2026-03-01",
                "end_date": "2026-03-10",
                "category": "fashion",
                "link": "https://example.com/events/mega-1",
                "description": "All brands mega sale",
                "source_type": "crawler",
                "status": "published",
            },
            {
                "platform": "musinsa",
                "sale_name": "Mega Sale Festival",
                "start_date": "2026-03-02",
                "end_date": "2026-03-10",
                "category": "fashion",
                "link": "https://example.com/events/mega-2",
                "description": "Category wide event",
                "source_type": "crawler",
                "status": "published",
            },
        ]

        self.client.send_sale.return_value = {"inserted": True}

        with patch("app.core.pipeline.normalize_official_rows", return_value=normalized_rows):
            result = self.engine.run_official_source(
                source="MusinsaScraper",
                scrape_fn=scrape_fn,
                default_category="fashion",
            )

        self.assertEqual(1, result.stats.collected)
        self.assertEqual(2, result.stats.normalized)
        self.assertEqual(2, result.stats.major_count)
        self.assertEqual(1, result.stats.grouped_event_count)
        self.assertEqual(1, result.stats.uploaded)
        self.assertEqual(1, self.client.send_sale.call_count)

        major_pages = [p for p in result.sale_pages if p.sale_tier == "major"]
        self.assertTrue(major_pages)
        self.assertTrue(all(p.event_key for p in major_pages))

    def test_run_official_source_preserves_signal_metadata_in_upload_payload(self) -> None:
        def scrape_fn(**kwargs):
            return {
                "rows": [{"title": "ignored"}],
                "debug": {
                    "requested_url": ["https://example.com/"],
                    "http_status": ["200"],
                    "html_length": ["1024"],
                    "raw_candidates": 1,
                    "reasons": [],
                },
            }

        normalized_rows = [
            {
                "platform": "ssg",
                "sale_name": "Spring Benefit Festival",
                "start_date": "2026-03-01",
                "end_date": "2026-03-05",
                "category": "general",
                "link": "https://example.com/events/spring-benefit",
                "description": "homepage promo card",
                "source_type": "crawler",
                "signal_type": "homepage",
                "confidence_score": 0.7,
                "source_url": "https://example.com/",
                "status": "published",
            }
        ]

        self.client.send_sale.return_value = {"inserted": True}

        with patch("app.core.pipeline.normalize_official_rows", return_value=normalized_rows):
            result = self.engine.run_official_source(
                source="SsgScraper",
                scrape_fn=scrape_fn,
                default_category="general",
            )

        self.assertEqual(1, result.stats.uploaded)
        payload = self.client.send_sale.call_args[0][0]
        self.assertEqual("homepage", payload["signal_type"])
        self.assertEqual(0.7, payload["confidence_score"])
        self.assertEqual("https://example.com/events/spring-benefit", payload["source_url"])

    def test_run_community_source_upload_toggle(self) -> None:
        def scrape_fn(**kwargs):
            return {
                "rows": [
                    {"title": "Mega Sale Event", "content": "all brands", "link": "https://x/event/1"},
                    {"title": "Coupon Notice", "content": "point gift", "link": "https://x/post/2"},
                ],
                "debug": {
                    "requested_url": ["https://x/community"],
                    "http_status": ["200"],
                    "html_length": ["500"],
                    "raw_candidates": 2,
                    "reasons": ["selector_zero"],
                },
            }

        def normalize_fn(raw_rows, source_site):
            self.assertEqual("ppomppu", source_site)
            return raw_rows

        self.client.send_community_post.return_value = {"inserted": True}

        disabled = self.engine.run_community_source(
            source="PpomppuCommunity",
            scrape_fn=scrape_fn,
            normalize_fn=normalize_fn,
            enable_upload=False,
        )
        self.assertEqual(2, disabled.stats.skipped)
        self.assertEqual(0, disabled.stats.uploaded)
        self.assertEqual(0, self.client.send_community_post.call_count)
        self.assertEqual("fallback_anchor", disabled.stats.parser_mode)

        enabled = self.engine.run_community_source(
            source="PpomppuCommunity",
            scrape_fn=scrape_fn,
            normalize_fn=normalize_fn,
            enable_upload=True,
        )
        self.assertEqual(2, enabled.stats.uploaded)
        self.assertEqual(2, self.client.send_community_post.call_count)

    def test_run_community_source_handles_clien_signal_rows(self) -> None:
        def scrape_fn(**kwargs):
            return {
                "rows": [
                    {
                        "title": "SSG 봄 혜택 기획전 최대 20% 할인",
                        "content": "행사 기간 안내",
                        "link": "https://www.clien.net/service/board/jirum/20000001",
                        "signal_type": "community",
                        "confidence_score": 0.35,
                    }
                ],
                "debug": {
                    "requested_url": ["https://www.clien.net/service/board/jirum"],
                    "http_status": ["200"],
                    "html_length": ["500"],
                    "raw_candidates": 1,
                    "reasons": [],
                },
            }

        def normalize_fn(raw_rows, source_site):
            self.assertEqual("clien", source_site)
            return raw_rows

        self.client.send_community_post.return_value = {"inserted": True}

        result = self.engine.run_community_source(
            source="ClienCommunity",
            scrape_fn=scrape_fn,
            normalize_fn=normalize_fn,
            enable_upload=True,
        )

        self.assertEqual(1, result.stats.uploaded)
        self.assertEqual(1, result.stats.filtered_in)

    def test_run_official_source_uploads_minor_as_draft(self) -> None:
        def scrape_fn(**kwargs):
            return {
                "rows": [{"title": "ignored"}],
                "debug": {
                    "requested_url": ["https://example.com/events"],
                    "http_status": ["200"],
                    "html_length": ["1024"],
                    "raw_candidates": 1,
                    "reasons": [],
                },
            }

        normalized_rows = [
            {
                "platform": "musinsa",
                "sale_name": "Weekend Event",
                "start_date": "2026-03-01",
                "end_date": "2026-03-01",
                "category": "fashion",
                "link": "https://example.com/posts/weekend-event",
                "description": "",
                "source_type": "crawler",
                "status": "published",
            }
        ]

        self.client.send_sale.return_value = {"inserted": True}

        with patch("app.core.pipeline.normalize_official_rows", return_value=normalized_rows):
            result = self.engine.run_official_source(
                source="MusinsaScraper",
                scrape_fn=scrape_fn,
                default_category="fashion",
            )

        self.assertEqual(0, result.stats.major_count)
        self.assertEqual(1, result.stats.minor_count)
        self.assertEqual(1, result.stats.grouped_event_count)
        self.assertEqual(1, result.stats.uploaded)

        payload = self.client.send_sale.call_args[0][0]
        self.assertEqual("minor", payload["sale_tier"])
        self.assertEqual("draft", payload["status"])
        self.assertEqual("pending", payload["review_status"])

    def test_run_official_source_marks_no_filtered_sales_when_scraper_candidates_do_not_produce_rows(self) -> None:
        def scrape_fn(**kwargs):
            return {
                "rows": [],
                "debug": {
                    "requested_url": ["https://example.com/events"],
                    "http_status": ["200"],
                    "html_length": ["1024"],
                    "raw_candidates": 6,
                    "filtered_candidates": 0,
                    "reasons": ["filtered_all"],
                },
            }

        result = self.engine.run_official_source(
            source="MusinsaScraper",
            scrape_fn=scrape_fn,
            default_category="fashion",
        )

        self.assertEqual(0, result.stats.collected)
        self.assertEqual(6, result.stats.raw_candidates)
        self.assertEqual(0, result.stats.filtered_candidates)
        self.assertEqual("no_filtered_sales", result.stats.skipped_upload_reason)

    def test_run_official_source_marks_no_normalized_sales_when_rows_fail_normalization(self) -> None:
        def scrape_fn(**kwargs):
            return {
                "rows": [{"title": "bad row"}],
                "debug": {
                    "requested_url": ["https://example.com/events"],
                    "http_status": ["200"],
                    "html_length": ["1024"],
                    "raw_candidates": 6,
                    "filtered_candidates": 1,
                    "reasons": [],
                },
            }

        with patch("app.core.pipeline.normalize_official_rows", return_value=[]):
            result = self.engine.run_official_source(
                source="MusinsaScraper",
                scrape_fn=scrape_fn,
                default_category="fashion",
            )

        self.assertEqual(1, result.stats.collected)
        self.assertEqual(0, result.stats.normalized)
        self.assertEqual("no_normalized_sales", result.stats.skipped_upload_reason)


if __name__ == "__main__":
    unittest.main()
