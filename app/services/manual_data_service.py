from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import ContractRow, LegalEntity, RealEstate, WasteObject
from app.repositories.contract_row_repository import ContractRowRepository
from app.repositories.legal_entity_repository import LegalEntityRepository
from app.repositories.real_estate_repository import RealEstateRepository
from app.services.address_normalization_service import AddressNormalizationService
from app.utils.dates import parse_date
from app.utils.normalization import normalize_address_key, normalize_inn, normalize_text, split_normalized_inns, to_float, to_int


class ManualDataService:
    def __init__(self) -> None:
        self.address_service = AddressNormalizationService()

    def update_real_estate(self, db: Session, real_estate: RealEstate, data: Mapping[str, Any]) -> RealEstate:
        address = self.address_service.normalize(
            address=normalize_text(data.get("address")),
            district=normalize_text(data.get("district")),
            city=normalize_text(data.get("city")),
            street=normalize_text(data.get("street")),
            building=normalize_text(data.get("building")),
        )
        if not address:
            raise ValueError("Укажите адрес объекта недвижимости.")

        address_key = normalize_address_key(address)
        if not address_key:
            raise ValueError("Не удалось нормализовать адрес объекта недвижимости.")

        duplicate = RealEstateRepository.get_by_address_key(db, address_key)
        if duplicate is not None and duplicate.id != real_estate.id:
            raise ValueError("Объект недвижимости с таким адресом уже существует.")

        real_estate.address = address
        real_estate.address_key = address_key
        real_estate.district = normalize_text(data.get("district"))
        real_estate.city = normalize_text(data.get("city"))
        real_estate.street = normalize_text(data.get("street"))
        real_estate.building = normalize_text(data.get("building"))
        real_estate.cadastral_number = normalize_text(data.get("cadastral_number"))
        real_estate.area = self._parse_float(data.get("area"), "Площадь")
        real_estate.floors = self._parse_int(data.get("floors"), "Этажность")
        real_estate.purpose = normalize_text(data.get("purpose"))
        real_estate.object_type = normalize_text(data.get("object_type"))
        db.flush()
        return real_estate

    def update_waste_object(self, db: Session, waste_object: WasteObject, data: Mapping[str, Any]) -> WasteObject:
        waste_object.name = normalize_text(data.get("name"))
        waste_object.category = normalize_text(data.get("category"))
        waste_object.waste_type = normalize_text(data.get("waste_type"))
        waste_object.calculation_value = normalize_text(data.get("calculation_value"))
        waste_object.billing_method = normalize_text(data.get("billing_method"))
        waste_object.contract_number = normalize_text(data.get("contract_number"))
        waste_object.contract_date = self._parse_date(data.get("contract_date"), "Дата договора")
        waste_object.contract_start_date = self._parse_date(data.get("contract_start_date"), "Дата начала действия")
        waste_object.comment = normalize_text(data.get("comment"))

        legal_entities = self._resolve_legal_entities_for_waste_object(db, waste_object, data)
        waste_object.legal_entity_id = legal_entities[0].id if legal_entities else None
        waste_object.inn = self._normalize_inn_value(data.get("inn"))

        db.flush()
        return waste_object

    def update_contract_row(self, db: Session, contract_row: ContractRow, data: Mapping[str, Any]) -> ContractRow:
        contract_row.contract_number = normalize_text(data.get("contract_number"))
        contract_row.contract_date = self._parse_date(data.get("contract_date"), "Дата договора")
        contract_row.legal_entity_name = normalize_text(data.get("legal_entity_name"))
        contract_row.waste_object_name = normalize_text(data.get("waste_object_name"))
        contract_row.inn = self._normalize_inn_value(data.get("inn"))
        contract_row.locality = normalize_text(data.get("locality"))
        contract_row.street = normalize_text(data.get("street"))
        contract_row.building = normalize_text(data.get("building"))
        contract_row.room = normalize_text(data.get("room"))
        contract_row.address = normalize_text(data.get("address")) or self._compose_contract_address(contract_row)
        contract_row.volume = self._parse_float(data.get("volume"), "Объём")
        contract_row.quantity = self._parse_float(data.get("quantity"), "Количество")
        contract_row.pickup_frequency = normalize_text(data.get("pickup_frequency"))
        contract_row.contact_person = normalize_text(data.get("contact_person"))
        contract_row.comment = normalize_text(data.get("comment"))
        contract_row.contract_start_date = self._parse_date(data.get("contract_start_date"), "Дата начала действия")
        db.flush()
        return contract_row

    def bind_contract_row_to_waste_object(
        self,
        db: Session,
        contract_row: ContractRow,
        waste_object: WasteObject,
    ) -> WasteObject:
        duplicate_link = ContractRowRepository.get_by_linked_waste_object_id(
            db,
            waste_object.id,
            exclude_contract_row_id=contract_row.id,
        )
        if duplicate_link is not None:
            raise ValueError("Этот объект 2ГИС уже привязан к другой строке договора.")

        self.update_waste_object(
            db,
            waste_object,
            {
                "name": waste_object.name,
                "category": waste_object.category,
                "waste_type": waste_object.waste_type,
                "calculation_value": self._format_float_value(contract_row.volume, contract_row.quantity),
                "billing_method": contract_row.pickup_frequency,
                "inn": contract_row.inn,
                "legal_entity_name": contract_row.legal_entity_name,
                "contact_person": contract_row.contact_person,
                "phone": waste_object.legal_entity.phone if waste_object.legal_entity else None,
                "email": waste_object.legal_entity.email if waste_object.legal_entity else None,
                "contract_number": contract_row.contract_number,
                "contract_date": contract_row.contract_date,
                "contract_start_date": contract_row.contract_start_date,
                "comment": contract_row.comment,
            },
        )

        waste_object.contract_link_status = "matched"
        waste_object.contract_link_strategy = "manual"
        waste_object.contract_link_reason = "Привязано вручную пользователем"
        waste_object.contract_link_score = None

        contract_row.linked_waste_object_id = waste_object.id
        contract_row.link_mode = "manual"
        contract_row.contract_link_status = "matched"
        contract_row.contract_link_strategy = "manual"
        contract_row.contract_link_reason = "Привязано вручную пользователем"

        db.flush()
        return waste_object

    def update_legal_entity(self, db: Session, entity: LegalEntity, data: Mapping[str, Any]) -> LegalEntity:
        new_inn = normalize_inn(data.get("inn"))
        if not new_inn:
            raise ValueError("ИНН юридического лица обязателен.")

        duplicate = LegalEntityRepository.get_by_inn(db, new_inn)
        if duplicate is not None and duplicate.id != entity.id:
            raise ValueError("Юридическое лицо с таким ИНН уже существует.")

        old_inn = entity.inn
        entity.inn = new_inn
        entity.name = normalize_text(data.get("name"))
        entity.contact_person = normalize_text(data.get("contact_person"))
        entity.phone = normalize_text(data.get("phone"))
        entity.email = normalize_text(data.get("email"))

        for waste_object in entity.waste_objects:
            if waste_object.inn in (None, old_inn):
                waste_object.inn = new_inn
                continue
            waste_inns = split_normalized_inns(waste_object.inn)
            if old_inn in waste_inns:
                updated_inns = [new_inn if inn == old_inn else inn for inn in waste_inns]
                waste_object.inn = "|".join(updated_inns)

        db.flush()
        return entity

    def _resolve_legal_entities_for_waste_object(
        self,
        db: Session,
        waste_object: WasteObject,
        data: Mapping[str, Any],
    ) -> list[LegalEntity]:
        inns = split_normalized_inns(data.get("inn"))
        name = normalize_text(data.get("legal_entity_name"))
        contact_person = normalize_text(data.get("contact_person"))
        phone = normalize_text(data.get("phone"))
        email = normalize_text(data.get("email"))

        if not inns:
            return []

        resolved_entities: list[LegalEntity] = []
        for inn in inns:
            entity = LegalEntityRepository.get_by_inn(db, inn)
            if entity is None:
                entity = LegalEntityRepository.create(
                    db,
                    inn=inn,
                    name=name or (waste_object.legal_entity.name if waste_object.legal_entity else waste_object.name),
                    contact_person=contact_person,
                    phone=phone,
                    email=email,
                )
            else:
                if name:
                    entity.name = name
                if contact_person:
                    entity.contact_person = contact_person
                if phone:
                    entity.phone = phone
                if email:
                    entity.email = email
                db.flush()
            resolved_entities.append(entity)
        return resolved_entities

    @staticmethod
    def _normalize_inn_value(value: Any) -> Optional[str]:
        inns = split_normalized_inns(value)
        if inns:
            return "|".join(inns)
        return normalize_inn(value)

    @staticmethod
    def _format_float_value(volume: Optional[float], quantity: Optional[float]) -> Optional[str]:
        if volume is None:
            return None
        total = volume
        if quantity not in (None, 0):
            total = volume * quantity
        return f"{total:g}"

    @staticmethod
    def _compose_contract_address(contract_row: ContractRow) -> Optional[str]:
        parts = [part for part in (contract_row.locality, contract_row.street) if part]
        if contract_row.building:
            parts.append(f"д. {contract_row.building}")
        if contract_row.room:
            parts.append(f"пом. {contract_row.room}")
        return ", ".join(parts) if parts else None

    @staticmethod
    def _parse_float(value: Any, field_name: str) -> Optional[float]:
        text = normalize_text(value)
        if not text:
            return None
        parsed = to_float(text)
        if parsed is None:
            raise ValueError(f"{field_name} должна быть числом.")
        return parsed

    @staticmethod
    def _parse_int(value: Any, field_name: str) -> Optional[int]:
        text = normalize_text(value)
        if not text:
            return None
        parsed = to_int(text)
        if parsed is None:
            raise ValueError(f"{field_name} должна быть целым числом.")
        return parsed

    @staticmethod
    def _parse_date(value: Any, field_name: str):
        text = normalize_text(value)
        if not text:
            return None
        parsed = parse_date(text)
        if parsed is None:
            raise ValueError(f"{field_name} указана в неверном формате.")
        return parsed
