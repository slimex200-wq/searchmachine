import unittest
from unittest.mock import MagicMock, patch

from app.core.pipeline import SaleDiscoveryEngine


class TestNewsPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.client = MagicMock()
        self.engine = SaleDiscoveryEngine(
            client=self.client,
            timeout_seconds=5,
            debug_save_html=False,
            debug_dir="scraper_debug",
        )

    def test_news_source_uploads_as_pending_draft(self) -> None:
        def scrape_fn(**kwargs):
            return {
                "rows": [
                    {
                        "title": "무신사 블랙프라이데이 최대 80% 세일",
                        "link": "https://news.example.com/musinsa-blackfriday",
                        "source_url": "https://news.example.com/musinsa-blackfriday",
                        "content": "연중 최대 세일",
                        "context": "연중 최대 세일",
                        "platform_hint": "musinsa",
                        "source_type": "news",
                        "status": "draft",
                        "publish_status": "draft",
                        "review_status": "pending",
                    }
                ],
                "debug": {"requested_url": ["https://openapi.naver.com/v1/search/news.json"], "http_status": ["200"]},
            }

        normalized_rows = [
            {
                "platform": "musinsa",
                "sale_name": "무신사 블랙프라이데이 최대 80% 세일",
                "start_date": "2026-03-09",
                "end_date": "2026-03-09",
                "category": "news",
                "link": "https://news.example.com/musinsa-blackfriday",
                "description": "연중 최대 세일",
                "source_type": "news",
                "status": "draft",
                "publish_status": "draft",
                "review_status": "pending",
            }
        ]

        self.client.send_sale.return_value = {"inserted": True}

        with patch("app.core.pipeline.normalize_official_rows", return_value=normalized_rows):
            result = self.engine.run_official_source(
                source="NaverNewsDiscovery",
                scrape_fn=scrape_fn,
                default_category="news",
            )

        self.assertEqual(1, result.stats.uploaded)
        payload = self.client.send_sale.call_args[0][0]
        self.assertEqual("news", payload["source_type"])
        self.assertEqual("draft", payload["publish_status"])
        self.assertEqual("pending", payload["review_status"])


if __name__ == "__main__":
    unittest.main()
