from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

import pandas as pd


def normalize_text(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    text = re.sub(r"\s+", " ", text)
    return text or None


def normalize_header(value: object) -> str:
    text = normalize_text(value) or ""
    text = text.lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[^a-z0-9а-я_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def normalize_inn(value: object) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            return str(int(value))

    text = normalize_text(value)
    if not text:
        return None

    try:
        decimal_value = Decimal(text)
        if decimal_value == decimal_value.to_integral_value():
            return str(decimal_value.quantize(Decimal("1")))
    except (InvalidOperation, ValueError):
        pass

    digits = re.sub(r"\D+", "", text)
    return digits or None


def split_normalized_inns(value: object) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        raw_parts = re.split(r"[|,;/]+", value)
    else:
        raw_parts = [value]

    inns: list[str] = []
    seen: set[str] = set()
    for raw_part in raw_parts:
        normalized = normalize_inn(raw_part)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        inns.append(normalized)
    return inns


def normalize_address_key(address: Optional[str]) -> Optional[str]:
    text = normalize_text(address)
    if not text:
        return None
    text = text.lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text


def to_float(value: object) -> Optional[float]:
    text = normalize_text(value)
    if text is None:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def to_int(value: object) -> Optional[int]:
    numeric = to_float(value)
    if numeric is None:
        return None
    return int(numeric)
