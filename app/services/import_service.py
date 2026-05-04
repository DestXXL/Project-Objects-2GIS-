from __future__ import annotations

import re
from collections import defaultdict
from typing import Callable, Optional, Union

from sqlalchemy.orm import Session

from app.models import ContractRow, LegalEntity, RealEstate
from app.repositories.contract_row_repository import ContractRowRepository
from app.repositories.legal_entity_repository import LegalEntityRepository
from app.repositories.real_estate_repository import RealEstateRepository
from app.repositories.waste_object_repository import WasteObjectRepository
from app.schemas.imports import ContractLinkResult, ImportResult, ParsedImportRow
from app.services.address_normalization_service import AddressNormalizationService
from app.services.contract_matching_service import (
    CONTRACT_LINK_STRATEGY_LABELS,
    ContractMatcher,
    ContractMatchingService,
)
from app.services.import_mapping import canonicalize_dataframe
from app.utils.dates import parse_date
from app.utils.normalization import (
    normalize_address_key,
    normalize_inn,
    normalize_text,
    split_normalized_inns,
    to_float,
    to_int,
)


class ImportService:
    def __init__(self) -> None:
        self.address_service = AddressNormalizationService()
        self.contract_service = ContractMatchingService()

    def import_dataframe(
        self,
        db: Session,
        dataframe,
        contract_dataframe=None,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> ImportResult:
        canonical_df, _ = canonicalize_dataframe(dataframe)
        contract_matcher: Optional[ContractMatcher] = None
        contracts_loaded = 0
        contracts_matched = 0
        contracts_unmatched = 0
        gis_rows_linked_to_contract = 0
        main_rows_with_contract_number = 0
        main_unique_contract_numbers: set[str] = set()
        contract_match_summary: dict[str, int] = defaultdict(int)
        contract_unmatched_summary: dict[str, int] = defaultdict(int)

        ContractRowRepository.delete_all(db)

        if contract_dataframe is not None:
            self._notify_progress(progress_callback, "contracts", "Подготовка файла договоров")
            contract_matcher = self.contract_service.build_matcher(contract_dataframe)
            contracts_loaded = len(contract_matcher.records)

        prepared_rows: list[ParsedImportRow] = []
        raw_rows = canonical_df.to_dict(orient="records")
        total_rows = len(raw_rows)
        self._notify_progress(progress_callback, "prepare", "Подготовка строк к импорту", 0, total_rows)
        for index, row in enumerate(raw_rows):
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
            source_contract_number = normalize_text(row.get("contract_number"))
            source_contract_date = parse_date(row.get("contract_date"))
            parsed_row = ParsedImportRow.model_construct(
                source_row_index=index + 2,
                source_inn=inn_value,
                source_contract_number=source_contract_number,
                source_contract_date=source_contract_date,
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
                contract_number=None,
                contract_date=None,
                legal_entity_name=normalize_text(row.get("legal_entity_name")),
                contact_person=normalize_text(row.get("contact_person")),
                phone=normalize_text(row.get("phone")),
                email=normalize_text(row.get("email")),
            )
            prepared_rows.append(parsed_row)
            if source_contract_number:
                main_rows_with_contract_number += 1
                main_unique_contract_numbers.add(source_contract_number)
            if index == 0 or (index + 1) % 250 == 0 or index + 1 == total_rows:
                self._notify_progress(
                    progress_callback,
                    "prepare",
                    "Подготовка строк к импорту",
                    index + 1,
                    total_rows,
                )

        self._hydrate_existing_contract_link_metadata(db, prepared_rows)

        if contract_matcher is not None:
            self._notify_progress(progress_callback, "match", "Сопоставление договоров и объектов", 0, len(prepared_rows))
            assignment_batch = contract_matcher.assign_rows(prepared_rows)
            contracts_matched = assignment_batch.matched_contracts
            contracts_unmatched = assignment_batch.unmatched_contracts
            contract_match_summary = defaultdict(int, assignment_batch.match_summary)
            contract_unmatched_summary = defaultdict(int, assignment_batch.unmatched_summary)
            gis_rows_linked_to_contract = sum(
                1
                for link_result in assignment_batch.row_results.values()
                if link_result.matched and link_result.status == "matched"
            )

            for row in prepared_rows:
                link_result = assignment_batch.row_results.get(
                    row.source_row_index,
                    ContractLinkResult(
                        matched=False,
                        status="unmatched",
                        strategy=None,
                        reason="Для строки 2ГИС подходящий договор не найден.",
                    ),
                )
                self._apply_contract_link_result(row, link_result)
                if link_result.matched and link_result.data is not None:
                    self._enrich_from_contract(row, link_result.data)
            self._notify_progress(progress_callback, "match", "Сопоставление договоров и объектов", len(prepared_rows), len(prepared_rows))
        else:
            for row in prepared_rows:
                self._apply_contract_link_result(
                    row,
                    ContractLinkResult(
                        matched=False,
                        status="not_checked",
                        strategy=None,
                        reason="Файл договоров не загружен, поэтому привязка не выполнялась.",
                    ),
                )

        address_keys = {
            address_key
            for row in prepared_rows
            if row.address and (address_key := normalize_address_key(row.address))
        }
        inns = {inn for row in prepared_rows for inn in self._split_row_inns(row.source_inn)}

        real_estates = RealEstateRepository.get_by_address_keys(db, address_keys)
        legal_entities = LegalEntityRepository.get_by_inns(db, inns)

        real_estates_created = 0
        legal_entities_created = 0
        waste_objects_created = 0
        skipped_rows = 0

        with db.no_autoflush:
            self._notify_progress(progress_callback, "entities", "Подготовка объектов и юрлиц", 0, len(prepared_rows))
            for index, row in enumerate(prepared_rows):
                created_entities_count = self._ensure_legal_entities(db, legal_entities, row, flush=False)
                legal_entities_created += created_entities_count

                address_key = normalize_address_key(row.address)
                if not address_key or not row.address:
                    if index == 0 or (index + 1) % 250 == 0 or index + 1 == len(prepared_rows):
                        self._notify_progress(
                            progress_callback,
                            "entities",
                            "Подготовка объектов и юрлиц",
                            index + 1,
                            len(prepared_rows),
                        )
                    continue

                real_estate = real_estates.get(address_key)
                if real_estate is None:
                    real_estate = RealEstateRepository.create(
                        db,
                        flush=False,
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

                if index == 0 or (index + 1) % 250 == 0 or index + 1 == len(prepared_rows):
                    self._notify_progress(
                        progress_callback,
                        "entities",
                        "Подготовка объектов и юрлиц",
                        index + 1,
                        len(prepared_rows),
                    )

            db.flush()
            waste_object_cache = self._prepare_existing_waste_object_cache(db, real_estates)
            waste_objects_by_source_row_index: dict[int, object] = {}

            self._notify_progress(progress_callback, "write", "Сохранение объектов отходов", 0, len(prepared_rows))
            for row in prepared_rows:
                address_key = normalize_address_key(row.address)
                if not address_key or not row.address:
                    skipped_rows += 1
                    continue

                real_estate = real_estates.get(address_key)
                if real_estate is None:
                    skipped_rows += 1
                    continue

                legal_entity = self._get_primary_legal_entity(legal_entities, row)
                cached_by_row_index = waste_object_cache.setdefault(real_estate.id, {})
                existing_group = cached_by_row_index.get(row.source_row_index, [])
                if existing_group:
                    waste_object = existing_group[0]
                    if len(existing_group) > 1:
                        for duplicate in existing_group[1:]:
                            self._fill_waste_object_from_existing(waste_object, duplicate)
                            db.delete(duplicate)
                        cached_by_row_index[row.source_row_index] = [waste_object]

                    self._fill_waste_object(
                        waste_object=waste_object,
                        row=row,
                        legal_entity_id=legal_entity.id if legal_entity else None,
                    )
                else:
                    waste_object = WasteObjectRepository.create(
                        db,
                        flush=False,
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
                        source_contract_number=row.source_contract_number,
                        source_contract_date=row.source_contract_date,
                        contract_number=row.contract_number,
                        contract_date=row.contract_date,
                        contract_start_date=getattr(row, "contract_start_date", None),
                        comment=getattr(row, "comment", None),
                        contract_link_status=row.contract_link_status,
                        contract_link_strategy=row.contract_link_strategy,
                        contract_link_reason=row.contract_link_reason,
                        contract_link_score=row.contract_link_score,
                        source_row_index=row.source_row_index,
                    )
                    cached_by_row_index[row.source_row_index] = [waste_object]
                    waste_objects_created += 1
                waste_objects_by_source_row_index[row.source_row_index] = waste_object
                processed = row.source_row_index - 1
                if processed == 1 or processed % 250 == 0 or processed == len(prepared_rows):
                    self._notify_progress(
                        progress_callback,
                        "write",
                        "Сохранение объектов отходов",
                        min(processed, len(prepared_rows)),
                        len(prepared_rows),
                    )

            if contract_matcher is not None:
                db.flush()
                self._persist_contract_rows(
                    db=db,
                    assignment_batch=assignment_batch,
                    waste_objects_by_source_row_index=waste_objects_by_source_row_index,
                )

        self._notify_progress(progress_callback, "commit", "Фиксация изменений в базе данных")
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
            contracts_unmatched=contracts_unmatched,
            contract_rows_matched=contracts_matched,
            gis_rows_linked_to_contract=gis_rows_linked_to_contract,
            main_rows_with_contract_number=main_rows_with_contract_number,
            main_unique_contract_numbers=len(main_unique_contract_numbers),
            contract_match_summary=dict(contract_match_summary),
            contract_unmatched_summary=dict(contract_unmatched_summary),
        )

    def _persist_contract_rows(
        self,
        db: Session,
        assignment_batch,
        waste_objects_by_source_row_index: dict[int, object],
    ) -> None:
        for contract_result in assignment_batch.contract_results:
            record = contract_result.record
            result = contract_result.result
            linked_waste_object_id = None
            if contract_result.matched_row_source_index is not None:
                linked_waste_object = waste_objects_by_source_row_index.get(contract_result.matched_row_source_index)
                if linked_waste_object is not None:
                    linked_waste_object_id = linked_waste_object.id

            ContractRowRepository.create(
                db,
                flush=False,
                source_row_index=record.source_row_index,
                contract_number=record.contract_number,
                contract_date=record.contract_date,
                legal_entity_name=record.legal_entity_name,
                waste_object_name=record.waste_object_name,
                inn=record.inn,
                address=self._compose_contract_row_address(record),
                compact_address=record.compact_address,
                district=record.district,
                locality=record.locality,
                street=record.street,
                building=record.building,
                room=record.room,
                material=record.material,
                volume=record.volume,
                quantity=record.quantity,
                pickup_frequency=record.pickup_frequency,
                contact_person=record.contact_person,
                comment=record.comment,
                contract_start_date=record.contract_start_date,
                contract_link_status=result.status,
                contract_link_strategy=result.strategy,
                contract_link_reason=result.reason,
                linked_waste_object_id=linked_waste_object_id,
                link_mode="auto" if linked_waste_object_id is not None else "none",
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
        self._reconcile_contract_enrichment(waste_object, row)
        self._assign_if_present(waste_object, "name", row.name)
        self._assign_if_present(waste_object, "category", row.category)
        self._assign_if_empty(waste_object, "waste_type", row.waste_type)
        self._assign_if_empty(waste_object, "waste_generation_norm", row.waste_generation_norm)
        self._assign_if_empty(waste_object, "calculation_unit", row.calculation_unit)
        self._assign_if_empty(waste_object, "calculation_value", row.calculation_value)
        self._assign_if_empty(waste_object, "billing_method", row.billing_method)
        self._assign_if_empty(waste_object, "inn", row.inn)
        self._assign_if_empty(waste_object, "source_contract_number", row.source_contract_number)
        self._assign_if_empty(waste_object, "source_contract_date", row.source_contract_date)
        if self._is_exact_auto_match(row):
            self._assign_if_present(waste_object, "contract_number", row.contract_number)
            self._assign_if_present(waste_object, "contract_date", row.contract_date)
            self._assign_if_present(
                waste_object,
                "contract_start_date",
                getattr(row, "contract_start_date", None),
            )
            self._assign_if_present(waste_object, "comment", getattr(row, "comment", None))
        else:
            self._assign_if_empty(waste_object, "contract_number", row.contract_number)
            self._assign_if_empty(waste_object, "contract_date", row.contract_date)
            self._assign_if_empty(waste_object, "contract_start_date", getattr(row, "contract_start_date", None))
            self._assign_if_empty(waste_object, "comment", getattr(row, "comment", None))
        self._assign_if_empty(waste_object, "legal_entity_id", legal_entity_id)
        self._update_contract_link_metadata(waste_object, row)

    def _fill_waste_object_from_existing(self, target, source) -> None:
        self._assign_if_empty(target, "name", source.name)
        self._assign_if_empty(target, "category", source.category)
        self._assign_if_empty(target, "waste_type", source.waste_type)
        self._assign_if_empty(target, "waste_generation_norm", source.waste_generation_norm)
        self._assign_if_empty(target, "calculation_unit", source.calculation_unit)
        self._assign_if_empty(target, "calculation_value", source.calculation_value)
        self._assign_if_empty(target, "billing_method", source.billing_method)
        self._assign_if_empty(target, "inn", source.inn)
        self._assign_if_empty(target, "source_contract_number", source.source_contract_number)
        self._assign_if_empty(target, "source_contract_date", source.source_contract_date)
        self._assign_if_empty(target, "contract_number", source.contract_number)
        self._assign_if_empty(target, "contract_date", source.contract_date)
        self._assign_if_empty(target, "contract_start_date", source.contract_start_date)
        self._assign_if_empty(target, "comment", source.comment)
        self._assign_if_empty(target, "legal_entity_id", source.legal_entity_id)
        self._assign_if_empty(target, "contract_link_status", source.contract_link_status)
        self._assign_if_empty(target, "contract_link_strategy", source.contract_link_strategy)
        self._assign_if_empty(target, "contract_link_reason", source.contract_link_reason)
        self._assign_if_empty(target, "contract_link_score", source.contract_link_score)

    @staticmethod
    def _apply_contract_link_result(row: ParsedImportRow, result: ContractLinkResult) -> None:
        row.contract_link_status = result.status
        row.contract_link_strategy = result.strategy
        row.contract_link_reason = result.reason
        row.contract_link_score = result.score

    @staticmethod
    def _update_contract_link_metadata(waste_object, row: ParsedImportRow) -> None:
        incoming_status = row.contract_link_status
        if incoming_status is None:
            return

        current_status = getattr(waste_object, "contract_link_status", None)
        if incoming_status == "not_checked" and current_status not in (None, ""):
            return

        waste_object.contract_link_status = incoming_status
        waste_object.contract_link_strategy = row.contract_link_strategy
        waste_object.contract_link_reason = row.contract_link_reason
        waste_object.contract_link_score = row.contract_link_score

    @staticmethod
    def _describe_strategy(strategy: str) -> str:
        return CONTRACT_LINK_STRATEGY_LABELS.get(strategy, strategy)

    def _resolve_legal_entities(
        self,
        db: Session,
        legal_entities: dict[str, LegalEntity],
        row: ParsedImportRow,
        flush: bool = True,
    ) -> tuple[Optional[LegalEntity], int]:
        row_inns = self._split_row_inns(row.source_inn)
        if not row_inns:
            return None, 0

        created_count = 0
        resolved_entities: list[LegalEntity] = []
        for inn in row_inns:
            legal_entity = legal_entities.get(inn)
            if legal_entity is None:
                legal_entity = LegalEntityRepository.create(
                    db,
                    flush=flush,
                    inn=inn,
                    name=row.legal_entity_name or row.name,
                    contact_person=row.contact_person,
                    phone=row.phone,
                    email=row.email,
                )
                legal_entities[inn] = legal_entity
                created_count += 1
            else:
                self._assign_if_empty(legal_entity, "name", row.legal_entity_name or row.name)
                self._assign_if_empty(legal_entity, "contact_person", row.contact_person)
                self._assign_if_empty(legal_entity, "phone", row.phone)
                self._assign_if_empty(legal_entity, "email", row.email)
            resolved_entities.append(legal_entity)
        return resolved_entities[0] if resolved_entities else None, created_count

    def _ensure_legal_entities(
        self,
        db: Session,
        legal_entities: dict[str, LegalEntity],
        row: ParsedImportRow,
        flush: bool = True,
    ) -> int:
        _entity, created_count = self._resolve_legal_entities(db, legal_entities, row, flush=flush)
        return created_count

    def _get_primary_legal_entity(
        self,
        legal_entities: dict[str, LegalEntity],
        row: ParsedImportRow,
    ) -> Optional[LegalEntity]:
        row_inns = self._split_row_inns(row.source_inn)
        if not row_inns:
            return None
        return legal_entities.get(row_inns[0])

    @staticmethod
    def _resolve_name(row) -> Optional[str]:
        return (
            normalize_text(row.get("name"))
            or normalize_text(row.get("legal_entity_name"))
            or normalize_text(row.get("object_type"))
        )

    @staticmethod
    def _resolve_category(row) -> Optional[str]:
        # Категория объекта отходов должна приходить из основной таблицы.
        # Не подменяем ее типом объекта недвижимости или другими полями.
        return normalize_text(row.get("category"))

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
    def _compose_contract_row_address(record) -> Optional[str]:
        if record.address:
            return record.address
        parts = [part for part in (record.locality, record.street) if part]
        if record.building:
            parts.append(f"д. {record.building}")
        if record.room:
            parts.append(f"пом. {record.room}")
        return ", ".join(parts) if parts else None

    def _build_waste_cache(self, waste_objects: list) -> dict[int, list]:
        grouped: dict[int, list] = {}
        for waste_object in waste_objects:
            grouped.setdefault(waste_object.source_row_index, []).append(waste_object)
        return grouped

    def _prepare_existing_waste_object_cache(
        self,
        db: Session,
        real_estates: dict[str, RealEstate],
    ) -> dict[int, dict[int, list]]:
        real_estate_ids = {entity.id for entity in real_estates.values() if getattr(entity, "id", None) is not None}
        existing_waste_objects = WasteObjectRepository.list_by_real_estate_ids(db, real_estate_ids)
        grouped_by_real_estate: dict[int, list] = defaultdict(list)
        for waste_object in existing_waste_objects:
            grouped_by_real_estate[waste_object.real_estate_id].append(waste_object)

        return {
            real_estate_id: self._build_waste_cache(items)
            for real_estate_id, items in grouped_by_real_estate.items()
        }

    def _hydrate_existing_contract_link_metadata(
        self,
        db: Session,
        prepared_rows: list[ParsedImportRow],
    ) -> None:
        address_keys = {
            address_key
            for row in prepared_rows
            if row.address and (address_key := normalize_address_key(row.address))
        }
        if not address_keys:
            return

        real_estates = RealEstateRepository.get_by_address_keys(db, address_keys)
        waste_object_cache = self._prepare_existing_waste_object_cache(db, real_estates)

        for row in prepared_rows:
            if not row.address:
                continue

            address_key = normalize_address_key(row.address)
            if not address_key:
                continue

            real_estate = real_estates.get(address_key)
            if real_estate is None:
                continue

            by_row_index = waste_object_cache.get(real_estate.id, {})
            existing_group = by_row_index.get(row.source_row_index, [])
            if not existing_group:
                continue

            existing = existing_group[0]
            if not self._is_exact_auto_match(existing):
                continue
            row.contract_link_status = existing.contract_link_status
            row.contract_link_strategy = existing.contract_link_strategy
            row.contract_link_reason = existing.contract_link_reason
            row.contract_link_score = existing.contract_link_score

    @staticmethod
    def _is_exact_auto_match(item) -> bool:
        return getattr(item, "contract_link_status", None) == "matched"

    @classmethod
    def _is_inexact_auto_match(cls, item) -> bool:
        return (
            getattr(item, "contract_link_status", None) == "matched"
            and not cls._is_exact_auto_match(item)
        )

    @classmethod
    def _reconcile_contract_enrichment(cls, waste_object, row: ParsedImportRow) -> None:
        incoming_checked = row.contract_link_status in {"matched", "review_required", "unmatched"}
        if not incoming_checked:
            return

        if cls._is_exact_auto_match(row):
            return

        if not cls._is_inexact_auto_match(waste_object):
            return

        for field_name in (
            "contract_number",
            "contract_date",
            "contract_start_date",
            "comment",
        ):
            setattr(waste_object, field_name, None)

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
    def _split_row_inns(value: Optional[str]) -> list[str]:
        if not value:
            return []
        return split_normalized_inns(value)

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
                normalized_chunk = normalize_inn(chunk)
                extracted = ImportService._split_concatenated_inn(normalized_chunk) if normalized_chunk else []
                if not extracted and normalized_chunk:
                    extracted = [normalized_chunk]

                for inn in extracted:
                    if not inn or inn in seen:
                        continue
                    seen.add(inn)
                    candidates.append(inn)

        return candidates

    @staticmethod
    def _split_concatenated_inn(value: Optional[str]) -> list[str]:
        if not value or not value.isdigit() or len(value) <= 12:
            return []

        solutions: list[list[str]] = []

        def walk(position: int, parts: list[str]) -> None:
            if position == len(value):
                if len(parts) > 1:
                    solutions.append(parts[:])
                return

            for length in (10, 12):
                candidate = value[position : position + length]
                if len(candidate) != length:
                    continue
                walk(position + length, parts + [candidate])

        walk(0, [])

        if len(solutions) != 1:
            return []
        return solutions[0]

    @staticmethod
    def _assign_if_empty(entity: Union[RealEstate, LegalEntity], field_name: str, value) -> None:
        if getattr(entity, field_name, None) in (None, "") and value not in (None, ""):
            setattr(entity, field_name, value)

    @staticmethod
    def _assign_if_present(entity: Union[RealEstate, LegalEntity], field_name: str, value) -> None:
        if value not in (None, ""):
            setattr(entity, field_name, value)

    @staticmethod
    def _enrich_from_contract(row: ParsedImportRow, contract_data) -> None:
        if not row.inn and contract_data.inn:
            row.inn = contract_data.inn
        if not row.address and contract_data.address:
            row.address = contract_data.address
        if not row.city and contract_data.locality:
            row.city = contract_data.locality
        if not row.street and contract_data.street:
            row.street = contract_data.street
        if not row.building and contract_data.building:
            row.building = contract_data.building
        if not row.room and contract_data.room:
            row.room = contract_data.room
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

    @staticmethod
    def _notify_progress(
        callback: Optional[Callable[[dict], None]],
        stage: str,
        message: str,
        current: Optional[int] = None,
        total: Optional[int] = None,
    ) -> None:
        if callback is None:
            return
        callback(
            {
                "stage": stage,
                "message": message,
                "current": current,
                "total": total,
            }
        )
