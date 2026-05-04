from __future__ import annotations

from collections import Counter
import re
from typing import Optional

from sqlalchemy import func, literal, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import LegalEntity, WasteObject
from app.utils.normalization import split_normalized_inns


class LegalEntityRepository:
    @staticmethod
    def count(db: Session) -> int:
        return db.scalar(select(func.count(LegalEntity.id))) or 0

    @staticmethod
    def get_by_id(db: Session, entity_id: int) -> Optional[LegalEntity]:
        query = (
            select(LegalEntity)
            .options(selectinload(LegalEntity.waste_objects).selectinload(WasteObject.real_estate))
            .where(LegalEntity.id == entity_id)
        )
        return db.scalar(query)

    @staticmethod
    def get_by_inn(db: Session, inn: str) -> Optional[LegalEntity]:
        return db.scalar(select(LegalEntity).where(LegalEntity.inn == inn))

    @staticmethod
    def get_by_inns(db: Session, inns: set[str]) -> dict[str, LegalEntity]:
        if not inns:
            return {}
        entities = db.scalars(select(LegalEntity).where(LegalEntity.inn.in_(inns))).all()
        return {entity.inn: entity for entity in entities}

    @staticmethod
    def list_with_counts(db: Session, filters: Optional[dict[str, str]] = None) -> list[tuple[LegalEntity, int]]:
        entities = list(db.scalars(select(LegalEntity).order_by(LegalEntity.inn)).all())
        count_by_entity_id = LegalEntityRepository._count_related_waste_objects(db, entities)
        rows = [(entity, count_by_entity_id.get(entity.id, 0)) for entity in entities]
        filters = {key: value.strip() for key, value in (filters or {}).items() if value and value.strip()}
        if not filters:
            return rows

        return [
            (entity, waste_count)
            for entity, waste_count in rows
            if LegalEntityRepository._matches_text(entity.inn, filters.get("inn"))
            and LegalEntityRepository._matches_text(entity.name, filters.get("name"))
        ]

    @staticmethod
    def list_with_counts_page(
        db: Session,
        filters: Optional[dict[str, str]] = None,
        limit: int = 150,
        offset: int = 0,
    ) -> tuple[list[tuple[LegalEntity, int]], int]:
        rows = LegalEntityRepository.list_with_counts(db, filters)
        return rows[offset : offset + limit], len(rows)

    @staticmethod
    def create(db: Session, flush: bool = True, **kwargs) -> LegalEntity:
        entity = LegalEntity(**kwargs)
        db.add(entity)
        if flush:
            db.flush()
        return entity

    @staticmethod
    def list_related_waste_objects(db: Session, entity_id: int) -> list[WasteObject]:
        entity = LegalEntityRepository.get_by_id(db, entity_id)
        if entity is None:
            return []

        query = (
            select(WasteObject)
            .options(selectinload(WasteObject.real_estate))
            .where(LegalEntityRepository._waste_object_link_condition(entity))
            .order_by(WasteObject.id.desc())
        )
        return list(db.scalars(query).all())

    @staticmethod
    def _waste_object_link_condition(entity: Optional[LegalEntity] = None):
        if entity is not None:
            inn = entity.inn
            return or_(
                WasteObject.legal_entity_id == entity.id,
                WasteObject.inn == inn,
                WasteObject.inn.like(inn + "|%"),
                WasteObject.inn.like("%|" + inn + "|%"),
                WasteObject.inn.like("%|" + inn),
            )

        return or_(
            WasteObject.legal_entity_id == LegalEntity.id,
            WasteObject.inn == LegalEntity.inn,
            WasteObject.inn.like(LegalEntity.inn + literal("|%")),
            WasteObject.inn.like(literal("%|") + LegalEntity.inn + literal("|%")),
            WasteObject.inn.like(literal("%|") + LegalEntity.inn),
        )

    @staticmethod
    def _count_related_waste_objects(db: Session, entities: list[LegalEntity]) -> dict[int, int]:
        if not entities:
            return {}

        inn_to_entity_id = {entity.inn: entity.id for entity in entities}
        counts: Counter[int] = Counter()
        rows = db.execute(select(WasteObject.legal_entity_id, WasteObject.inn)).all()

        for legal_entity_id, inn_value in rows:
            matched_entity_ids: set[int] = set()
            if legal_entity_id is not None:
                matched_entity_ids.add(legal_entity_id)
            for inn in split_normalized_inns(inn_value):
                entity_id = inn_to_entity_id.get(inn)
                if entity_id is not None:
                    matched_entity_ids.add(entity_id)
            for entity_id in matched_entity_ids:
                counts[entity_id] += 1

        return dict(counts)

    @staticmethod
    def _matches_text(value: Optional[str], raw_filter: Optional[str]) -> bool:
        if not raw_filter:
            return True
        haystack = (value or "").lower()
        tokens = LegalEntityRepository._search_tokens(raw_filter)
        return all(token in haystack for token in tokens)

    @staticmethod
    def _search_tokens(value: str) -> list[str]:
        tokens = [token for token in re.split(r"[\s,;|/()\\.-]+", value.lower()) if token]
        return tokens or [value.lower()]
