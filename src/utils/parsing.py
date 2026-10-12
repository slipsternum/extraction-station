from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from src.core import config

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y")
_YEARLESS_FORMATS = ("%d/%m", "%d.%m", "%d %b", "%d %B", "%b %d", "%B %d")


LOCAL_TZ = timezone(timedelta(hours=config.UTC_OFFSET_HOURS))


def today_local() -> date:
    return datetime.now(LOCAL_TZ).date()


def to_local(timestamp: str) -> datetime:
    """A stored UTC timestamp (``2026-10-12T08:00:00Z``) in the configured local time."""
    return datetime.fromisoformat(timestamp).astimezone(LOCAL_TZ)


def parse_date(text: str, *, today: Optional[date] = None) -> Optional[date]:
    """Parse common roast-date spellings; a missing year resolves to the latest date not in the future."""
    cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text.strip().replace(",", " "))
    cleaned = re.sub(r"\s+", " ", cleaned)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    today = today or today_local()
    for fmt in _YEARLESS_FORMATS:
        try:
            parsed = datetime.strptime(f"{cleaned} {today.year}", f"{fmt} %Y").date()
        except ValueError:
            continue
        return parsed if parsed <= today else parsed.replace(year=today.year - 1)
    return None


def parse_number(text: str) -> Optional[float]:
    """Parse a positive number, accepting ``m:ss`` durations as seconds."""
    cleaned = text.strip().lower().rstrip("gsch°").strip().replace(",", ".")
    minutes = re.fullmatch(r"(\d+):([0-5]\d)", cleaned)
    if minutes:
        return int(minutes.group(1)) * 60 + int(minutes.group(2))
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value >= 0 else None


def split_notes(text: str) -> list[str]:
    return [note.strip().lower() for note in re.split(r"[,;\n/]", text) if note.strip()]


__all__ = ["LOCAL_TZ", "parse_date", "parse_number", "split_notes", "to_local", "today_local"]
