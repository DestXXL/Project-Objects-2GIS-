from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.legal_entity import LegalEntity
    from app.models.real_estate import RealEstate


class WasteObject(TimestampMixin, Base):
    __tablename__ = "waste_objects"

    id: Mapped[int] = mapped_column(primary_key=True)
    real_estate_id: Mapped[int] = mapped_column(ForeignKey("real_estates.id"), nullable=False, index=True)
    legal_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("legal_entities.id"),
        nullable=True,
        index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    waste_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    waste_generation_norm: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    calculation_unit: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    calculation_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    billing_method: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    inn: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    source_contract_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_contract_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contract_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    contract_link_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    contract_link_strategy: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contract_link_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    contract_link_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_row_index: Mapped[int] = mapped_column(Integer, nullable=False)

    real_estate: Mapped["RealEstate"] = relationship(back_populates="waste_objects")
    legal_entity: Mapped[Optional["LegalEntity"]] = relationship(back_populates="waste_objects")
