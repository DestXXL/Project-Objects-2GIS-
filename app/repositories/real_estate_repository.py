from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import RealEstate, WasteObject


class RealEstateRepository:
    @staticmethod
    def count(db: Session) -> int:
        return db.scalar(select(func.count(RealEstate.id))) or 0

    @staticmethod
    def get_by_id(db: Session, real_estate_id: int) -> Optional[RealEstate]:
        query = (
            select(RealEstate)
            .options(selectinload(RealEstate.waste_objects).selectinload(WasteObject.legal_entity))
            .where(RealEstate.id == real_estate_id)
        )
        return db.scalar(query)

    @staticmethod
    def get_by_address_key(db: Session, address_key: str) -> Optional[RealEstate]:
        return db.scalar(select(RealEstate).where(RealEstate.address_key == address_key))

    @staticmethod
    def get_by_address_keys(db: Session, address_keys: set[str]) -> dict[str, RealEstate]:
        if not address_keys:
            return {}
        real_estates = db.scalars(select(RealEstate).where(RealEstate.address_key.in_(address_keys))).all()
        return {real_estate.address_key: real_estate for real_estate in real_estates}

    @staticmethod
    def list_with_counts(db: Session, filters: Optional[dict[str, str]] = None) -> list[tuple[RealEstate, int]]:
        query = (
            select(RealEstate, func.count(WasteObject.id).label("waste_count"))
            .outerjoin(WasteObject, WasteObject.real_estate_id == RealEstate.id)
            .group_by(RealEstate.id)
            .order_by(RealEstate.address)
        )
        rows = [(entity, waste_count) for entity, waste_count in db.execute(query).all()]
        filters = {key: value.strip() for key, value in (filters or {}).items() if value and value.strip()}
        if not filters:
            return rows

        return [
            (entity, waste_count)
            for entity, waste_count in rows
            if RealEstateRepository._matches_text(entity.address, filters.get("address"))
        ]

    @staticmethod
    def list_with_counts_page(
        db: Session,
        filters: Optional[dict[str, str]] = None,
        limit: int = 150,
        offset: int = 0,
    ) -> tuple[list[tuple[RealEstate, int]], int]:
        filters = {key: value.strip() for key, value in (filters or {}).items() if value and value.strip()}
        if filters:
            rows = RealEstateRepository.list_with_counts(db, filters)
            return rows[offset : offset + limit], len(rows)

        total = RealEstateRepository.count(db)
        query = (
            select(RealEstate, func.count(WasteObject.id).label("waste_count"))
            .outerjoin(WasteObject, WasteObject.real_estate_id == RealEstate.id)
            .group_by(RealEstate.id)
            .order_by(RealEstate.address)
            .limit(limit)
            .offset(offset)
        )
        return [(entity, waste_count) for entity, waste_count in db.execute(query).all()], total

    @staticmethod
    def create(db: Session, flush: bool = True, **kwargs) -> RealEstate:
        real_estate = RealEstate(**kwargs)
        db.add(real_estate)
        if flush:
            db.flush()
        return real_estate

    @staticmethod
    def _matches_text(value: Optional[str], raw_filter: Optional[str]) -> bool:
        if not raw_filter:
            return True
        haystack = (value or "").lower()
        tokens = RealEstateRepository._search_tokens(raw_filter)
        return all(token in haystack for token in tokens)

    @staticmethod
    def _search_tokens(value: str) -> list[str]:
        tokens = [token for token in re.split(r"[\s,;|/()\\.-]+", value.lower()) if token]
        return tokens or [value.lower()]
