from __future__ import annotations

from datetime import date, timedelta

from api_client import ApiRequestError, PickSaleApiClient
from config import get_settings


def build_test_payload() -> dict[str, object]:
    start_date = date.today().isoformat()
    end_date = (date.today() + timedelta(days=2)).isoformat()
    return {
        "platform": "test",
        "sale_name": "API upload probe",
        "start_date": start_date,
        "end_date": end_date,
        "category": "test",
        "link": "https://example.com/test-sale-visible-001",
        "description": "manual API upload verification",
        "source_type": "crawler",
        "status": "published",
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
    print(f"[test-api] upload_url={client.sales_api_url}")
    print(f"[test-api] payload={payload}")

    try:
        result = client.send_sale(payload)
        print(f"[test-api] response_status={result.get('_status_code', '')}")
        print(f"[test-api] response_body={result.get('_response_text', '')}")
    except ApiRequestError as exc:
        print(f"[test-api] response_status={exc.status_code or ''}")
        if exc.response_text:
            print(f"[test-api] response_body={exc.response_text}")
        print(f"[test-api] error={exc}")
        raise


if __name__ == "__main__":
    main()
