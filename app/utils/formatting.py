from __future__ import annotations

from datetime import date, datetime


def format_date_ru(value: object) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)
