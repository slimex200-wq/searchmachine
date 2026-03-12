from __future__ import annotations

from dataclasses import dataclass
import sys


@dataclass
class SourceStats:
    source: str = ""
    collected: int = 0
    normalized: int = 0
    uploadable_count: int = 0
    uploaded: int = 0
    duplicates: int = 0
    errors: int = 0
    skipped: int = 0
    filtered_in: int = 0
    major_count: int = 0
    minor_count: int = 0
    excluded_count: int = 0
    grouped_event_count: int = 0
    requested_url: str = ""
    hub_url: str = ""
    http_status: str = ""
    hub_http_status: str = ""
    html_length: str = ""
    hub_html_length: str = ""
    valid_source_page_count: int = 0
    detail_links_found: int = 0
    detail_pages_parsed: int = 0
    raw_candidates: int = 0
    fallback_candidates: int = 0
    filtered_candidates: int = 0
    normalized_success_count: int = 0
    normalized_failure_count: int = 0
    normalize_failure_reasons: str = ""
    upload_attempt_count: int = 0
    upload_url: str = ""
    response_status: str = ""
    response_body: str = ""
    failure_reason: str = ""
    skipped_upload_reason: str = ""
    parser_mode: str = ""
    debug_reasons: str = ""


def safe_print(*values: object, sep: str = " ", end: str = "\n") -> None:
    message = sep.join(str(value) for value in values) + end
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        sys.stdout.write(message)
    except UnicodeEncodeError:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(message.encode(encoding, errors="replace"))
        else:
            sys.stdout.write(message.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def print_source_header(name: str) -> None:
    safe_print(f"=== {name} start ===")


def print_source_report(name: str, stats: SourceStats, community_mode: bool = False) -> None:
    safe_print(f"scraped_count: {stats.collected}")
    safe_print(f"normalized_count: {stats.normalized}")
    safe_print(f"major_count: {stats.major_count}")
    safe_print(f"minor_count: {stats.minor_count}")
    safe_print(f"excluded_count: {stats.excluded_count}")
    safe_print(f"uploadable_count: {stats.uploadable_count}")
    safe_print(f"grouped_event_count: {stats.grouped_event_count}")
    safe_print(f"uploaded_count: {stats.uploaded}")
    safe_print(f"hub_url: {stats.hub_url}")
    safe_print(f"requested_url: {stats.requested_url}")
    safe_print(f"hub_http_status: {stats.hub_http_status}")
    safe_print(f"http_status: {stats.http_status}")
    safe_print(f"hub_html_length: {stats.hub_html_length}")
    safe_print(f"html_length: {stats.html_length}")
    safe_print(f"valid_source_page_count: {stats.valid_source_page_count}")
    safe_print(f"detail_links_found: {stats.detail_links_found}")
    safe_print(f"detail_pages_parsed: {stats.detail_pages_parsed}")
    safe_print(f"parser_mode: {stats.parser_mode}")
    safe_print(f"raw_candidates: {stats.raw_candidates}")
    safe_print(f"fallback_candidates: {stats.fallback_candidates}")
    safe_print(f"filtered_candidates: {stats.filtered_candidates}")
    safe_print(f"normalized_success_count: {stats.normalized_success_count}")
    safe_print(f"normalized_failure_count: {stats.normalized_failure_count}")
    if stats.normalize_failure_reasons:
        safe_print(f"normalize_failure_reasons: {stats.normalize_failure_reasons}")
    safe_print(f"upload_attempt_count: {stats.upload_attempt_count}")
    safe_print(f"upload_url: {stats.upload_url}")
    safe_print(f"response_status: {stats.response_status}")
    if stats.failure_reason:
        safe_print(f"failure_reason: {stats.failure_reason}")
    if stats.response_body:
        safe_print(f"response_body: {stats.response_body}")
    if stats.skipped_upload_reason:
        safe_print(f"skipped_upload_reason: {stats.skipped_upload_reason}")
    if community_mode:
        safe_print(f"Filtered in: {stats.filtered_in}")
        safe_print(f"Uploaded to community_posts: {stats.uploaded}")
        safe_print(f"Skipped: {stats.skipped}")
        safe_print(f"Duplicates: {stats.duplicates}")
        safe_print(f"Errors: {stats.errors}")
    else:
        safe_print(f"Normalized: {stats.normalized}")
        safe_print(f"Uploaded: {stats.uploaded}")
        safe_print(f"Duplicates: {stats.duplicates}")
        safe_print(f"Errors: {stats.errors}")


def print_summary(summary: dict[str, SourceStats]) -> None:
    safe_print("=== Summary ===")
    for name, stats in summary.items():
        safe_print(
            f"[{name}] source={stats.source or name} parser_mode={stats.parser_mode} "
            f"hub_url={stats.hub_url} requested_url={stats.requested_url} "
            f"hub_http_status={stats.hub_http_status} http_status={stats.http_status} "
            f"hub_html_length={stats.hub_html_length} html_length={stats.html_length} scraped_count={stats.collected} "
            f"valid_source_page_count={stats.valid_source_page_count} "
            f"detail_links_found={stats.detail_links_found} detail_pages_parsed={stats.detail_pages_parsed} "
            f"normalized_count={stats.normalized} major_count={stats.major_count} "
            f"minor_count={stats.minor_count} excluded_count={stats.excluded_count} "
            f"uploadable_count={stats.uploadable_count} raw_candidates={stats.raw_candidates} "
            f"fallback_candidates={stats.fallback_candidates} filtered_candidates={stats.filtered_candidates} "
            f"normalized_success_count={stats.normalized_success_count} "
            f"normalized_failure_count={stats.normalized_failure_count} "
            f"grouped_event_count={stats.grouped_event_count} uploaded_count={stats.uploaded} "
            f"upload_attempt_count={stats.upload_attempt_count} upload_url={stats.upload_url} "
            f"response_status={stats.response_status} duplicates={stats.duplicates} errors={stats.errors}"
        )
        if stats.normalize_failure_reasons:
            safe_print(f"[{name}] normalize_failure_reasons={stats.normalize_failure_reasons}")
        if stats.failure_reason:
            safe_print(f"[{name}] failure_reason={stats.failure_reason}")
        if stats.debug_reasons:
            safe_print(f"[{name}] reasons={stats.debug_reasons}")
        if stats.skipped_upload_reason:
            safe_print(f"[{name}] skipped_upload reason={stats.skipped_upload_reason}")
        if stats.response_body:
            safe_print(f"[{name}] response_body={stats.response_body}")
