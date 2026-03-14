from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json_files(folder: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover
            results.append({"file": path.name, "error": type(exc).__name__})
            continue
        if isinstance(data, dict):
            data["file"] = path.name
            results.append(data)
    return results


def _infer_block_reason(item: dict[str, Any]) -> str:
    title = str(item.get("title", "") or "")
    status_code = item.get("status_code")
    headers = item.get("headers") or {}
    html_length = int(item.get("html_length") or 0)

    if title.lower() == "access denied":
        return "akamai_or_edge_access_denied"
    if title.lower() == "general error page":
        return "site_error_shell"
    if status_code == 403 and str(headers.get("cf-mitigated", "")).lower() == "challenge":
        return "cloudflare_challenge"
    if status_code == 403:
        return "http_403_block"
    if status_code == 404:
        return "http_404_surface"
    if html_length and html_length < 500:
        return "tiny_html"
    return "unknown"


def summarize(folder: Path) -> None:
    items = _load_json_files(folder)
    if not items:
        print(f"[probe_summary] no_json_files folder={folder}")
        return

    print(f"[probe_summary] folder={folder}")
    print(f"[probe_summary] files={len(items)}")

    for item in items:
        mode = str(item.get("mode", ""))
        url = str(item.get("url", ""))
        final_url = str(item.get("final_url", ""))
        status_code = item.get("status_code", "")
        title = str(item.get("title", ""))
        html_length = item.get("html_length", "")
        error = str(item.get("error", ""))
        reason = _infer_block_reason(item)
        print(
            "[probe_summary] item"
            f" file={item.get('file','')}"
            f" mode={mode}"
            f" status={status_code}"
            f" title={title or 'none'}"
            f" html_length={html_length}"
            f" reason={reason}"
            f" error={error or 'none'}"
            f" url={url}"
            f" final_url={final_url or 'none'}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize probe result folders")
    parser.add_argument("folder", help="probe output folder under scraper_debug or absolute path")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        candidate = Path("scraper_debug") / args.folder
        if candidate.exists():
            folder = candidate
    if not folder.exists():
        raise FileNotFoundError(folder)

    summarize(folder)


if __name__ == "__main__":
    main()
