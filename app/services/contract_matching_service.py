from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd

from app.schemas.imports import ContractMatchData, ParsedImportRow
from app.services.address_normalization_service import AddressNormalizationService
from app.utils.dates import parse_date
from app.utils.normalization import normalize_inn, normalize_text


@dataclass
class ContractRecord:
    contract_number: Optional[str]
    contract_date: Optional[date]
    legal_entity_name: Optional[str]
    waste_object_name: Optional[str]
    inn: Optional[str]
    address: Optional[str]
    locality: Optional[str]
    street: Optional[str]
    building: Optional[str]
    room: Optional[str]
    volume: Optional[str]
    pickup_frequency: Optional[str]
    contact_person: Optional[str]
    contract_start_date: Optional[date]
    comment: Optional[str]
    search_key: Optional[str]


class ContractMatchingService:
    COLUMN_ALIASES: dict[str, list[str]] = {
        "contract_number": ["№", "№ ", "номер", "номер договора"],
        "contract_date": ["дата", "дата договора"],
        "legal_entity_name": ["наименование потребителя"],
        "waste_object_name": ["наименование иоо"],
        "inn": ["инн"],
        "address": ["адрес объекта"],
        "district": ["район"],
        "locality_type": ["тип населенного пункта"],
        "locality": ["населенный пункт"],
        "street_type": ["тип улицы"],
        "street": ["улица"],
        "building": ["дом"],
        "room_type": ["тип пом"],
        "room": ["помещение"],
        "volume": ["объем", "объём"],
        "pickup_frequency": ["периодичность вывоза"],
        "contact_person": ["контактное лицо"],
        "comment": ["комментарии"],
        "contract_start_date": ["дата начала"],
    }

    def __init__(self) -> None:
        self.address_service = AddressNormalizationService()

    def build_matcher(self, dataframe: pd.DataFrame) -> "ContractMatcher":
        canonical_df = self._canonicalize_contract_dataframe(dataframe)
        records: list[ContractRecord] = []

        for _, row in canonical_df.iterrows():
            locality = self._compose_locality(
                normalize_text(row.get("locality_type")),
                normalize_text(row.get("locality")),
            )
            street = self._compose_street(
                normalize_text(row.get("street_type")),
                normalize_text(row.get("street")),
            )
            room = self._compose_room(
                normalize_text(row.get("room_type")),
                normalize_text(row.get("room")),
            )
            search_key = self.address_service.build_search_key(
                locality=locality,
                street=street,
                building=normalize_text(row.get("building")),
                room=room,
            )
            records.append(
                ContractRecord(
                    contract_number=normalize_text(row.get("contract_number")),
                    contract_date=parse_date(row.get("contract_date")),
                    legal_entity_name=normalize_text(row.get("legal_entity_name")),
                    waste_object_name=normalize_text(row.get("waste_object_name")),
                    inn=normalize_inn(row.get("inn")),
                    address=normalize_text(row.get("address")),
                    locality=locality,
                    street=street,
                    building=normalize_text(row.get("building")),
                    room=room,
                    volume=normalize_text(row.get("volume")),
                    pickup_frequency=normalize_text(row.get("pickup_frequency")),
                    contact_person=normalize_text(row.get("contact_person")),
                    contract_start_date=parse_date(row.get("contract_start_date")),
                    comment=normalize_text(row.get("comment")),
                    search_key=search_key,
                )
            )

        return ContractMatcher(records=records, address_service=self.address_service)

    def _canonicalize_contract_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        normalized_columns = {self._normalize_header(column): str(column) for column in df.columns}
        renamed = df.copy()

        for target, aliases in self.COLUMN_ALIASES.items():
            for alias in aliases:
                normalized_alias = self._normalize_header(alias)
                if normalized_alias in normalized_columns:
                    renamed = renamed.rename(columns={normalized_columns[normalized_alias]: target})
                    break

        for target in self.COLUMN_ALIASES:
            if target not in renamed.columns:
                renamed[target] = None

        return renamed[list(self.COLUMN_ALIASES.keys())]

    @staticmethod
    def _normalize_header(value: object) -> str:
        text = normalize_text(value) or ""
        text = text.replace("№", "num")
        return "".join(ch.lower().replace("ё", "е") if ch.isalnum() or ch == "_" else "_" for ch in text).strip("_")

    @staticmethod
    def _compose_locality(locality_type: Optional[str], locality: Optional[str]) -> Optional[str]:
        parts = [part for part in (locality_type, locality) if part]
        return " ".join(parts) if parts else None

    @staticmethod
    def _compose_street(street_type: Optional[str], street: Optional[str]) -> Optional[str]:
        parts = [part for part in (street_type, street) if part]
        return " ".join(parts) if parts else None

    @staticmethod
    def _compose_room(room_type: Optional[str], room: Optional[str]) -> Optional[str]:
        parts = [part for part in (room_type, room) if part]
        return " ".join(parts) if parts else None


class ContractMatcher:
    def __init__(self, records: list[ContractRecord], address_service: AddressNormalizationService) -> None:
        self.records = records
        self.address_service = address_service
        self.by_inn_and_key: dict[tuple[str, str], ContractRecord] = {}
        self.by_key: dict[str, list[ContractRecord]] = defaultdict(list)
        self.by_inn: dict[str, list[ContractRecord]] = defaultdict(list)

        for record in records:
            if record.search_key:
                self.by_key[record.search_key].append(record)
            if record.inn:
                self.by_inn[record.inn].append(record)
            if record.inn and record.search_key:
                self.by_inn_and_key[(record.inn, record.search_key)] = record

    def match(self, row: ParsedImportRow) -> Optional[ContractMatchData]:
        inns = [part for part in (row.inn or "").split("|") if part]
        search_key = self.address_service.build_search_key(
            locality=row.city or row.settlement or row.district,
            street=row.street,
            building=row.building,
            office=row.office,
            room=row.room,
        )

        if search_key:
            for inn in inns:
                matched = self.by_inn_and_key.get((inn, search_key))
                if matched:
                    return self._to_match_data(matched)

            key_records = self.by_key.get(search_key, [])
            if len(key_records) == 1:
                return self._to_match_data(key_records[0])

        if len(inns) == 1:
            inn_records = self.by_inn.get(inns[0], [])
            if len(inn_records) == 1:
                return self._to_match_data(inn_records[0])

        return None

    @staticmethod
    def _to_match_data(record: ContractRecord) -> ContractMatchData:
        return ContractMatchData(
            contract_number=record.contract_number,
            contract_date=record.contract_date,
            legal_entity_name=record.legal_entity_name,
            waste_object_name=record.waste_object_name,
            contact_person=record.contact_person,
            calculation_value=record.volume,
            calculation_unit="м3" if record.volume else None,
            waste_generation_norm=record.pickup_frequency,
            billing_method=record.pickup_frequency,
            contract_start_date=record.contract_start_date,
            comment=record.comment,
        )
