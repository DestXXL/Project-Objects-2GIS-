from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import RealEstate, WasteObject


class WasteObjectRepository:
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
    def list(db: Session, search: Optional[str] = None) -> list[WasteObject]:
        query = (
            select(WasteObject)
            .options(
                joinedload(WasteObject.real_estate),
                joinedload(WasteObject.legal_entity),
            )
            .join(RealEstate)
            .order_by(WasteObject.id.desc())
        )
        if search:
            pattern = f"%{search.lower()}%"
            query = query.where(
                or_(
                    func.lower(func.coalesce(WasteObject.name, "")).like(pattern),
                    func.lower(func.coalesce(WasteObject.inn, "")).like(pattern),
                    func.lower(func.coalesce(RealEstate.address, "")).like(pattern),
                )
            )

        return list(db.scalars(query).all())

    @staticmethod
    def list_by_real_estate_id(db: Session, real_estate_id: int) -> list[WasteObject]:
        query = select(WasteObject).where(WasteObject.real_estate_id == real_estate_id).order_by(WasteObject.id)
        return list(db.scalars(query).all())

    @staticmethod
    def create(db: Session, **kwargs) -> WasteObject:
        waste_object = WasteObject(**kwargs)
        db.add(waste_object)
        db.flush()
        return waste_object
