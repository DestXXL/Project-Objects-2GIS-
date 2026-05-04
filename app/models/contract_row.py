from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.waste_object import WasteObject


class ContractRow(TimestampMixin, Base):
    __tablename__ = "contract_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_row_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    contract_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    contract_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    legal_entity_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    waste_object_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    inn: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, index=True)
    compact_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    locality: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    building: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    room: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    material: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pickup_frequency: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    contract_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_link_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    contract_link_strategy: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contract_link_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    linked_waste_object_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("waste_objects.id"),
        nullable=True,
        index=True,
    )
    link_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="none")

    linked_waste_object: Mapped[Optional["WasteObject"]] = relationship()
