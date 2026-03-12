import unittest
from unittest.mock import MagicMock, patch

import requests

from news.google_news import scrape_google_news


class TestGoogleNewsScraper(unittest.TestCase):
    @patch("news.google_news.requests.Session")
    def test_filters_stale_and_roundup_news(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        response = MagicMock(status_code=200, text="""
        <rss><channel>
            <item>
                <title>무신사 봄 세일 최대 80% 할인 - 연합뉴스</title>
                <link>https://news.example.com/musinsa-spring-sale</link>
                <description>무신사 단독 봄 세일 진행</description>
                <pubDate>Tue, 10 Mar 2026 09:00:00 +0900</pubDate>
            </item>
            <item>
                <title>무신사 블랙프라이데이 판매 기록 - 매체</title>
                <link>https://news.example.com/musinsa-old-sale</link>
                <description>지난 시즌 블랙프라이데이 성과</description>
                <pubDate>Thu, 27 Nov 2025 09:00:00 +0900</pubDate>
            </item>
            <item>
                <title>무신사·에이블리·지그재그 봄 세일 - 매체</title>
                <link>https://news.example.com/roundup-sale</link>
                <description>플랫폼 3사의 할인 행사 비교</description>
                <pubDate>Tue, 10 Mar 2026 09:00:00 +0900</pubDate>
            </item>
        </channel></rss>
        """)
        session.get.return_value = response

        result = scrape_google_news(timeout_seconds=1, limit=5)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("https://news.example.com/musinsa-spring-sale", result["rows"][0]["link"])
        self.assertIn("stale_news:2025-11-27", result["debug"]["reasons"])
        self.assertIn("roundup_noise", result["debug"]["reasons"])

    @patch("news.google_news.requests.Session")
    def test_request_error_keeps_failure_reason(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        session.get.side_effect = requests.ConnectionError("network down")

        result = scrape_google_news(timeout_seconds=1, limit=5)

        self.assertEqual([], result["rows"])
        self.assertEqual("request_error:ConnectionError", result["debug"]["failure_reason"])

    @patch("news.google_news.requests.Session")
    def test_rejects_unrelated_article_without_platform_match(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        response = MagicMock(status_code=200, text="""
        <rss><channel>
            <item>
                <title>여기어때 X 코코호텔, 단독 브랜드위크…최대 47% 할인 - 데일리안</title>
                <link>https://news.example.com/unrelated-sale</link>
                <description><![CDATA[<a href=\"https://news.example.com/unrelated-sale\">여기어때 X 코코호텔, 단독 브랜드위크…최대 47% 할인</a>]]></description>
                <pubDate>Tue, 10 Mar 2026 09:00:00 +0900</pubDate>
            </item>
        </channel></rss>
        """)
        session.get.return_value = response

        result = scrape_google_news(timeout_seconds=1, limit=5)

        self.assertEqual([], result["rows"])
        self.assertIn("platform_unrecognized", result["debug"]["reasons"])

    @patch("news.google_news.requests.Session")
    def test_rejects_google_redirect_article_links(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        response = MagicMock(status_code=200, text="""
        <rss><channel>
            <item>
                <title>SSG닷컴, 패션명품 쓱세일 진행…최대 60% 할인 - 연합뉴스</title>
                <link>https://news.google.com/rss/articles/CBMiExample?oc=5</link>
                <description>SSG닷컴이 패션명품 쓱세일 행사를 진행한다.</description>
                <pubDate>Tue, 10 Mar 2026 09:00:00 +0900</pubDate>
            </item>
        </channel></rss>
        """)
        session.get.return_value = response

        result = scrape_google_news(timeout_seconds=1, limit=5)

        self.assertEqual([], result["rows"])
        self.assertIn("google_redirect_link", result["debug"]["reasons"])

    @patch("news.google_news.requests.Session")
    def test_filters_source_mention_noise_article(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        response = MagicMock(status_code=200, text="""
        <rss><channel>
            <item>
                <title>헤이데이무드, 에센셜 타월 로브 세트 출시 - 매체</title>
                <link>https://news.example.com/29cm-mention-only</link>
                <description>29CM 이구홈위크 쇼케이스와 앙코르 입점회에 참가하며 채널 내 매출이 증가했다.</description>
                <pubDate>Tue, 10 Mar 2026 09:00:00 +0900</pubDate>
            </item>
        </channel></rss>
        """)
        session.get.return_value = response

        result = scrape_google_news(timeout_seconds=1, limit=5)

        self.assertEqual([], result["rows"])
        self.assertIn("source_mention_noise", result["debug"]["reasons"])

    @patch("news.google_news.requests.Session")
    def test_filters_article_noise_keywords(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        response = MagicMock(status_code=200, text="""
        <rss><channel>
            <item>
                <title>[유프로의 AI 픽] 올영세일 추천 총정리 - 매체</title>
                <link>https://news.example.com/oliveyoung-ai-pick</link>
                <description>올리브영 세일과 앱 트래픽을 분석한 기사</description>
                <pubDate>Thu, 12 Mar 2026 09:00:00 +0900</pubDate>
            </item>
        </channel></rss>
        """)
        session.get.return_value = response

        result = scrape_google_news(timeout_seconds=1, limit=5)

        self.assertEqual([], result["rows"])
        self.assertIn("article_noise", result["debug"]["reasons"])

    @patch("news.google_news.requests.Session")
    def test_accepts_kream_sale_keywords(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        response = MagicMock(status_code=200, text="""
        <rss><channel>
            <item>
                <title>크림 봄 세일 최대 30% 할인 - 매체</title>
                <link>https://news.example.com/kream-sale</link>
                <description>크림이 스니커즈와 패션 카테고리 할인 행사를 진행한다.</description>
                <pubDate>Thu, 12 Mar 2026 09:00:00 +0900</pubDate>
            </item>
        </channel></rss>
        """)
        session.get.return_value = response

        result = scrape_google_news(timeout_seconds=1, limit=1)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("kream", result["rows"][0]["platform_hint"])
        self.assertEqual("https://news.example.com/kream-sale", result["rows"][0]["link"])


if __name__ == "__main__":
    unittest.main()
