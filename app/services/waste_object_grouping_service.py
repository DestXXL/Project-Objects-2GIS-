from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class WasteObjectGroupingResult:
    enriched_items: list
    incomplete_items: list


class WasteObjectGroupingService:
    # "Большинство данных" считаем по полям, которые обычно приходят из договорной базы
    # и реально помогают работать с объектом дальше.
    ENRICHMENT_THRESHOLD = 4

    @classmethod
    def split_by_enrichment(cls, items: list) -> WasteObjectGroupingResult:
        enriched_items: list = []
        incomplete_items: list = []

        for item in items:
            score = cls._enrichment_score(item)
            if score >= cls.ENRICHMENT_THRESHOLD:
                enriched_items.append(item)
            else:
                incomplete_items.append(item)

        return WasteObjectGroupingResult(
            enriched_items=enriched_items,
            incomplete_items=incomplete_items,
        )

    @classmethod
    def _enrichment_score(cls, item) -> int:
        fields = [
            item.inn,
            getattr(item, "legal_entity_id", None),
            item.contract_number,
            item.contract_date,
            item.contract_start_date,
            item.billing_method,
            item.calculation_value,
            item.comment,
        ]
        return sum(1 for value in fields if cls._is_filled(value))

    @staticmethod
    def _is_filled(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, date):
            return True
        return True
