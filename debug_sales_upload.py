from __future__ import annotations

from datetime import date, timedelta

from api_client import ApiRequestError, PickSaleApiClient
from config import get_settings


def build_test_payload() -> dict[str, object]:
    start_date = date.today().isoformat()
    end_date = (date.today() + timedelta(days=3)).isoformat()
    return {
        "platform": "test",
        "sale_name": "테스트 세일",
        "title": "테스트 세일",
        "start_date": start_date,
        "end_date": end_date,
        "category": "test",
        "link": "https://example.com/test-sale",
        "description": "debug sales upload probe",
        "source_type": "crawler",
        "status": "published",
        "sale_tier": "major",
        "importance_score": 10,
        "filter_reason": "major_event",
        "review_status": "approved",
        "publish_status": "published",
    }


def main() -> None:
    settings = get_settings()
    client = PickSaleApiClient(
        sales_api_url=settings.sales_api_url,
        community_api_url=settings.community_api_url,
        api_key=settings.api_key,
        timeout_seconds=settings.request_timeout_seconds,
    )

    payload = build_test_payload()
    print(f"[sales-debug] upload_url={client.sales_api_url}")
    print(f"[sales-debug] payload_keys={sorted(payload.keys())}")

    try:
        result = client.send_sale(payload)
        print(f"[sales-debug] response_status={result.get('_status_code', '')}")
        print(f"[sales-debug] response_body={result.get('_response_text', '')}")
        print(f"[sales-debug] result={result}")
    except ApiRequestError as exc:
        print(f"[sales-debug] response_status={exc.status_code or ''}")
        if exc.response_text:
            print(f"[sales-debug] response_body={exc.response_text}")
        print(f"[sales-debug] error={exc}")
        raise


if __name__ == "__main__":
    main()
