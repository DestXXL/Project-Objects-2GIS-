from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.models import ContractRow, WasteObject


class ContractRowRepository:
    @staticmethod
    def get_by_id(db: Session, contract_row_id: int) -> Optional[ContractRow]:
        query = (
            select(ContractRow)
            .options(joinedload(ContractRow.linked_waste_object).joinedload(WasteObject.real_estate))
            .where(ContractRow.id == contract_row_id)
        )
        return db.scalar(query)

    @staticmethod
    def create(db: Session, flush: bool = True, **kwargs) -> ContractRow:
        contract_row = ContractRow(**kwargs)
        db.add(contract_row)
        if flush:
            db.flush()
        return contract_row

    @staticmethod
    def delete_all(db: Session) -> None:
        db.execute(delete(ContractRow))

    @staticmethod
    def count(db: Session) -> int:
        return db.query(ContractRow).count()

    @staticmethod
    def list_unresolved(db: Session, filters: Optional[dict[str, str]] = None) -> list[ContractRow]:
        query = (
            select(ContractRow)
            .options(joinedload(ContractRow.linked_waste_object).joinedload(WasteObject.real_estate))
            .where((ContractRow.linked_waste_object_id.is_(None)) | (ContractRow.contract_link_status == "review_required"))
            .order_by(ContractRow.source_row_index)
        )
        items = list(db.scalars(query).all())
        filters = {key: value.strip() for key, value in (filters or {}).items() if value and value.strip()}
        if not filters:
            return items

        return [
            item
            for item in items
            if ContractRowRepository._matches_text(getattr(item, "contract_number", None), filters.get("contract_number"))
            and ContractRowRepository._matches_text(getattr(item, "waste_object_name", None), filters.get("waste_object_name"))
            and ContractRowRepository._matches_text(getattr(item, "inn", None), filters.get("inn"))
            and ContractRowRepository._matches_text(getattr(item, "address", None), filters.get("address"))
        ]

    @staticmethod
    def list_unresolved_page(
        db: Session,
        filters: Optional[dict[str, str]] = None,
        limit: int = 150,
        offset: int = 0,
    ) -> tuple[list[ContractRow], int]:
        items = ContractRowRepository.list_unresolved(db, filters)
        return items[offset : offset + limit], len(items)

    @staticmethod
    def linked_waste_object_ids(db: Session, exclude_contract_row_id: Optional[int] = None) -> set[int]:
        query = select(ContractRow.linked_waste_object_id).where(ContractRow.linked_waste_object_id.is_not(None))
        if exclude_contract_row_id is not None:
            query = query.where(ContractRow.id != exclude_contract_row_id)
        return {value for value in db.scalars(query).all() if value is not None}

    @staticmethod
    def get_by_linked_waste_object_id(
        db: Session,
        waste_object_id: int,
        exclude_contract_row_id: Optional[int] = None,
    ) -> Optional[ContractRow]:
        query = select(ContractRow).where(ContractRow.linked_waste_object_id == waste_object_id)
        if exclude_contract_row_id is not None:
            query = query.where(ContractRow.id != exclude_contract_row_id)
        return db.scalar(query)

    @staticmethod
    def _matches_text(value: Optional[str], raw_filter: Optional[str]) -> bool:
        if not raw_filter:
            return True
        haystack = (value or "").lower()
        tokens = ContractRowRepository._search_tokens(raw_filter)
        return all(token in haystack for token in tokens)

    @staticmethod
    def _search_tokens(value: str) -> list[str]:
        tokens = [token for token in re.split(r"[\s,;|/()\\.-]+", value.lower()) if token]
        return tokens or [value.lower()]
