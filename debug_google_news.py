from __future__ import annotations

from api_client import PickSaleApiClient
from app.core import SaleDiscoveryEngine
from config import get_settings
from news import scrape_google_news
from utils import print_source_header, print_source_report


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

    print_source_header("GoogleNewsDebug")
    result = engine.run_official_source(
        source="GoogleNewsDiscovery",
        scrape_fn=scrape_google_news,
        default_category="news",
    )
    result.stats.source = "GoogleNewsDiscovery"
    print_source_report("GoogleNewsDebug", result.stats, community_mode=False)


if __name__ == "__main__":
    main()
