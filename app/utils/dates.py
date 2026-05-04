from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd


def parse_date(value: object) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    try:
        parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    except (TypeError, ValueError):
        return None

    if pd.isna(parsed):
        return None

    return parsed.date()
