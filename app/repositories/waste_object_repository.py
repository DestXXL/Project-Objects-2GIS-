from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import RealEstate, WasteObject
from app.services.contract_matching_service import CONTRACT_LINK_STATUS_LABELS, CONTRACT_LINK_STRATEGY_LABELS


class WasteObjectRepository:
    @staticmethod
    def _sort_key(item: WasteObject) -> tuple[bool, bool, int]:
        return (
            getattr(item, "contract_link_status", None) != "matched",
            not bool(getattr(item, "contract_number", None)),
            -item.id,
        )

    @staticmethod
    def count(db: Session) -> int:
        return db.scalar(select(func.count(WasteObject.id))) or 0

    @staticmethod
    def get_by_id(db: Session, waste_object_id: int) -> Optional[WasteObject]:
        query = (
            select(WasteObject)
            .options(
                joinedload(WasteObject.real_estate),
                joinedload(WasteObject.legal_entity),
            )
            .where(WasteObject.id == waste_object_id)
        )
        return db.scalar(query)

    @staticmethod
    def list(db: Session, filters: Optional[dict[str, str]] = None) -> list[WasteObject]:
        query = (
            select(WasteObject)
            .options(
                joinedload(WasteObject.real_estate),
                joinedload(WasteObject.legal_entity),
            )
            .join(RealEstate)
            .order_by(WasteObject.id.desc())
        )
        items = list(db.scalars(query).all())
        items.sort(key=WasteObjectRepository._sort_key)
        filters = {key: value.strip() for key, value in (filters or {}).items() if value and value.strip()}
        if not filters:
            return items

        return [
            item
            for item in items
            if WasteObjectRepository._matches_text(getattr(item, "name", None), filters.get("name"))
            and WasteObjectRepository._matches_text(getattr(item, "category", None), filters.get("category"))
            and WasteObjectRepository._matches_text(getattr(item.real_estate, "address", None), filters.get("address"))
            and WasteObjectRepository._matches_text(getattr(item, "inn", None), filters.get("inn"))
            and WasteObjectRepository._matches_text(getattr(item, "contract_number", None), filters.get("contract"))
            and WasteObjectRepository._matches_link_strategy(item, filters.get("link_strategy"))
        ]

    @staticmethod
    def list_page(
        db: Session,
        filters: Optional[dict[str, str]] = None,
        limit: int = 150,
        offset: int = 0,
    ) -> tuple[list[WasteObject], int]:
        filters = {key: value.strip() for key, value in (filters or {}).items() if value and value.strip()}
        if filters:
            items = WasteObjectRepository.list(db, filters)
            return items[offset : offset + limit], len(items)

        total = WasteObjectRepository.count(db)
        query = (
            select(WasteObject)
            .options(
                joinedload(WasteObject.real_estate),
                joinedload(WasteObject.legal_entity),
            )
            .join(RealEstate)
            .order_by(
                WasteObject.contract_link_status != "matched",
                WasteObject.contract_number.is_(None),
                WasteObject.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(db.scalars(query).all()), total

    @staticmethod
    def list_by_real_estate_id(db: Session, real_estate_id: int) -> list[WasteObject]:
        query = select(WasteObject).where(WasteObject.real_estate_id == real_estate_id).order_by(WasteObject.id)
        return list(db.scalars(query).all())

    @staticmethod
    def list_by_real_estate_ids(db: Session, real_estate_ids: set[int]) -> list[WasteObject]:
        if not real_estate_ids:
            return []
        query = (
            select(WasteObject)
            .where(WasteObject.real_estate_id.in_(real_estate_ids))
            .order_by(WasteObject.real_estate_id, WasteObject.id)
        )
        return list(db.scalars(query).all())

    @staticmethod
    def create(db: Session, flush: bool = True, **kwargs) -> WasteObject:
        waste_object = WasteObject(**kwargs)
        db.add(waste_object)
        if flush:
            db.flush()
        return waste_object

    @staticmethod
    def _matches_text(value: Optional[str], raw_filter: Optional[str]) -> bool:
        if not raw_filter:
            return True
        haystack = (value or "").lower()
        tokens = WasteObjectRepository._search_tokens(raw_filter)
        return all(token in haystack for token in tokens)

    @staticmethod
    def _matches_link_strategy(item: WasteObject, raw_filter: Optional[str]) -> bool:
        if not raw_filter:
            return True
        normalized_filter = raw_filter.strip().lower()
        strategy = item.contract_link_strategy or ""
        status = item.contract_link_status or ""
        selected_strategies = {value for value in normalized_filter.split("|") if value}
        if len(selected_strategies) > 1:
            return strategy.lower() in selected_strategies
        values = [
            strategy,
            CONTRACT_LINK_STRATEGY_LABELS.get(strategy, ""),
            CONTRACT_LINK_STATUS_LABELS.get(status, ""),
            "—" if not strategy and not status else "",
        ]
        if any(marker in normalized_filter for marker in ("+", "_", "—")):
            return any(value.lower() == normalized_filter for value in values if value)
        return any(WasteObjectRepository._matches_text(value, raw_filter) for value in values if value)

    @staticmethod
    def _search_tokens(value: str) -> list[str]:
        tokens = [token for token in re.split(r"[\s,;|/()\\.-]+", value.lower()) if token]
        return tokens or [value.lower()]
