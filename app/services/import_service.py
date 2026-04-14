from __future__ import annotations

import re
from typing import Optional, Union

from sqlalchemy.orm import Session

from app.models import LegalEntity, RealEstate
from app.repositories.legal_entity_repository import LegalEntityRepository
from app.repositories.real_estate_repository import RealEstateRepository
from app.repositories.waste_object_repository import WasteObjectRepository
from app.schemas.imports import ImportResult, ParsedImportRow
from app.services.address_normalization_service import AddressNormalizationService
from app.services.contract_matching_service import ContractMatcher, ContractMatchingService
from app.services.import_mapping import canonicalize_dataframe
from app.utils.dates import parse_date
from app.utils.normalization import (
    normalize_address_key,
    normalize_inn,
    normalize_text,
    to_float,
    to_int,
)


class ImportService:
    def __init__(self) -> None:
        self.address_service = AddressNormalizationService()
        self.contract_service = ContractMatchingService()

    def import_dataframe(self, db: Session, dataframe, contract_dataframe=None) -> ImportResult:
        canonical_df, _ = canonicalize_dataframe(dataframe)
        contract_matcher: Optional[ContractMatcher] = None
        contracts_loaded = 0
        contracts_matched = 0

        if contract_dataframe is not None:
            contract_matcher = self.contract_service.build_matcher(contract_dataframe)
            contracts_loaded = len(contract_matcher.records)

        prepared_rows: list[ParsedImportRow] = []
        for index, row in canonical_df.iterrows():
            address = self.address_service.normalize(
                normalize_text(row.get("address")),
                postal_code=normalize_text(row.get("postal_code")),
                region=normalize_text(row.get("region")),
                district=normalize_text(row.get("district")),
                city=normalize_text(row.get("city")),
                settlement=normalize_text(row.get("settlement")),
                street=normalize_text(row.get("street")),
                building=normalize_text(row.get("building")),
                floor=normalize_text(row.get("floor")),
                office=normalize_text(row.get("office")),
                block=normalize_text(row.get("block")),
                structure=normalize_text(row.get("structure")),
                room=normalize_text(row.get("room")),
            )
            name = self._resolve_name(row)
            category = self._resolve_category(row)
            inn_value = self._resolve_inn_value(row)
            parsed_row = ParsedImportRow(
                source_row_index=int(index) + 2,
                postal_code=normalize_text(row.get("postal_code")),
                region=normalize_text(row.get("region")),
                address=address,
                district=normalize_text(row.get("district")),
                city=normalize_text(row.get("city")),
                settlement=normalize_text(row.get("settlement")),
                street=normalize_text(row.get("street")),
                building=normalize_text(row.get("building")),
                floor=normalize_text(row.get("floor")),
                office=normalize_text(row.get("office")),
                block=normalize_text(row.get("block")),
                structure=normalize_text(row.get("structure")),
                room=normalize_text(row.get("room")),
                cadastral_number=normalize_text(row.get("cadastral_number")),
                area=to_float(row.get("area")),
                floors=to_int(row.get("floors")),
                purpose=normalize_text(row.get("purpose")),
                object_type=normalize_text(row.get("object_type")),
                name=name,
                category=category,
                waste_type=normalize_text(row.get("waste_type")),
                waste_generation_norm=normalize_text(row.get("waste_generation_norm")),
                calculation_unit=normalize_text(row.get("calculation_unit")),
                calculation_value=normalize_text(row.get("calculation_value")),
                billing_method=normalize_text(row.get("billing_method")),
                inn=inn_value,
                contract_number=normalize_text(row.get("contract_number")),
                contract_date=parse_date(row.get("contract_date")),
                legal_entity_name=normalize_text(row.get("legal_entity_name")),
                contact_person=normalize_text(row.get("contact_person")),
                phone=normalize_text(row.get("phone")),
                email=normalize_text(row.get("email")),
            )
            if contract_matcher is not None:
                contract_data = contract_matcher.match(parsed_row)
                if contract_data is not None:
                    self._enrich_from_contract(parsed_row, contract_data)
                    contracts_matched += 1
            prepared_rows.append(parsed_row)

        address_keys = {
            address_key
            for row in prepared_rows
            if row.address and (address_key := normalize_address_key(row.address))
        }
        inns = {row.inn for row in prepared_rows if row.inn and "|" not in row.inn}

        real_estates = RealEstateRepository.get_by_address_keys(db, address_keys)
        legal_entities = LegalEntityRepository.get_by_inns(db, inns)

        real_estates_created = 0
        legal_entities_created = 0
        waste_objects_created = 0
        skipped_rows = 0
        waste_object_cache: dict[int, dict[tuple[str, str, str], list]] = {}

        for row in prepared_rows:
            address_key = normalize_address_key(row.address)
            if not address_key or not row.address:
                skipped_rows += 1
                continue

            real_estate = real_estates.get(address_key)
            if real_estate is None:
                real_estate = RealEstateRepository.create(
                    db,
                    address=row.address,
                    address_key=address_key,
                    district=row.district,
                    city=row.city or row.settlement or row.region,
                    street=row.street,
                    building=self._compose_building(row),
                    cadastral_number=row.cadastral_number,
                    area=row.area,
                    floors=row.floors,
                    purpose=row.purpose,
                    object_type=row.object_type,
                )
                real_estates[address_key] = real_estate
                real_estates_created += 1
            else:
                self._fill_real_estate(real_estate, row)

            legal_entity = self._resolve_legal_entity(db, legal_entities, row)
            if legal_entity and legal_entity.inn not in legal_entities:
                legal_entities[legal_entity.inn] = legal_entity
                legal_entities_created += 1

            waste_signature = self._build_waste_signature(
                name=row.name,
                category=row.category,
                inn=row.inn,
            )
            cached_by_signature = waste_object_cache.get(real_estate.id)
            if cached_by_signature is None:
                cached_by_signature = self._build_waste_cache(
                    WasteObjectRepository.list_by_real_estate_id(db, real_estate.id)
                )
                waste_object_cache[real_estate.id] = cached_by_signature

            existing_group = cached_by_signature.get(waste_signature, [])
            if existing_group:
                waste_object = existing_group[0]
                if len(existing_group) > 1:
                    for duplicate in existing_group[1:]:
                        self._fill_waste_object_from_existing(waste_object, duplicate)
                        db.delete(duplicate)
                    cached_by_signature[waste_signature] = [waste_object]

                self._fill_waste_object(
                    waste_object=waste_object,
                    row=row,
                    legal_entity_id=legal_entity.id if legal_entity else None,
                )
            else:
                waste_object = WasteObjectRepository.create(
                    db,
                    real_estate_id=real_estate.id,
                    legal_entity_id=legal_entity.id if legal_entity else None,
                    name=row.name,
                    category=row.category,
                    waste_type=row.waste_type,
                    waste_generation_norm=row.waste_generation_norm,
                    calculation_unit=row.calculation_unit,
                    calculation_value=row.calculation_value,
                    billing_method=row.billing_method,
                    inn=row.inn,
                    contract_number=row.contract_number,
                    contract_date=row.contract_date,
                    contract_start_date=getattr(row, "contract_start_date", None),
                    comment=getattr(row, "comment", None),
                    source_row_index=row.source_row_index,
                )
                cached_by_signature[waste_signature] = [waste_object]
                waste_objects_created += 1

        db.commit()

        return ImportResult(
            processed_rows=len(prepared_rows),
            unique_addresses=len(address_keys),
            real_estates_created=real_estates_created,
            waste_objects_created=waste_objects_created,
            legal_entities_created=legal_entities_created,
            skipped_rows=skipped_rows,
            contracts_loaded=contracts_loaded,
            contracts_matched=contracts_matched,
        )

    def _fill_real_estate(self, real_estate: RealEstate, row: ParsedImportRow) -> None:
        self._assign_if_empty(real_estate, "district", row.district)
        self._assign_if_empty(real_estate, "city", row.city or row.settlement or row.region)
        self._assign_if_empty(real_estate, "street", row.street)
        self._assign_if_empty(real_estate, "building", self._compose_building(row))
        self._assign_if_empty(real_estate, "cadastral_number", row.cadastral_number)
        self._assign_if_empty(real_estate, "area", row.area)
        self._assign_if_empty(real_estate, "floors", row.floors)
        self._assign_if_empty(real_estate, "purpose", row.purpose)
        self._assign_if_empty(real_estate, "object_type", row.object_type)

    def _fill_waste_object(self, waste_object, row: ParsedImportRow, legal_entity_id: Optional[int]) -> None:
        self._assign_if_empty(waste_object, "name", row.name)
        self._assign_if_empty(waste_object, "category", row.category)
        self._assign_if_empty(waste_object, "waste_type", row.waste_type)
        self._assign_if_empty(waste_object, "waste_generation_norm", row.waste_generation_norm)
        self._assign_if_empty(waste_object, "calculation_unit", row.calculation_unit)
        self._assign_if_empty(waste_object, "calculation_value", row.calculation_value)
        self._assign_if_empty(waste_object, "billing_method", row.billing_method)
        self._assign_if_empty(waste_object, "inn", row.inn)
        self._assign_if_empty(waste_object, "contract_number", row.contract_number)
        self._assign_if_empty(waste_object, "contract_date", row.contract_date)
        self._assign_if_empty(waste_object, "contract_start_date", getattr(row, "contract_start_date", None))
        self._assign_if_empty(waste_object, "comment", getattr(row, "comment", None))
        self._assign_if_empty(waste_object, "legal_entity_id", legal_entity_id)

    def _fill_waste_object_from_existing(self, target, source) -> None:
        self._assign_if_empty(target, "name", source.name)
        self._assign_if_empty(target, "category", source.category)
        self._assign_if_empty(target, "waste_type", source.waste_type)
        self._assign_if_empty(target, "waste_generation_norm", source.waste_generation_norm)
        self._assign_if_empty(target, "calculation_unit", source.calculation_unit)
        self._assign_if_empty(target, "calculation_value", source.calculation_value)
        self._assign_if_empty(target, "billing_method", source.billing_method)
        self._assign_if_empty(target, "inn", source.inn)
        self._assign_if_empty(target, "contract_number", source.contract_number)
        self._assign_if_empty(target, "contract_date", source.contract_date)
        self._assign_if_empty(target, "contract_start_date", source.contract_start_date)
        self._assign_if_empty(target, "comment", source.comment)
        self._assign_if_empty(target, "legal_entity_id", source.legal_entity_id)

    def _resolve_legal_entity(
        self,
        db: Session,
        legal_entities: dict[str, LegalEntity],
        row: ParsedImportRow,
    ) -> Optional[LegalEntity]:
        if not row.inn:
            return None
        if "|" in row.inn:
            return None

        legal_entity = legal_entities.get(row.inn)
        if legal_entity is None:
            return LegalEntityRepository.create(
                db,
                inn=row.inn,
                name=row.legal_entity_name or row.name,
                contact_person=row.contact_person,
                phone=row.phone,
                email=row.email,
            )

        self._assign_if_empty(legal_entity, "name", row.legal_entity_name or row.name)
        self._assign_if_empty(legal_entity, "contact_person", row.contact_person)
        self._assign_if_empty(legal_entity, "phone", row.phone)
        self._assign_if_empty(legal_entity, "email", row.email)
        return legal_entity

    @staticmethod
    def _resolve_name(row) -> Optional[str]:
        return (
            normalize_text(row.get("name"))
            or normalize_text(row.get("legal_entity_name"))
            or normalize_text(row.get("object_type"))
        )

    @staticmethod
    def _resolve_category(row) -> Optional[str]:
        return normalize_text(row.get("category")) or normalize_text(row.get("object_type"))

    @staticmethod
    def _compose_building(row: ParsedImportRow) -> Optional[str]:
        parts = [
            normalize_text(row.building),
            normalize_text(row.floor),
            normalize_text(row.office),
            normalize_text(row.block),
            normalize_text(row.structure),
            normalize_text(row.room),
        ]
        parts = [part for part in parts if part]
        if not parts:
            return None
        return ", ".join(parts)

    @staticmethod
    def _build_waste_signature(name: Optional[str], category: Optional[str], inn: Optional[str]) -> tuple[str, str, str]:
        return (
            (normalize_text(name) or "").lower(),
            (normalize_text(category) or "").lower(),
            normalize_text(inn) or "",
        )

    def _build_waste_cache(self, waste_objects: list) -> dict[tuple[str, str, str], list]:
        grouped: dict[tuple[str, str, str], list] = {}
        for waste_object in waste_objects:
            signature = self._build_waste_signature(
                name=waste_object.name,
                category=waste_object.category,
                inn=waste_object.inn,
            )
            grouped.setdefault(signature, []).append(waste_object)
        return grouped

    @staticmethod
    def _resolve_inn_value(row) -> Optional[str]:
        raw_values = [
            row.get("inn"),
            row.get("inn_1"),
            row.get("inn_2"),
            row.get("inn_3"),
            row.get("inn_4"),
            row.get("inn_5"),
        ]
        candidates = ImportService._extract_inn_candidates(raw_values)
        if not candidates:
            return None
        return "|".join(candidates)

    @staticmethod
    def _extract_inn_candidates(values: list[object]) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()

        for value in values:
            if value is None:
                continue

            if isinstance(value, str):
                chunks = re.split(r"[|,;/]+", value)
            else:
                chunks = [value]

            for chunk in chunks:
                inn = normalize_inn(chunk)
                if not inn or inn in seen:
                    continue
                seen.add(inn)
                candidates.append(inn)

        return candidates

    @staticmethod
    def _assign_if_empty(entity: Union[RealEstate, LegalEntity], field_name: str, value) -> None:
        if getattr(entity, field_name, None) in (None, "") and value not in (None, ""):
            setattr(entity, field_name, value)

    @staticmethod
    def _enrich_from_contract(row: ParsedImportRow, contract_data) -> None:
        if not row.contract_number and contract_data.contract_number:
            row.contract_number = contract_data.contract_number
        if not row.contract_date and contract_data.contract_date:
            row.contract_date = contract_data.contract_date
        if not row.legal_entity_name and contract_data.legal_entity_name:
            row.legal_entity_name = contract_data.legal_entity_name
        if not row.name and contract_data.waste_object_name:
            row.name = contract_data.waste_object_name
        if not row.contact_person and contract_data.contact_person:
            row.contact_person = contract_data.contact_person
        if not row.calculation_value and contract_data.calculation_value:
            row.calculation_value = contract_data.calculation_value
        if not row.calculation_unit and contract_data.calculation_unit:
            row.calculation_unit = contract_data.calculation_unit
        if not row.billing_method and contract_data.billing_method:
            row.billing_method = contract_data.billing_method
        if not row.waste_generation_norm and contract_data.waste_generation_norm:
            row.waste_generation_norm = contract_data.waste_generation_norm
        row.contract_start_date = getattr(contract_data, "contract_start_date", None)
        row.comment = getattr(contract_data, "comment", None)
