from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import LegalEntity, WasteObject


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
    def list_with_counts(db: Session, search: Optional[str] = None) -> list[tuple[LegalEntity, int]]:
        query = (
            select(LegalEntity, func.count(WasteObject.id).label("waste_count"))
            .outerjoin(WasteObject, WasteObject.legal_entity_id == LegalEntity.id)
            .group_by(LegalEntity.id)
            .order_by(LegalEntity.inn)
        )
        if search:
            pattern = f"%{search.lower()}%"
            query = query.where(
                or_(
                    func.lower(LegalEntity.inn).like(pattern),
                    func.lower(func.coalesce(LegalEntity.name, "")).like(pattern),
                )
            )

        return [(entity, waste_count) for entity, waste_count in db.execute(query).all()]

    @staticmethod
    def create(db: Session, **kwargs) -> LegalEntity:
        entity = LegalEntity(**kwargs)
        db.add(entity)
        db.flush()
        return entity
