from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from api_client import ApiRequestError, PickSaleApiClient
from app.core.models import GroupedSaleEvent, SalePage
from app.core.sale_classifier import classify_sale_importance
from app.core.sale_grouping import group_sale_events
from pipelines.normalize import normalize_official_rows
from pipelines.upload import upload_community_payloads
from utils import SourceStats, clean_text, normalize_link, normalize_platform, parse_date_range_to_iso, safe_print


@dataclass
class SourceRunResult:
    source: str
    stats: SourceStats
    sale_pages: list[SalePage] = field(default_factory=list)
    grouped_events: list[GroupedSaleEvent] = field(default_factory=list)


class SaleDiscoveryEngine:
    def __init__(self, client: PickSaleApiClient, timeout_seconds: int, debug_save_html: bool, debug_dir: str):
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.debug_save_html = debug_save_html
        self.debug_dir = debug_dir

    def run_official_source(
        self,
        source: str,
        scrape_fn: Callable[..., dict],
        default_category: str,
    ) -> SourceRunResult:
        stats = SourceStats()
        raw_rows, dbg = self._run_scrape(source, scrape_fn, stats, limit=12)
        if stats.errors:
            return SourceRunResult(source=source, stats=stats)

        self._populate_stats_from_debug(stats, dbg, collected=len(raw_rows))
        stats.upload_url = self.client.sales_api_url
        source_label = self._source_label(source)

        safe_print(f"[sales] source={source} scraped_count={stats.collected}")
        if not stats.upload_url:
            stats.skipped_upload_reason = "missing_sales_api_url"
            safe_print("[sales] skipped_upload reason=missing_sales_api_url")

        self._log_official_raw_candidates(source_label, raw_rows)
        normalized_rows = normalize_official_rows(raw_rows, default_category=default_category)
        stats.normalized = len(normalized_rows)
        safe_print(f"[{source_label}] normalized_count={stats.normalized}")
        norm_debug = self._log_official_normalization_debug(source_label, raw_rows, default_category)
        stats.normalized_success_count = norm_debug["success_count"]
        stats.normalized_failure_count = norm_debug["failure_count"]
        stats.normalize_failure_reasons = ",".join(norm_debug["failure_reasons"])

        sale_pages = [self._to_sale_page(row, source) for row in normalized_rows]
        sale_pages = [self._classify_page(page) for page in sale_pages]
        stats.major_count = sum(1 for p in sale_pages if p.sale_tier == "major")
        stats.minor_count = sum(1 for p in sale_pages if p.sale_tier == "minor")
        stats.excluded_count = sum(1 for p in sale_pages if p.sale_tier == "excluded")
        major_titles = [p.title for p in sale_pages if p.sale_tier == "major"]
        minor_titles = [p.title for p in sale_pages if p.sale_tier == "minor"]
        excluded_titles = [p.title for p in sale_pages if p.sale_tier == "excluded"]
        safe_print(f"[{source_label}] major_titles={major_titles}")
        safe_print(f"[{source_label}] minor_titles={minor_titles}")
        safe_print(f"[{source_label}] excluded_titles={excluded_titles}")
        for page in sale_pages:
            safe_print(
                f"[{source_label}] item=\"{page.title}\" score={page.importance_score} "
                f"tier={page.sale_tier} reason={page.filter_reason}"
            )
        safe_print(
            f"[sales] major={stats.major_count} minor={stats.minor_count} excluded={stats.excluded_count}"
        )

        candidate_pages = [p for p in sale_pages if p.sale_tier in {"major", "minor"}]
        stats.uploadable_count = len(candidate_pages)
        safe_print(f"[sales] uploadable_count={stats.uploadable_count}")

        self._set_skipped_upload_reason(stats, candidate_pages)

        grouped_events, pages_with_key = group_sale_events(candidate_pages)
        stats.grouped_event_count = len(grouped_events)
        safe_print(f"[sales] grouped_events={stats.grouped_event_count}")

        event_key_by_link = {p.link: p.event_key for p in pages_with_key}
        for page in sale_pages:
            if page.link in event_key_by_link:
                page.event_key = event_key_by_link[page.link]

        uploaded = self._upload_grouped_events(grouped_events, stats)
        stats.uploaded = uploaded
        safe_print(f"[{source_label}] uploaded_count={stats.uploaded}")
        if stats.skipped_upload_reason:
            safe_print(f"[{source_label}] skipped_reason={stats.skipped_upload_reason}")

        return SourceRunResult(
            source=source,
            stats=stats,
            sale_pages=sale_pages,
            grouped_events=grouped_events,
        )

    def run_community_source(
        self,
        source: str,
        scrape_fn: Callable[..., dict],
        normalize_fn: Callable[..., list[dict]],
        enable_upload: bool,
    ) -> SourceRunResult:
        stats = SourceStats()
        raw_rows, dbg = self._run_scrape(source, scrape_fn, stats, limit=20)
        if stats.errors:
            return SourceRunResult(source=source, stats=stats)

        self._populate_stats_from_debug(stats, dbg, collected=len(raw_rows))

        normalized_rows = normalize_fn(raw_rows, source_site=source.lower().replace("community", "").strip("_"))
        stats.normalized = len(normalized_rows)

        classified_rows: list[dict] = []
        for row in normalized_rows:
            tier, score, reason = classify_sale_importance(
                title=str(row.get("title", "")),
                description=str(row.get("content", "")),
                link=str(row.get("link", "")),
                start_date=None,
                end_date=None,
            )
            row2 = dict(row)
            row2["sale_tier"] = tier
            row2["importance_score"] = score
            row2["filter_reason"] = reason
            classified_rows.append(row2)

        stats.major_count = sum(1 for r in classified_rows if r.get("sale_tier") == "major")
        stats.minor_count = sum(1 for r in classified_rows if r.get("sale_tier") == "minor")
        stats.excluded_count = sum(1 for r in classified_rows if r.get("sale_tier") == "excluded")
        stats.filtered_in = len(classified_rows)

        if enable_upload:
            upload_community_payloads(self.client, classified_rows, stats)
        else:
            stats.skipped += len(classified_rows)

        return SourceRunResult(source=source, stats=stats)

    def _run_scrape(
        self,
        source: str,
        scrape_fn: Callable[..., dict],
        stats: SourceStats,
        *,
        limit: int,
    ) -> tuple[list[dict], dict]:
        try:
            scraped = scrape_fn(
                timeout_seconds=self.timeout_seconds,
                limit=limit,
                debug_save_html=self.debug_save_html,
                debug_dir=self.debug_dir,
            )
        except Exception as exc:
            stats.errors += 1
            stats.debug_reasons = f"scrape_error:{type(exc).__name__}"
            safe_print(f"[{self._source_label(source)}] scrape_error={type(exc).__name__}: {exc}")
            return [], {}

        if isinstance(scraped, dict):
            rows = scraped.get("rows", [])
            debug = scraped.get("debug", {})
            return rows if isinstance(rows, list) else [], debug if isinstance(debug, dict) else {}
        return scraped if isinstance(scraped, list) else [], {}

    def _populate_stats_from_debug(self, stats: SourceStats, dbg: dict, *, collected: int) -> None:
        stats.collected = collected
        stats.hub_url = str(dbg.get("hub_url", "") or "")
        stats.requested_url = ",".join(dbg.get("requested_url", []))
        stats.hub_http_status = str(dbg.get("hub_http_status", "") or "")
        stats.http_status = ",".join(dbg.get("http_status", []))
        stats.hub_html_length = str(dbg.get("hub_html_length", "") or "")
        stats.html_length = ",".join(dbg.get("html_length", []))
        stats.valid_source_page_count = int(dbg.get("valid_source_page_count", 0) or 0)
        stats.detail_links_found = int(dbg.get("detail_links_found", 0) or 0)
        stats.detail_pages_parsed = int(dbg.get("detail_pages_parsed", 0) or 0)
        stats.raw_candidates = int(dbg.get("raw_candidates", 0) or 0)
        stats.fallback_candidates = int(dbg.get("fallback_candidates", 0) or 0)
        stats.filtered_candidates = int(dbg.get("filtered_candidates", 0) or 0)
        stats.failure_reason = str(dbg.get("failure_reason", "") or "")
        stats.debug_reasons = ",".join(dbg.get("reasons", []))
        stats.parser_mode = self._parser_mode(dbg)

    def _set_skipped_upload_reason(self, stats: SourceStats, candidate_pages: list[SalePage]) -> None:
        if stats.skipped_upload_reason:
            return

        reason = ""
        if stats.collected == 0 and stats.raw_candidates == 0:
            reason = "no_scraped_sales"
        elif stats.collected == 0 and stats.raw_candidates > 0:
            reason = "no_filtered_sales"
        elif stats.normalized == 0:
            reason = "no_normalized_sales"
        elif not candidate_pages:
            reason = "no_uploadable_sales"

        if reason:
            stats.skipped_upload_reason = reason
            safe_print(f"[sales] skipped_upload reason={reason}")

    @staticmethod
    def _source_label(source: str) -> str:
        label = source.lower().replace("scraper", "").replace("discovery", "").strip("_")
        if "navernews" in label:
            return "naver_news"
        return label

    def _upload_grouped_events(self, events: list[GroupedSaleEvent], stats: SourceStats) -> int:
        uploaded = 0
        seen_links: set[str] = set()
        safe_print(f"[sales] upload_attempt_count={len(events)}")
        safe_print(f"[sales] upload_url={self.client.sales_api_url}")
        for ev in events:
            payload = ev.as_sales_payload()
            if not payload.get("link"):
                stats.skipped += 1
                if not stats.skipped_upload_reason:
                    stats.skipped_upload_reason = "missing_link"
                safe_print("[sales] skipped_upload reason=missing_link")
                continue
            if payload["link"] in seen_links:
                stats.duplicates += 1
                safe_print(f"[sales] skipped_upload reason=duplicate_link link={payload['link']}")
                continue
            seen_links.add(payload["link"])
            stats.upload_attempt_count += 1
            try:
                result = self.client.send_sale(payload)
                stats.response_status = str(result.get("_status_code", ""))
                stats.response_body = str(result.get("_response_text", ""))[:500]
                safe_print(f"[sales] response_status={stats.response_status}")
                if result.get("inserted"):
                    uploaded += 1
                    safe_print(f"[sales] uploaded={uploaded}")
                elif result.get("duplicate") or result.get("inserted") is False:
                    stats.duplicates += 1
                    safe_print(f"[sales] duplicate_response body={stats.response_body}")
                else:
                    stats.errors += 1
                    safe_print(f"[sales] unexpected_response body={stats.response_body}")
            except ApiRequestError as exc:
                stats.response_status = str(exc.status_code or "")
                stats.response_body = exc.response_text[:500]
                safe_print(f"[sales] response_status={stats.response_status}")
                if stats.response_body:
                    safe_print(f"[sales] response_body={stats.response_body}")
                fallback_payload = dict(payload)
                fallback_payload.pop("event_key", None)
                fallback_payload.pop("sale_tier", None)
                fallback_payload.pop("importance_score", None)
                fallback_payload.pop("filter_reason", None)
                safe_print("[sales] retry_without_extended_fields=true")
                try:
                    result = self.client.send_sale(fallback_payload)
                    stats.response_status = str(result.get("_status_code", ""))
                    stats.response_body = str(result.get("_response_text", ""))[:500]
                    safe_print(f"[sales] response_status={stats.response_status}")
                    if result.get("inserted"):
                        uploaded += 1
                        safe_print(f"[sales] uploaded={uploaded}")
                    elif result.get("duplicate") or result.get("inserted") is False:
                        stats.duplicates += 1
                        safe_print(f"[sales] duplicate_response body={stats.response_body}")
                    else:
                        stats.errors += 1
                        safe_print(f"[sales] unexpected_response body={stats.response_body}")
                except ApiRequestError as retry_exc:
                    stats.errors += 1
                    stats.response_status = str(retry_exc.status_code or "")
                    stats.response_body = retry_exc.response_text[:500]
                    safe_print(f"[sales] response_status={stats.response_status}")
                    safe_print(f"[sales] upload_error={retry_exc}")
                    if stats.response_body:
                        safe_print(f"[sales] response_body={stats.response_body}")
                except Exception as retry_exc:
                    stats.errors += 1
                    stats.response_body = str(retry_exc)[:500]
                    safe_print(f"[sales] upload_error={retry_exc}")
            except Exception as exc:
                stats.errors += 1
                stats.response_body = str(exc)[:500]
                safe_print(f"[sales] upload_error={exc}")
        return uploaded

    @staticmethod
    def _log_official_raw_candidates(source_label: str, raw_rows: list[dict]) -> None:
        for row in raw_rows:
            safe_print(f"[{source_label}] raw_candidate={row}")

    @staticmethod
    def _log_official_normalization_debug(
        source_label: str,
        raw_rows: list[dict],
        default_category: str,
    ) -> dict[str, Any]:
        normalized_rows = normalize_official_rows(raw_rows, default_category=default_category)
        normalized_success_count = len(normalized_rows)
        normalized_failure_count = max(0, len(raw_rows) - normalized_success_count)
        normalize_failure_reasons: list[str] = []

        for row in raw_rows:
            title = clean_text(row.get("title", ""), 120)
            link = normalize_link(row.get("link", ""), row.get("source_url", ""))
            platform = normalize_platform(row.get("platform_hint") or row.get("platform") or "")
            if not title:
                normalize_failure_reasons.append("missing_title")
                safe_print(f"[{source_label}] normalize_failure reason=missing_title row={row}")
            elif not link.startswith("http"):
                normalize_failure_reasons.append("invalid_link")
                safe_print(f"[{source_label}] normalize_failure reason=invalid_link row={row}")
            elif not platform:
                normalize_failure_reasons.append("platform_unrecognized")
                safe_print(f"[{source_label}] normalize_failure reason=platform_unrecognized row={row}")

        for normalized_payload in normalized_rows:
            safe_print(f"[{source_label}] normalized_item={normalized_payload}")

        safe_print(f"[{source_label}] normalized_success_count={normalized_success_count}")
        safe_print(f"[{source_label}] normalized_failure_count={normalized_failure_count}")
        safe_print(f"[{source_label}] normalize_failure_reasons={normalize_failure_reasons}")
        return {
            "success_count": normalized_success_count,
            "failure_count": normalized_failure_count,
            "failure_reasons": normalize_failure_reasons,
        }

    @staticmethod
    def _parser_mode(debug: dict) -> str:
        explicit = str(debug.get("parser_mode", "") or "")
        if explicit:
            return explicit
        reasons = set(debug.get("reasons", []) if isinstance(debug, dict) else [])
        if "next_data_fallback" in reasons:
            return "next_data_fallback"
        if "selector_zero" in reasons:
            return "fallback_anchor"
        return "selector"

    @staticmethod
    def _to_sale_page(row: dict, source: str) -> SalePage:
        return SalePage(
            platform=str(row.get("platform", "")),
            title=str(row.get("sale_name", "")),
            link=str(row.get("link", "")),
            start_date=row.get("start_date"),
            end_date=row.get("end_date"),
            category=str(row.get("category", "기획전")),
            description=str(row.get("description", "")),
            source=source,
            source_type=str(row.get("source_type", "crawler")),
            status=str(row.get("status", "published")),
            signal_type=str(row.get("signal_type", "detail")),
            confidence_score=float(row.get("confidence_score", 0.0) or 0.0),
            source_url=str(row.get("source_url", row.get("link", "")) or row.get("link", "")),
            pub_date=row.get("pub_date"),
            image_url=row.get("image_url"),
            review_status=row.get("review_status"),
            publish_status=row.get("publish_status"),
        )

    @staticmethod
    def _classify_page(page: SalePage) -> SalePage:
        tier, score, reason = classify_sale_importance(
            title=page.title,
            description=page.description,
            link=page.link,
            start_date=page.start_date,
            end_date=page.end_date,
            signal_type=page.signal_type,
            confidence_score=page.confidence_score,
        )
        page.sale_tier = tier
        page.importance_score = score
        page.filter_reason = reason
        return page
