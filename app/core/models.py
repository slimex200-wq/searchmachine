from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


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
        if self.source_type == "news":
            publish_status = self.publish_status or "draft"
            review_status = self.review_status or "pending"
        else:
            publish_status = self.publish_status or ("published" if self.sale_tier == "major" else "draft")
            review_status = self.review_status or ("approved" if self.sale_tier == "major" else "pending")
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
            "status": publish_status,
            "publish_status": publish_status,
            "review_status": review_status,
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
        if self.source_type == "news":
            publish_status = self.publish_status or "draft"
            review_status = self.review_status or "pending"
        else:
            publish_status = self.publish_status or ("published" if self.sale_tier == "major" else "draft")
            review_status = self.review_status or ("approved" if self.sale_tier == "major" else "pending")
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
            "status": publish_status,
            "publish_status": publish_status,
            "review_status": review_status,
            "sale_tier": self.sale_tier,
            "importance_score": self.importance_score,
            "filter_reason": self.filter_reason,
            "event_key": self.event_key,
        }
