from __future__ import annotations

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
    def list_with_counts(db: Session, search: Optional[str] = None) -> list[tuple[RealEstate, int]]:
        query = (
            select(RealEstate, func.count(WasteObject.id).label("waste_count"))
            .outerjoin(WasteObject, WasteObject.real_estate_id == RealEstate.id)
            .group_by(RealEstate.id)
            .order_by(RealEstate.address)
        )
        if search:
            pattern = f"%{search.lower()}%"
            query = query.where(func.lower(RealEstate.address).like(pattern))

        return [(entity, waste_count) for entity, waste_count in db.execute(query).all()]

    @staticmethod
    def create(db: Session, **kwargs) -> RealEstate:
        real_estate = RealEstate(**kwargs)
        db.add(real_estate)
        db.flush()
        return real_estate
