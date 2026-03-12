import unittest

from app.core.sale_classifier import classify_sale_importance


class TestSaleClassifier(unittest.TestCase):
    def test_major_when_score_is_four_or_more(self) -> None:
        tier, score, reason = classify_sale_importance(
            title="Spring Sale Category Event",
            description="All brands campaign",
            link="https://example.com/event/spring",
            start_date=None,
            end_date=None,
        )
        self.assertEqual("major", tier)
        self.assertGreaterEqual(score, 4)
        self.assertIn("official_event_url", reason)

    def test_minor_at_boundary_score_one(self) -> None:
        tier, score, reason = classify_sale_importance(
            title="Weekend Event",
            description="",
            link="https://example.com/products/123",
            start_date=None,
            end_date=None,
        )
        self.assertEqual("minor", tier)
        self.assertEqual(3, score)
        self.assertIn("medium_positive:event", reason)

    def test_excluded_below_minor_threshold(self) -> None:
        tier, score, reason = classify_sale_importance(
            title="Coupon Point Gift Pack",
            description="",
            link="https://example.com/deals/1",
            start_date=None,
            end_date=None,
        )
        self.assertEqual("excluded", tier)
        self.assertLess(score, 1)
        self.assertIn("medium_negative:coupon", reason)

    def test_detail_signal_scores_higher_than_homepage_signal(self) -> None:
        detail_tier, detail_score, detail_reason = classify_sale_importance(
            title="Spring Sale Event",
            description="All brands campaign",
            link="https://example.com/event/spring",
            start_date="2026-03-01",
            end_date="2026-03-05",
            signal_type="detail",
            confidence_score=0.9,
        )
        home_tier, home_score, home_reason = classify_sale_importance(
            title="Spring Sale Event",
            description="All brands campaign",
            link="https://example.com/home",
            start_date="2026-03-01",
            end_date="2026-03-05",
            signal_type="homepage",
            confidence_score=0.6,
        )

        self.assertEqual("major", detail_tier)
        self.assertGreater(detail_score, home_score)
        self.assertIn("signal_type:detail", detail_reason)
        self.assertIn("signal_type:homepage", home_reason)

    def test_platform_specific_event_name_keeps_news_article_uploadable(self) -> None:
        tier, score, reason = classify_sale_importance(
            title="SSG닷컴, 패션명품 쓱세일 진행…최대 60% 할인",
            description="오는 15일까지 봄·여름 상품 할인 행사를 진행한다.",
            link="https://www.news1.kr/amp/industry/distribution/6094187",
            start_date="2026-03-09",
            end_date="2026-03-15",
            signal_type="news",
            confidence_score=0.35,
        )

        self.assertIn(tier, {"minor", "major"})
        self.assertGreaterEqual(score, 1)
        self.assertIn("strong_positive:쓱세일", reason)


if __name__ == "__main__":
    unittest.main()
