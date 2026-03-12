from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# ── 뉴스 세일 자동 승인 기준 ──
# importance_score가 이 값 이상이고 sale_tier가 major이면 자동 승인
AUTO_APPROVE_SCORE_THRESHOLD = 50


def _resolve_publish_status(
    source_type: str,
    sale_tier: str,
    importance_score: int | None,
    publish_status: str | None,
    review_status: str | None,
) -> tuple[str, str]:
    """소스 타입과 점수에 따라 publish_status, review_status를 결정."""
    score = importance_score or 0
    if source_type == "news":
        if sale_tier == "major" and score >= AUTO_APPROVE_SCORE_THRESHOLD:
            return (
                publish_status or "published",
                review_status or "approved",
            )
        return (
            publish_status or "draft",
            review_status or "pending",
        )
    return (
        publish_status or ("published" if sale_tier == "major" else "draft"),
        review_status or ("approved" if sale_tier == "major" else "pending"),
    )


@dataclass
class SalePage:
    platform: str
    title: str
    link: str
    start_date: str | None
    end_date: str | None
    category: str
    description: str
    source: str
    source_type: str
    status: str
    signal_type: str = "detail"
    confidence_score: float = 0.0
    source_url: str | None = None
    pub_date: str | None = None
    image_url: str | None = None
    review_status: str | None = None
    publish_status: str | None = None
    sale_tier: str = "excluded"
    importance_score: int = 0
    filter_reason: str = "unclassified"
    event_key: str | None = None

    def as_sales_payload(self) -> dict:
        start = self.start_date or date.today().isoformat()
        end = self.end_date or start
        pub, rev = _resolve_publish_status(
            self.source_type, self.sale_tier, self.importance_score,
            self.publish_status, self.review_status,
        )
        return {
            "platform": self.platform,
            "sale_name": self.title,
            "title": self.title,
            "start_date": start,
            "end_date": end,
            "category": self.category,
            "link": self.link,
            "description": self.description,
            "source_type": self.source_type,
            "signal_type": self.signal_type,
            "confidence_score": self.confidence_score,
            "source_url": self.source_url or self.link,
            "pub_date": self.pub_date,
            "image_url": self.image_url,
            "status": pub,
            "publish_status": pub,
            "review_status": rev,
            "sale_tier": self.sale_tier,
            "importance_score": self.importance_score,
            "filter_reason": self.filter_reason,
            "event_key": self.event_key,
        }


@dataclass
class GroupedSaleEvent:
    title: str
    platform: str
    start_date: str | None
    end_date: str | None
    source_page_count: int
    grouped_urls: list[str] = field(default_factory=list)
    importance_score: int = 0
    sale_tier: str = "excluded"
    filter_reason: str = ""
    event_key: str | None = None
    category: str = "기획전"
    description: str = ""
    source_type: str = "crawler"
    signal_type: str = "detail"
    confidence_score: float = 0.0
    pub_date: str | None = None
    image_url: str | None = None
    review_status: str | None = None
    publish_status: str | None = None

    def as_sales_payload(self) -> dict:
        start = self.start_date or date.today().isoformat()
        end = self.end_date or start
        pub, rev = _resolve_publish_status(
            self.source_type, self.sale_tier, self.importance_score,
            self.publish_status, self.review_status,
        )
        return {
            "platform": self.platform,
            "sale_name": self.title,
            "title": self.title,
            "start_date": start,
            "end_date": end,
            "category": self.category,
            "link": self.grouped_urls[0] if self.grouped_urls else "",
            "description": self.description or self.title,
            "source_type": self.source_type,
            "signal_type": self.signal_type,
            "confidence_score": self.confidence_score,
            "source_url": self.grouped_urls[0] if self.grouped_urls else "",
            "pub_date": self.pub_date,
            "image_url": self.image_url,
            "status": pub,
            "publish_status": pub,
            "review_status": rev,
            "sale_tier": self.sale_tier,
            "importance_score": self.importance_score,
            "filter_reason": self.filter_reason,
            "event_key": self.event_key,
        }
