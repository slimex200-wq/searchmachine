import unittest
from unittest.mock import MagicMock, patch

import requests

from news.naver_news import scrape_naver_news
from pipelines.normalize import normalize_official_rows


class TestNaverNewsScraper(unittest.TestCase):
    @patch("news.naver_news.requests.Session")
    def test_missing_credentials_skips_cleanly(self, session_cls) -> None:
        result = scrape_naver_news(timeout_seconds=1, limit=5, client_id="", client_secret="")
        self.assertEqual([], result["rows"])
        self.assertEqual("missing_naver_credentials", result["debug"]["failure_reason"])
        session_cls.assert_not_called()

    @patch("news.naver_news.requests.Session")
    def test_filters_news_to_major_sale_candidates(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response = MagicMock(status_code=200, text='{"items":[]}')
        response.json.return_value = {
            "total": 2,
            "items": [
                {
                    "title": "<b>무신사</b> 블랙프라이데이 최대 80% 세일",
                    "originallink": "https://news.example.com/musinsa-sale",
                    "description": "연중 최대 세일 진행",
                    "pubDate": "Mon, 09 Mar 2026 09:00:00 +0900",
                },
                {
                    "title": "무신사 카드 할인 쿠폰 이벤트",
                    "originallink": "https://news.example.com/musinsa-coupon",
                    "description": "카드 할인과 쿠폰 지급",
                    "pubDate": "Mon, 09 Mar 2026 09:00:00 +0900",
                },
            ],
        }
        session.get.return_value = response

        result = scrape_naver_news(
            timeout_seconds=1,
            limit=1,
            client_id="id",
            client_secret="secret",
        )

        self.assertEqual(1, len(result["rows"]))
        row = result["rows"][0]
        self.assertEqual("news", row["source_type"])
        self.assertEqual("draft", row["publish_status"])
        self.assertEqual("pending", row["review_status"])
        self.assertEqual("musinsa", row["platform_hint"])
        self.assertEqual(1, result["debug"]["filtered_candidates"])

    @patch("news.naver_news.requests.Session")
    def test_auth_failure_stops_further_queries(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        session.get.return_value = MagicMock(status_code=401, text='{"errorMessage":"auth"}')

        result = scrape_naver_news(timeout_seconds=1, limit=5, client_id="id", client_secret="secret")

        self.assertEqual([], result["rows"])
        self.assertEqual("naver_api_auth_failed", result["debug"]["failure_reason"])
        self.assertEqual(1, session.get.call_count)

    @patch("news.naver_news.requests.Session")
    def test_rate_limit_stops_further_queries(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        session.get.return_value = MagicMock(status_code=429, text='{"errorMessage":"rate"}')

        result = scrape_naver_news(timeout_seconds=1, limit=5, client_id="id", client_secret="secret")

        self.assertEqual([], result["rows"])
        self.assertEqual("naver_api_rate_limited", result["debug"]["failure_reason"])
        self.assertEqual(1, session.get.call_count)

    @patch("news.naver_news.requests.Session")
    def test_request_error_keeps_exception_detail(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session
        session.get.side_effect = requests.ConnectionError("dns failure")

        result = scrape_naver_news(timeout_seconds=1, limit=5, client_id="id", client_secret="secret")

        self.assertEqual([], result["rows"])
        self.assertEqual("request_error:ConnectionError", result["debug"]["failure_reason"])
        self.assertEqual("dns failure", result["debug"]["error_detail"])

    @patch("news.naver_news.requests.Session")
    def test_filters_out_stale_and_roundup_news(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response = MagicMock(status_code=200, text='{"items":[]}')
        response.json.return_value = {
            "total": 3,
            "items": [
                {
                    "title": "<b>무신사</b> 봄 세일 최대 80% 할인",
                    "originallink": "https://news.example.com/musinsa-spring-sale",
                    "description": "오늘 시작한 무신사 단독 세일",
                    "pubDate": "Mon, 09 Mar 2026 09:00:00 +0900",
                },
                {
                    "title": "무신사 블랙프라이데이 판매 기록",
                    "originallink": "https://news.example.com/musinsa-old-sale",
                    "description": "지난 시즌 블랙프라이데이 성과",
                    "pubDate": "Thu, 27 Nov 2025 09:00:00 +0900",
                },
                {
                    "title": "무신사·에이블리·지그재그 봄 세일",
                    "originallink": "https://news.example.com/roundup-sale",
                    "description": "플랫폼 3사의 할인 행사 비교",
                    "pubDate": "Mon, 09 Mar 2026 09:00:00 +0900",
                },
            ],
        }
        session.get.return_value = response

        result = scrape_naver_news(
            timeout_seconds=1,
            limit=5,
            client_id="id",
            client_secret="secret",
        )

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("https://news.example.com/musinsa-spring-sale", result["rows"][0]["link"])
        self.assertIn("stale_news:2025-11-27", result["debug"]["reasons"])
        self.assertTrue(
            "multi_platform_roundup" in result["debug"]["reasons"]
            or "roundup_noise" in result["debug"]["reasons"]
        )

    @patch("news.naver_news.requests.Session")
    def test_filters_out_brief_noise_article(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response = MagicMock(status_code=200, text='{"items":[]}')
        response.json.return_value = {
            "total": 1,
            "items": [
                {
                    "title": "[브리프]아모레퍼시픽 LF 코스맥스 에이피알 外",
                    "originallink": "https://news.example.com/brief-roundup",
                    "description": "무신사 뷰티 페스타와 여러 업체 소식을 묶은 기사",
                    "pubDate": "Mon, 09 Mar 2026 09:00:00 +0900",
                }
            ],
        }
        session.get.return_value = response

        result = scrape_naver_news(
            timeout_seconds=1,
            limit=5,
            client_id="id",
            client_secret="secret",
        )

        self.assertEqual([], result["rows"])
        self.assertIn("brief_noise", result["debug"]["reasons"])

    @patch("news.naver_news.requests.Session")
    def test_filters_out_result_and_roundup_noise(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response = MagicMock(status_code=200, text='{"items":[]}')
        response.json.return_value = {
            "total": 2,
            "items": [
                {
                    "title": "29CM 이구 홈 위크 열흘간 홈·인테리어 거래액 3배↑",
                    "originallink": "https://news.example.com/29cm-result",
                    "description": "거래액이 급증하며 역대 최대 성과를 기록",
                    "pubDate": "Mon, 09 Mar 2026 09:00:00 +0900",
                },
                {
                    "title": "봄 세일 시작…패션 플랫폼 최대 95% 할인 경쟁",
                    "originallink": "https://news.example.com/platform-roundup",
                    "description": "플랫폼 업계 할인 경쟁",
                    "pubDate": "Mon, 09 Mar 2026 09:00:00 +0900",
                },
            ],
        }
        session.get.return_value = response

        result = scrape_naver_news(
            timeout_seconds=1,
            limit=5,
            client_id="id",
            client_secret="secret",
        )

        self.assertEqual([], result["rows"])
        self.assertTrue(
            "result_noise" in result["debug"]["reasons"]
            or "roundup_title_noise" in result["debug"]["reasons"]
        )

    @patch("news.naver_news.requests.Session")
    def test_filters_out_context_noise_even_with_high_signal_phrase(self, session_cls) -> None:
        session = MagicMock()
        session_cls.return_value = session

        response = MagicMock(status_code=200, text='{"items":[]}')
        response.json.return_value = {
            "total": 1,
            "items": [
                {
                    "title": "내 집 고쳐 쓰는 불황의 역설…프리미엄 리빙 시장 활활",
                    "originallink": "https://news.example.com/living-roundup",
                    "description": "오는 15일까지 상반기 최대 규모 리빙 행사와 29CM 오프라인 경쟁력 강화",
                    "pubDate": "Mon, 09 Mar 2026 09:00:00 +0900",
                },
            ],
        }
        session.get.return_value = response

        result = scrape_naver_news(
            timeout_seconds=1,
            limit=5,
            client_id="id",
            client_secret="secret",
        )

        self.assertEqual([], result["rows"])
        self.assertIn("context_noise", result["debug"]["reasons"])

    def test_news_dates_prefer_event_period_over_pub_date(self) -> None:
        normalized = normalize_official_rows(
            [
                {
                    "title": "무신사 뷰티 페스타",
                    "link": "https://news.example.com/musinsa-beauty-festa",
                    "source_url": "https://news.example.com/musinsa-beauty-festa",
                    "description": "무신사 뷰티가 19일까지 상반기 최대 할인 행사를 진행한다.",
                    "content": "무신사 뷰티가 19일까지 상반기 최대 할인 행사를 진행한다.",
                    "context": "무신사 뷰티가 19일까지 상반기 최대 할인 행사를 진행한다.",
                    "date_text": "무신사 뷰티 페스타 무신사 뷰티가 19일까지 상반기 최대 할인 행사를 진행한다.",
                    "start_date": None,
                    "end_date": None,
                    "platform_hint": "musinsa",
                    "category_hint": "news",
                    "source_type": "news",
                    "pub_date": "2026-03-10",
                }
            ],
            "news",
        )
        self.assertEqual(1, len(normalized))
        self.assertEqual("2026-03-10", normalized[0]["start_date"])
        self.assertEqual("2026-03-19", normalized[0]["end_date"])


if __name__ == "__main__":
    unittest.main()
