from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.waste_object import WasteObject


class RealEstate(TimestampMixin, Base):
    __tablename__ = "real_estates"

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    address_key: Mapped[str] = mapped_column(String(500), unique=True, index=True, nullable=False)
    district: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    building: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cadastral_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    object_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    waste_objects: Mapped[list["WasteObject"]] = relationship(
        back_populates="real_estate",
        cascade="all, delete-orphan",
    )
