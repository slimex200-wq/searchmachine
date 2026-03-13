from __future__ import annotations

from api_client import PickSaleApiClient
from app.core import SaleDiscoveryEngine
from community import scrape_clien, scrape_ppomppu
from config import get_settings
from news import scrape_google_news, scrape_naver_news
from pipelines.normalize import normalize_community_rows
from scrapers import (
    scrape_29cm,
    scrape_coupang,
    scrape_musinsa,
    scrape_ohouse,
    scrape_oliveyoung,
    scrape_ssg,
    scrape_wconcept,
)
from utils import print_source_header, print_source_report, print_summary


def main() -> None:
    settings = get_settings()
    client = PickSaleApiClient(
        sales_api_url=settings.sales_api_url,
        community_api_url=settings.community_api_url,
        api_key=settings.api_key,
        timeout_seconds=settings.request_timeout_seconds,
    )

    engine = SaleDiscoveryEngine(
        client=client,
        timeout_seconds=settings.request_timeout_seconds,
        debug_save_html=settings.debug_save_html,
        debug_dir=settings.debug_dir,
    )

    summary = {}

    official_sources = [
        ("29cmScraper", scrape_29cm, "fashion"),
        ("WconceptScraper", lambda **kwargs: scrape_wconcept(**kwargs, enable_browser=True), "fashion"),
        ("SsgScraper", lambda **kwargs: scrape_ssg(**kwargs, enable_browser=True), "general"),
        ("MusinsaScraper", scrape_musinsa, "fashion"),
        ("CoupangScraper", scrape_coupang, "general"),
        ("OhouseScraper", scrape_ohouse, "living"),
        ("OliveyoungScraper", lambda **kwargs: scrape_oliveyoung(**kwargs, enable_browser=True), "beauty"),
        (
            "NaverNewsDiscovery",
            lambda **kwargs: scrape_naver_news(
                **kwargs,
                client_id=settings.naver_client_id,
                client_secret=settings.naver_client_secret,
            ),
            "news",
        ),
    ]
    if settings.enable_google_news:
        official_sources.append(("GoogleNewsDiscovery", scrape_google_news, "news"))

    for name, scrape_fn, default_category in official_sources:
        print_source_header(name)
        result = engine.run_official_source(
            source=name,
            scrape_fn=scrape_fn,
            default_category=default_category,
        )
        result.stats.source = name
        print_source_report(name, result.stats, community_mode=False)
        summary[name] = result.stats

    community_sources = [
        ("PpomppuCommunity", scrape_ppomppu),
        ("ClienCommunity", scrape_clien),
    ]

    for community_name, scrape_fn in community_sources:
        print_source_header(community_name)
        community_result = engine.run_community_source(
            source=community_name,
            scrape_fn=scrape_fn,
            normalize_fn=normalize_community_rows,
            enable_upload=settings.enable_community_upload,
        )
        community_result.stats.source = community_name
        print_source_report(community_name, community_result.stats, community_mode=True)
        summary[community_name] = community_result.stats

    print_summary(summary)


if __name__ == "__main__":
    main()
