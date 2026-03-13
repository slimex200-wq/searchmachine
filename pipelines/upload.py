from __future__ import annotations

from datetime import date

from api_client import PickSaleApiClient
from utils import SourceStats, safe_print


def upload_sales_payloads(client: PickSaleApiClient, payloads: list[dict], stats: SourceStats) -> None:
    for payload in payloads:
        if not payload.get("start_date"):
            payload["start_date"] = date.today().isoformat()
        if not payload.get("end_date"):
            payload["end_date"] = payload["start_date"]

        try:
            result = client.send_sale(payload)
            if result.get("inserted"):
                stats.uploaded += 1
            elif result.get("duplicate") or result.get("inserted") is False:
                stats.duplicates += 1
            else:
                stats.errors += 1
        except Exception as exc:
            stats.errors += 1
            safe_print(f"[upload] sale_upload_error={type(exc).__name__}: {exc}")


def upload_community_payloads(client: PickSaleApiClient, payloads: list[dict], stats: SourceStats) -> None:
    for payload in payloads:
        try:
            result = client.send_community_post(payload)
            if result.get("inserted"):
                stats.uploaded += 1
            elif result.get("duplicate") or result.get("inserted") is False:
                stats.duplicates += 1
            else:
                stats.errors += 1
        except Exception as exc:
            stats.errors += 1
            safe_print(f"[upload] community_upload_error={type(exc).__name__}: {exc}")
