"""Canonical parsers for workout field values."""

from __future__ import annotations

from datetime import date, datetime


DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%b %d, %Y",
    "%b %d",
)


def parse_date(value: str | date | datetime) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    for fmt in DATE_FORMATS:
        try:
            if fmt == "%b %d":
                parsed = datetime.strptime(f"{text} {date.today().year}", "%b %d %Y").date()
            else:
                parsed = datetime.strptime(text, fmt).date()
            return parsed
        except ValueError:
            continue
    return None


def parse_weight(value: str | int | float) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None
