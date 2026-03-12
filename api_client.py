from __future__ import annotations

from typing import Any

import requests


class ApiRequestError(RuntimeError):
    def __init__(self, message: str, url: str, status_code: int | None = None, response_text: str = ""):
        super().__init__(message)
        self.url = url
        self.status_code = status_code
        self.response_text = response_text


class PickSaleApiClient:
    def __init__(self, sales_api_url: str, community_api_url: str, api_key: str, timeout_seconds: int):
        self.sales_api_url = sales_api_url
        self.community_api_url = community_api_url
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "apikey": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def send_sale(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(self.sales_api_url, payload)

    def send_community_post(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(self.community_api_url, payload)

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not url:
            raise ApiRequestError("API URL is missing", url="")

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            body_preview = response.text[:500]
            try:
                data = response.json()
            except ValueError:
                data = {}

            if isinstance(data, dict):
                result = dict(data)
            else:
                result = {"data": data}
            result.setdefault("_status_code", response.status_code)
            result.setdefault("_response_text", body_preview)
            result.setdefault("_url", url)
            return result
        except requests.Timeout as exc:
            raise ApiRequestError(
                f"API timeout ({self.timeout_seconds}s): {url}",
                url=url,
            ) from exc
        except requests.HTTPError as exc:
            detail = ""
            status_code: int | None = None
            try:
                status_code = response.status_code
                detail = response.text[:500]
            except Exception:
                detail = str(exc)
            raise ApiRequestError(
                f"API HTTP error: {status_code} {detail}",
                url=url,
                status_code=status_code,
                response_text=detail,
            ) from exc
        except requests.RequestException as exc:
            raise ApiRequestError(f"API request failed: {exc}", url=url) from exc
