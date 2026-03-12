import unittest

from app.core.models import SalePage
from app.core.sale_grouping import group_sale_events


def _page(
    title: str,
    link: str,
    *,
    platform: str = "musinsa",
    sale_tier: str = "major",
    score: int = 7,
    start_date: str = "2026-03-01",
    end_date: str = "2026-03-10",
    source_type: str = "crawler",
    pub_date: str | None = None,
) -> SalePage:
    return SalePage(
        platform=platform,
        title=title,
        link=link,
        start_date=start_date,
        end_date=end_date,
        category="fashion",
        description=title,
        source="MusinsaScraper",
        source_type=source_type,
        status="published",
        pub_date=pub_date,
        sale_tier=sale_tier,
        importance_score=score,
        filter_reason="test",
    )


class TestSaleGrouping(unittest.TestCase):
    def test_groups_related_major_pages_and_assigns_event_key(self) -> None:
        pages = [
            _page("Mega Sale Week", "https://example.com/events/mega-1", score=8),
            _page("Mega Sale Festival", "https://example.com/events/mega-2", score=7),
            _page(
                "Denim Drop",
                "https://example.com/posts/denim",
                score=6,
                start_date="2026-04-01",
                end_date="2026-04-03",
            ),
            _page("Mega Sale Week", "https://example.com/events/minor", sale_tier="minor", score=3),
        ]

        grouped, pages_with_key = group_sale_events(pages)

        self.assertEqual(2, len(grouped))
        grouped_sizes = sorted(ev.source_page_count for ev in grouped)
        self.assertEqual([1, 3], grouped_sizes)

        self.assertEqual(4, len(pages_with_key))
        self.assertTrue(all(p.event_key for p in pages_with_key))

    def test_news_group_prefers_latest_article_as_representative(self) -> None:
        pages = [
            _page(
                "무신사 뷰티 페스타",
                "https://news.example.com/older",
                sale_tier="minor",
                score=2,
                source_type="news",
                pub_date="2026-03-09",
                start_date="2026-03-10",
                end_date="2026-03-19",
            ),
            _page(
                "무신사 뷰티 페스타 할인 행사",
                "https://news.example.com/newer",
                sale_tier="minor",
                score=2,
                source_type="news",
                pub_date="2026-03-10",
                start_date="2026-03-10",
                end_date="2026-03-19",
            ),
        ]

        grouped, _ = group_sale_events(pages)

        self.assertEqual(1, len(grouped))
        self.assertEqual("https://news.example.com/newer", grouped[0].grouped_urls[0])
        self.assertEqual("2026-03-10", grouped[0].pub_date)

    def test_platform_common_tokens_do_not_merge_distinct_wconcept_events(self) -> None:
        pages = [
            _page(
                "SPRING SHOES WEEK | W컨셉(W CONCEPT)",
                "https://event.wconcept.co.kr/event/128337",
                platform="WCONCEPT",
                start_date="2026-03-09",
                end_date="2026-03-15",
            ),
            _page(
                "스프링백 모아보기 | W컨셉(W CONCEPT)",
                "https://event.wconcept.co.kr/event/128316",
                platform="WCONCEPT",
                start_date="2026-03-09",
                end_date="2026-03-15",
            ),
            _page(
                "스프링 디지털페어 | W컨셉(W CONCEPT)",
                "https://event.wconcept.co.kr/event/128336",
                platform="WCONCEPT",
                start_date="2026-03-09",
                end_date="2026-03-15",
            ),
        ]

        grouped, _ = group_sale_events(pages)

        self.assertEqual(3, len(grouped))

    def test_ssg_distinct_event_ids_do_not_merge_on_shared_detail_path(self) -> None:
        pages = [
            _page(
                "패션명품 쓱세일",
                "https://event.ssg.com/eventDetail.ssg?nevntId=1000000021683",
                platform="SSG",
                start_date="2026-03-09",
                end_date="2026-03-15",
            ),
            _page(
                "쓱7클럽 전용쿠폰 현대카드",
                "https://event.ssg.com/eventDetail.ssg?nevntId=1000000021588&domainSiteNo=6005",
                platform="SSG",
                start_date="2026-03-01",
                end_date="2026-03-31",
            ),
        ]

        grouped, _ = group_sale_events(pages)

        self.assertEqual(2, len(grouped))


if __name__ == "__main__":
    unittest.main()
