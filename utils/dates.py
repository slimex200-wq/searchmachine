from __future__ import annotations

import re
from datetime import date
from typing import Optional, Tuple

from dateutil import parser

from utils.normalize import normalize_space

_DATE_TOKEN = r"(?:20\d{2}[./-]|\d{2}[./-])?\d{1,2}[./-]\d{1,2}|\d{1,2}월\s*\d{1,2}일"
_RANGE_PATTERN = re.compile(rf"(?P<a>{_DATE_TOKEN})\s*(?:~|-|to)\s*(?P<b>{_DATE_TOKEN})", re.IGNORECASE)
_UNTIL_PATTERN = re.compile(rf"(?P<d>{_DATE_TOKEN})\s*(?:까지|종료)", re.IGNORECASE)
_DAY_ONLY_UNTIL_PATTERN = re.compile(r"(?P<d>\d{1,2})\s*일까지", re.IGNORECASE)
_MONTH_DAY_TO_DAY_RANGE_PATTERN = re.compile(
    r"(?P<m>\d{1,2})[./-](?P<start_d>\d{1,2})\s*(?:~|-|to)\s*(?P<end_d>\d{1,2})(?![./-])",
    re.IGNORECASE,
)
_WEEKDAY_PAREN_PATTERN = re.compile(r"\(\s*[월화수목금토일]\s*\)")
_TIME_TOKEN_PATTERN = re.compile(r"\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*(?:AM|PM)\b", re.IGNORECASE)


def _safe_parse_one(value: str, fallback_year: int) -> Optional[date]:
    text = normalize_space(value)
    text = text.replace("년", ".").replace("월", ".").replace("일", "")
    text = text.replace("/", ".").replace("-", ".")
    text = re.sub(r"\.(?=\s|$)", "", text)
    text = normalize_space(text)

    if re.match(r"^\d{1,2}\.\d{1,2}$", text):
        text = f"{fallback_year}.{text}"
    elif re.match(r"^\d{2}\.\d{1,2}\.\d{1,2}$", text):
        text = f"20{text}"

    try:
        return parser.parse(text, yearfirst=True, dayfirst=False).date()
    except Exception:
        return None


def parse_date_range_to_iso(text: str, today: Optional[date] = None) -> Tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None

    today = today or date.today()
    normalized = normalize_space(text)
    cleaned = _TIME_TOKEN_PATTERN.sub(" ", _WEEKDAY_PAREN_PATTERN.sub(" ", normalized))
    cleaned = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", cleaned)
    cleaned = re.sub(r"(?<=\d)\.(?=\s*(?:~|-|to|$))", "", cleaned, flags=re.IGNORECASE)
    cleaned = normalize_space(cleaned)

    ranges: list[tuple[date | None, date | None]] = []

    for rng in _RANGE_PATTERN.finditer(cleaned):
        start = _safe_parse_one(rng.group("a"), today.year)
        end = _safe_parse_one(rng.group("b"), today.year)
        if start and end and end < start:
            try:
                end = end.replace(year=end.year + 1)
            except ValueError:
                pass
        if start or end:
            ranges.append((start, end))

    for short_rng in _MONTH_DAY_TO_DAY_RANGE_PATTERN.finditer(cleaned):
        try:
            start = date(today.year, int(short_rng.group("m")), int(short_rng.group("start_d")))
            end = date(today.year, int(short_rng.group("m")), int(short_rng.group("end_d")))
        except ValueError:
            start = None
            end = None
        if start and end and end < start:
            month = start.month + 1
            year = start.year
            if month == 13:
                month = 1
                year += 1
            try:
                end = date(year, month, int(short_rng.group("end_d")))
            except ValueError:
                end = None
        if start or end:
            ranges.append((start, end))

    if ranges:
        starts = [start for start, _ in ranges if start]
        ends = [end for _, end in ranges if end]
        return (
            min(starts).isoformat() if starts else None,
            max(ends).isoformat() if ends else None,
        )

    until = _UNTIL_PATTERN.search(cleaned)
    if until:
        end = _safe_parse_one(until.group("d"), today.year)
        return (None, end.isoformat() if end else None)

    day_only_until = _DAY_ONLY_UNTIL_PATTERN.search(cleaned)
    if day_only_until:
        try:
            end = date(today.year, today.month, int(day_only_until.group("d")))
        except ValueError:
            end = None
        return (None, end.isoformat() if end else None)

    single = _safe_parse_one(cleaned, today.year)
    return (single.isoformat() if single else None, None)
