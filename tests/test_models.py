import unittest

from app.core.models import GroupedSaleEvent, SalePage


class TestModels(unittest.TestCase):
    def test_sale_page_news_none_importance_stays_draft(self) -> None:
        page = SalePage(
            platform="SSG",
            title="패션명품 쓱세일",
            link="https://example.com/news/ssg-sale",
            start_date="2026-03-13",
            end_date="2026-03-15",
            category="news",
            description="뉴스 기사",
            source="NaverNewsDiscovery",
            source_type="news",
            status="draft",
            sale_tier="major",
            importance_score=None,
        )

        payload = page.as_sales_payload()

        self.assertEqual("draft", payload["publish_status"])
        self.assertEqual("pending", payload["review_status"])

    def test_grouped_sale_event_news_none_importance_stays_draft(self) -> None:
        event = GroupedSaleEvent(
            title="무신사 뷰티 페스타",
            platform="무신사",
            start_date="2026-03-13",
            end_date="2026-03-19",
            source_page_count=2,
            grouped_urls=["https://example.com/news/musinsa-beauty-festa"],
            source_type="news",
            sale_tier="major",
            importance_score=None,
        )

        payload = event.as_sales_payload()

        self.assertEqual("draft", payload["publish_status"])
        self.assertEqual("pending", payload["review_status"])


if __name__ == "__main__":
    unittest.main()
