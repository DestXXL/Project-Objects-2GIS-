from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
import re
from typing import Optional

import pandas as pd

from app.schemas.imports import ContractLinkResult, ContractMatchData, ParsedImportRow
from app.services.address_normalization_service import AddressNormalizationService
from app.utils.dates import parse_date
from app.utils.normalization import normalize_inn, normalize_text, split_normalized_inns, to_float


CONTRACT_LINK_STATUS_LABELS = {
    "matched": "Договор привязан",
    "unmatched": "Договор не найден",
    "review_required": "Нужна ручная проверка",
    "not_checked": "Файл договоров не загружен",
}

CONTRACT_LINK_STRATEGY_LABELS = {
    "city_street_building": "город+улица+дом",
    "name": "имя",
    "inn": "инн",
    "address_plus": "адрес+",
    "address_name_plus": "адрес+имя+",
    "address_name_inn_plus": "адрес+имя+инн+",
    "address_name_minus": "адрес+имя-",
    "address_name_inn_minus": "адрес+имя+инн-",
    "address_name_minus_inn_plus": "адрес+имя-инн+",
    "address_name_minus_inn_minus": "адрес+имя-инн-",
}

NAME_STOPWORDS = {
    "магазин",
    " и",
    " со",
    " по",
}

@dataclass(frozen=True)
class ContractRecord:
    source_row_index: int
    contract_number: Optional[str]
    contract_date: Optional[date]
    legal_entity_name: Optional[str]
    waste_object_name: Optional[str]
    inn: Optional[str]
    address: Optional[str]
    compact_address: Optional[str]
    district: Optional[str]
    locality: Optional[str]
    street: Optional[str]
    building: Optional[str]
    room: Optional[str]
    material: Optional[str]
    volume: Optional[float]
    quantity: Optional[float]
    pickup_frequency: Optional[str]
    contact_person: Optional[str]
    comment: Optional[str]
    contract_start_date: Optional[date]
    name_variants: tuple[str, ...]
    raw_name: Optional[str]
    quoted_name_fragments: tuple[str, ...]
    name_excluded_tokens: frozenset[str]
    inn_keys: frozenset[str]
    address_keys: frozenset[str]
    city_key: str
    street_key: str
    building_key: str


@dataclass
class ContractAssignmentBatch:
    row_results: dict[int, ContractLinkResult]
    contract_results: list["ContractRecordResult"]
    matched_contracts: int
    unmatched_contracts: int
    match_summary: dict[str, int]
    unmatched_summary: dict[str, int]


@dataclass
class ContractRecordResult:
    record: ContractRecord
    result: ContractLinkResult
    matched_row_source_index: Optional[int] = None


@dataclass
class GISSearchState:
    candidate: Optional["GISObjectCandidate"]
    strategy: Optional[str]


@dataclass
class GISObjectCandidate:
    row: ParsedImportRow
    name_variants: tuple[str, ...]
    raw_name: Optional[str]
    name_excluded_tokens: frozenset[str]
    inn_keys: frozenset[str]
    address_keys: frozenset[str]
    city_key: str
    street_key: str
    building_key: str
    already_matched: bool = False
    assigned: bool = False


class ContractMatchingService:
    COLUMN_ALIASES: dict[str, list[str]] = {
        "contract_number": ["№", "№ ", "номер", "номер договора"],
        "contract_date": ["дата", "дата договора"],
        "legal_entity_name": ["наименование потребителя"],
        "waste_object_name": ["наименование иоо"],
        "inn": ["инн"],
        "address": ["адрес объекта"],
        "compact_address": ["compact_address", "unnamed_6"],
        "district": ["район"],
        "locality_type": ["тип населенного пункта"],
        "locality": ["населенный пункт"],
        "street_type": ["тип улицы"],
        "street": ["улица"],
        "building": ["дом"],
        "room_type": ["тип пом"],
        "room": ["помещение"],
        "material": ["материал"],
        "volume": ["объем", "объём"],
        "quantity": ["кол-во", "количество"],
        "pickup_frequency": ["периодичность вывоза", "период вывоза"],
        "contact_person": ["контактное лицо", "контакт"],
        "comment": ["комментарии", "комментарий"],
        "contract_start_date": ["дата начала", "дата начала действия"],
    }

    def __init__(self) -> None:
        self.address_service = AddressNormalizationService()

    def build_matcher(self, dataframe: pd.DataFrame) -> "ContractMatcher":
        canonical_df = self._canonicalize_contract_dataframe(dataframe)
        records: list[ContractRecord] = []

        for index, row in enumerate(canonical_df.to_dict(orient="records"), start=2):
            district = normalize_text(row.get("district"))
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
            inn = normalize_inn(row.get("inn"))
            address = normalize_text(row.get("address"))
            compact_address = normalize_text(row.get("compact_address"))
            waste_object_name = normalize_text(row.get("waste_object_name"))
            legal_entity_name = normalize_text(row.get("legal_entity_name"))

            records.append(
                ContractRecord(
                    source_row_index=index,
                    contract_number=normalize_text(row.get("contract_number")),
                    contract_date=parse_date(row.get("contract_date")),
                    legal_entity_name=legal_entity_name,
                    waste_object_name=waste_object_name,
                    inn=inn,
                    address=address,
                    compact_address=compact_address,
                    district=district,
                    locality=locality,
                    street=street,
                    building=normalize_text(row.get("building")),
                    room=room,
                    material=normalize_text(row.get("material")),
                    volume=to_float(row.get("volume")),
                    quantity=to_float(row.get("quantity")),
                    pickup_frequency=normalize_text(row.get("pickup_frequency")),
                    contact_person=normalize_text(row.get("contact_person")),
                    comment=normalize_text(row.get("comment")),
                    contract_start_date=parse_date(row.get("contract_start_date")),
                    name_variants=self._build_name_variants(waste_object_name, legal_entity_name),
                    raw_name=waste_object_name or legal_entity_name,
                    quoted_name_fragments=self._build_quoted_name_fragments(waste_object_name),
                    name_excluded_tokens=frozenset(
                        self._build_excluded_name_tokens(
                            district,
                            locality,
                            street,
                            normalize_text(row.get("building")),
                            room,
                        )
                    ),
                    inn_keys=self._build_inn_key_set(inn),
                    address_keys=frozenset(
                        self._build_contract_address_keys(
                            address=address,
                            compact_address=compact_address,
                            district=district,
                            locality=locality,
                            street=street,
                            building=normalize_text(row.get("building")),
                            room=room,
                        )
                    ),
                    city_key=self._norm_city_value(locality),
                    street_key=self._norm_street_value(street),
                    building_key=self._norm_building_value(normalize_text(row.get("building"))),
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
        text = text.lower().replace("ё", "е").replace("№", "num")
        text = re.sub(r"[^a-z0-9а-я_]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text

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

    def _norm_city_value(self, value: Optional[str]) -> str:
        return self.address_service._clean_locality(value) or ""

    def _norm_street_value(self, value: Optional[str]) -> str:
        return self.address_service._clean_street(value) or ""

    def _norm_building_value(self, value: Optional[str]) -> str:
        return self.address_service._clean_generic(value) or ""

    def _build_name_variants(self, *values: Optional[str]) -> tuple[str, ...]:
        variants: list[str] = []
        for value in values:
            normalized = self._normalize_name(value)
            if normalized and normalized not in variants:
                variants.append(normalized)
        return tuple(variants)

    def _build_quoted_name_fragments(self, *values: Optional[str]) -> tuple[str, ...]:
        fragments: list[str] = []
        for value in values:
            text = normalize_text(value)
            if not text:
                continue
            for fragment in re.findall(r'"([^"]+)"|«([^»]+)»', text):
                raw_fragment = next((part for part in fragment if part), "")
                normalized = self._normalize_exact_name_fragment(raw_fragment)
                if normalized and normalized not in fragments:
                    fragments.append(normalized)
        return tuple(fragments)

    def _build_inn_key_set(self, value: Optional[str]) -> frozenset[str]:
        return frozenset(self._extract_inn_keys(value))

    @staticmethod
    def _extract_inn_keys(value: Optional[str]) -> set[str]:
        if not value:
            return set()
        keys: set[str] = set()
        text = normalize_text(value) or str(value)
        for match in re.findall(r"\d{9,12}", text):
            keys.add(match)
        for inn in split_normalized_inns(value):
            if 9 <= len(inn) <= 12:
                keys.add(inn)
        return keys

    def _build_contract_address_keys(
        self,
        *,
        address: Optional[str],
        compact_address: Optional[str],
        district: Optional[str],
        locality: Optional[str],
        street: Optional[str],
        building: Optional[str],
        room: Optional[str],
    ) -> set[str]:
        keys: set[str] = set()
        keys.update(self._build_address_keys_from_parts(district=district, locality=locality, street=street, building=building))
        keys.update(self._build_address_keys_from_text(address, default_locality=locality, district=district))
        keys.update(self._build_address_keys_from_text(compact_address, default_locality=locality, district=district))

        freeform_parts = self.address_service.parse_freeform_address(address=address, default_locality=locality)
        if freeform_parts:
            keys.update(
                self._build_address_keys_from_parts(
                    district=district,
                    locality=freeform_parts.get("locality"),
                    street=freeform_parts.get("street"),
                    building=freeform_parts.get("building"),
                )
            )

        compact_parts = self.address_service.parse_compact_address(compact_address)
        if compact_parts:
            keys.update(
                self._build_address_keys_from_parts(
                    district=district,
                    locality=compact_parts.get("locality"),
                    street=compact_parts.get("street"),
                    building=compact_parts.get("building"),
                )
            )

        return {key for key in keys if key}

    def _build_row_address_keys(self, row: ParsedImportRow) -> set[str]:
        keys = self._build_address_keys_from_parts(
            district=row.district,
            locality=row.city or row.settlement or row.region,
            street=row.street,
            building=row.building,
        )
        keys.update(
            self._build_address_keys_from_text(
                row.address,
                default_locality=row.city or row.settlement or row.region,
                district=row.district,
            )
        )

        freeform_parts = self.address_service.parse_freeform_address(
            address=row.address,
            default_locality=row.city or row.settlement or row.region,
        )
        if freeform_parts:
            keys.update(
                self._build_address_keys_from_parts(
                    district=row.district,
                    locality=freeform_parts.get("locality"),
                    street=freeform_parts.get("street"),
                    building=freeform_parts.get("building"),
                )
            )
        return {key for key in keys if key}

    def _build_address_keys_from_text(
        self,
        value: Optional[str],
        *,
        default_locality: Optional[str],
        district: Optional[str],
    ) -> set[str]:
        text = normalize_text(value)
        if not text:
            return set()

        keys: set[str] = set()
        parsed = self.address_service.parse_freeform_address(address=text, default_locality=default_locality)
        if parsed:
            keys.update(
                self._build_address_keys_from_parts(
                    district=district,
                    locality=parsed.get("locality"),
                    street=parsed.get("street"),
                    building=parsed.get("building"),
                )
            )

        compact = self.address_service.parse_compact_address(text)
        if compact:
            keys.update(
                self._build_address_keys_from_parts(
                    district=district,
                    locality=compact.get("locality"),
                    street=compact.get("street"),
                    building=compact.get("building"),
                )
            )

        parts = self._parse_address_like_text(text, default_locality=default_locality)
        if parts:
            keys.update(
                self._build_address_keys_from_parts(
                    district=district,
                    locality=parts.get("locality"),
                    street=parts.get("street"),
                    building=parts.get("building"),
                )
            )
        return keys

    def _parse_address_like_text(
        self,
        value: str,
        *,
        default_locality: Optional[str],
    ) -> Optional[dict[str, Optional[str]]]:
        text = normalize_text(value)
        if not text:
            return None

        normalized = text.lower().replace("ё", "е")
        normalized = re.sub(r"\bпр[\.-]?\s*", "проспект ", normalized)
        normalized = re.sub(r"\bпер[\.-]?\s*", "переулок ", normalized)
        normalized = re.sub(r"\bул[\.-]?\s*", "улица ", normalized)
        normalized = re.sub(r"[.;]+", ",", normalized)

        street_match = re.search(
            r"\b(улица|ул|переулок|пер|проспект|просп|пр-т|проезд|тракт|шоссе|бульвар|площадь|пл|набережная|наб)\.?\s+([^,]+)",
            normalized,
            re.IGNORECASE,
        )
        if not street_match:
            return None

        street_type, street_name = street_match.groups()
        street = f"{street_type} {street_name}".strip()
        tail = normalized[street_match.end() :]
        building_match = re.search(
            r"(?:^|,|\s)(?:д(?:ом)?\.?\s*)?([0-9]+(?:[/\\-][0-9]+)?[a-zа-я]?(?:\s*(?:к|корп|корпус|киоск|пом|помещение)\.?\s*[0-9a-zа-я/\\-]+)?)",
            tail,
            re.IGNORECASE,
        )
        building = building_match.group(1) if building_match else None

        locality = self.address_service._extract_locality(normalized) or normalize_text(default_locality)
        if not locality or not building:
            return None

        return {
            "locality": locality,
            "street": street,
            "building": building,
        }

    def _build_address_keys_from_parts(
        self,
        *,
        district: Optional[str],
        locality: Optional[str],
        street: Optional[str],
        building: Optional[str],
    ) -> set[str]:
        locality_key = self._norm_city_value(locality)
        street_key = self._norm_street_value(street)
        district_key = self._norm_city_value(district)
        building_variants = self._building_variants(building)

        if not locality_key or not street_key or not building_variants:
            return set()

        keys: set[str] = set()
        for building_key in building_variants:
            keys.add(f"{locality_key}|{street_key}|{building_key}")
            if district_key:
                keys.add(f"{district_key}|{locality_key}|{street_key}|{building_key}")
        return keys

    def _building_variants(self, value: Optional[str]) -> set[str]:
        text = normalize_text(value)
        if not text:
            return set()

        lowered = text.lower().replace("ё", "е")
        lowered = re.sub(r"\b(дом|д|здание)\b\.?", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        building_key = self._norm_building_value(lowered)
        if not building_key:
            return set()

        variants = {building_key}

        first_number = re.search(r"\d+", building_key)
        if first_number:
            variants.add(first_number.group(0))

        without_suffix = re.sub(r"[а-яa-z]+$", "", building_key)
        if without_suffix and without_suffix != building_key:
            variants.add(without_suffix)
        if "/" in text:
            slashless = building_key.replace("/", "")
            if slashless:
                variants.add(slashless)
            first_part = text.split("/", 1)[0]
            first_key = self._norm_building_value(first_part)
            if first_key:
                variants.add(first_key)
        for marker in ("к", "корп", "корпус", "киоск", "пом", "помещение"):
            marker_match = re.search(rf"^(.+?){marker}[0-9a-zа-я/\\-]+$", building_key)
            if marker_match:
                base = marker_match.group(1)
                if base:
                    variants.add(base)
        return {variant for variant in variants if variant}

    def _build_excluded_name_tokens(self, *values: Optional[str]) -> set[str]:
        tokens: set[str] = set()
        # Exclude only district/locality words from name matching. Street/building
        # tokens can be legitimate object names, so filtering them drops valid matches.
        for value in values[:2]:
            normalized = self._normalize_name(value)
            if not normalized:
                continue
            tokens.update(token for token in normalized.split() if len(token) >= 3)
        return tokens

    @staticmethod
    def _normalize_name(value: Optional[str], excluded_tokens: Optional[set[str]] = None) -> Optional[str]:
        text = normalize_text(value)
        if not text:
            return None
        text = text.lower().replace("ё", "е")
        text = re.sub(r"\([^)]*\)", " ", text)
        text = text.replace('"', " ").replace("'", " ")
        text = re.sub(r"[^a-z0-9а-я]+", " ", text)
        excluded_tokens = excluded_tokens or set()
        tokens = [
            token
            for token in text.split()
            if token and token not in NAME_STOPWORDS and token not in excluded_tokens
        ]
        return " ".join(tokens) or None

    @staticmethod
    def _normalize_exact_name_fragment(value: Optional[str]) -> Optional[str]:
        text = normalize_text(value)
        if not text:
            return None
        text = text.lower().replace("ё", "е")
        text = re.sub(r"\([^)]*\)", " ", text)
        text = re.sub(r"[^a-z0-9а-я]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or None


class ContractMatcher:
    def __init__(self, records: list[ContractRecord], address_service: AddressNormalizationService) -> None:
        self.records = records
        self.address_service = address_service
        self.builder = ContractMatchingService()

    def assign_rows(self, rows: list[ParsedImportRow]) -> ContractAssignmentBatch:
        row_results: dict[int, ContractLinkResult] = {}
        contract_results_by_row_index: dict[int, ContractRecordResult] = {}
        matched_contracts = 0
        unmatched_contracts = 0
        match_summary: dict[str, int] = defaultdict(int)
        unmatched_summary: dict[str, int] = defaultdict(int)
        gis_collection = GISObjectCollection(rows=rows, matcher=self)

        resolved_contracts: set[int] = set()
        for strategy in (
            "address_name_inn_plus",
            "address_name_inn_minus",
            "address_name_minus_inn_plus",
            "address_plus",
        ):
            for record in self.records:
                if record.source_row_index in resolved_contracts:
                    continue

                candidate = gis_collection.search(record, strategy)
                if candidate is None:
                    continue

                _, result = self._result_from_gis_state(record, GISSearchState(candidate=candidate, strategy=strategy))
                contract_results_by_row_index[record.source_row_index] = ContractRecordResult(
                    record=record,
                    result=result,
                    matched_row_source_index=candidate.row.source_row_index if result.matched else None,
                )
                resolved_contracts.add(record.source_row_index)
                candidate.assigned = True
                row_results[candidate.row.source_row_index] = result

        contract_results: list[ContractRecordResult] = []
        for record in self.records:
            contract_result = contract_results_by_row_index.get(record.source_row_index)
            if contract_result is None:
                contract_result = ContractRecordResult(
                    record=record,
                    result=self._unmatched_result("В таблице 2ГИС не найдено совпадение по адресу."),
                    matched_row_source_index=None,
                )
            contract_results.append(contract_result)

            result = contract_result.result
            if result.matched:
                matched_contracts += 1
                if result.strategy:
                    match_summary[result.strategy] += 1
            else:
                unmatched_contracts += 1
                unmatched_summary[result.reason or "Причина не определена"] += 1

        for row in rows:
            if row.source_row_index in row_results:
                continue
            if row.contract_link_status == "matched":
                row_results[row.source_row_index] = ContractLinkResult(
                    matched=True,
                    status="matched",
                    strategy=row.contract_link_strategy,
                    reason=row.contract_link_reason or "Строка 2ГИС уже была автоматически сопоставлена ранее.",
                    score=row.contract_link_score,
                    data=None,
                )
                continue
            row_results[row.source_row_index] = self._unmatched_result("Для строки 2ГИС подходящий договор не найден.")

        return ContractAssignmentBatch(
            row_results=row_results,
            contract_results=contract_results,
            matched_contracts=matched_contracts,
            unmatched_contracts=unmatched_contracts,
            match_summary=dict(match_summary),
            unmatched_summary=dict(unmatched_summary),
        )

    def _result_from_gis_state(
        self,
        record: ContractRecord,
        state: GISSearchState,
    ) -> tuple[Optional[GISObjectCandidate], ContractLinkResult]:
        if state.candidate is None or state.strategy is None:
            return None, self._unmatched_result("В таблице 2ГИС не найдено совпадение по адресу.")

        reason_by_strategy = {
            "address_name_inn_plus": "Совпали адрес, наименование и ИНН.",
            "address_name_inn_minus": "Совпали адрес и наименование, ИНН не совпал или отсутствует.",
            "address_name_minus_inn_plus": "Совпали адрес и ИНН, наименование не подтвердилось.",
        }
        score_by_strategy = {
            "address_name_inn_plus": 100,
            "address_name_inn_minus": 85,
            "address_name_minus_inn_plus": 80,
        }
        if state.strategy == "address_plus":
            return state.candidate, self._review_required_result(
                strategy=state.strategy,
                reason=f"Совпал только адрес, данные договора не перенесены. Строка договора: {record.source_row_index}.",
            )

        return state.candidate, self._matched_result(
            data=self._to_match_data(record),
            strategy=state.strategy,
            reason=reason_by_strategy.get(state.strategy, "Договор найден."),
            score=score_by_strategy.get(state.strategy, 50),
        )

    def _build_gis_candidate(self, row: ParsedImportRow) -> GISObjectCandidate:
        return GISObjectCandidate(
            row=row,
            name_variants=self.builder._build_name_variants(row.name, row.legal_entity_name),
            raw_name=row.name or row.legal_entity_name,
            name_excluded_tokens=frozenset(
                self.builder._build_excluded_name_tokens(
                    row.district,
                    row.city or row.settlement,
                    row.street,
                    row.building,
                    row.room or row.office,
                )
            ),
            inn_keys=self.builder._build_inn_key_set(row.inn),
            address_keys=frozenset(self.builder._build_row_address_keys(row)),
            city_key=self.builder._norm_city_value(row.city or row.settlement),
            street_key=self.builder._norm_street_value(row.street),
            building_key=self.builder._norm_building_value(row.building),
            already_matched=row.contract_link_status == "matched",
        )

    @staticmethod
    def _city_street_building_match(record: ContractRecord, candidate: GISObjectCandidate) -> bool:
        return bool(record.address_keys and candidate.address_keys and record.address_keys & candidate.address_keys)

    def _names_match_variants(
        self,
        contract_variants: tuple[str, ...],
        row_variants: tuple[str, ...],
        excluded_tokens: frozenset[str] = frozenset(),
        quoted_fragments: tuple[str, ...] = (),
    ) -> bool:
        for contract_name in contract_variants:
            for row_name in row_variants:
                if self._names_match(contract_name, row_name, excluded_tokens, quoted_fragments):
                    return True
        return False

    def _names_match_candidate(self, record: ContractRecord, candidate: GISObjectCandidate) -> bool:
        if record.raw_name and candidate.raw_name:
            return self._names_match(
                record.raw_name,
                candidate.raw_name,
                excluded_tokens=record.name_excluded_tokens | candidate.name_excluded_tokens,
            )
        return self._names_match_variants(record.name_variants, candidate.name_variants)

    @staticmethod
    def _names_match(
        contract_name: str,
        row_name: str,
        excluded_tokens: frozenset[str] = frozenset(),
        quoted_fragments: tuple[str, ...] = (),
    ) -> bool:
        row_text = ContractMatcher._only_cyrillic(row_name)
        if not row_text:
            return False

        current = ""
        contract_text = contract_name.lower().replace("ё", "е")
        for index, char in enumerate(contract_text):
            if ord(char) > 48:
                current += char
                if index == len(contract_text) - 1:
                    cleaned = ContractMatcher._check_name_fragment(current)
                    if cleaned in excluded_tokens:
                        cleaned = ""
                    return bool(cleaned and ContractMatcher._name_fragment_in_row(row_text, cleaned))
                continue

            cleaned = ContractMatcher._check_name_fragment(current)
            if cleaned in excluded_tokens:
                cleaned = ""
            if cleaned and ContractMatcher._name_fragment_in_row(row_text, cleaned):
                return True
            if cleaned:
                current = ""
            else:
                current = ""

        cleaned = ContractMatcher._check_name_fragment(current)
        if cleaned in excluded_tokens:
            cleaned = ""
        return bool(cleaned and ContractMatcher._name_fragment_in_row(row_text, cleaned))

    @staticmethod
    def _quoted_fragments_match(row_name: str, quoted_fragments: tuple[str, ...]) -> bool:
        row_text = ContractMatchingService._normalize_exact_name_fragment(row_name) or ""
        row_compact = row_text.replace(" ", "")
        for fragment in quoted_fragments:
            fragment_compact = fragment.replace(" ", "")
            if fragment in row_text or fragment_compact in row_compact:
                return True
        return False

    @staticmethod
    def _only_cyrillic(value: str) -> str:
        return "".join(ch for ch in value.lower().replace("ё", "е") if ord(ch) > 128)

    @staticmethod
    def _check_name_fragment(value: str) -> str:
        lowered = value.lower().replace("ё", "е")
        for stop_word in NAME_STOPWORDS:
            if stop_word in lowered:
                return ""
        return lowered

    @staticmethod
    def _name_fragment_in_row(row_text: str, fragment: str) -> bool:
        return bool(fragment and fragment.lower() in row_text.lower())

    @staticmethod
    def _inn_sets_match(left: frozenset[str], right: frozenset[str]) -> bool:
        return bool(left and right and left & right)

    @staticmethod
    def _matched_result(data: ContractMatchData, strategy: str, reason: str, score: int) -> ContractLinkResult:
        return ContractLinkResult(
            matched=True,
            status="matched",
            strategy=strategy,
            reason=reason,
            score=score,
            data=data,
        )

    @staticmethod
    def _unmatched_result(reason: str) -> ContractLinkResult:
        return ContractLinkResult(
            matched=False,
            status="unmatched",
            strategy=None,
            reason=reason,
            score=None,
            data=None,
        )

    @staticmethod
    def _review_required_result(strategy: str, reason: str) -> ContractLinkResult:
        return ContractLinkResult(
            matched=False,
            status="review_required",
            strategy=strategy,
            reason=reason,
            score=None,
            data=None,
        )

    @staticmethod
    def _to_match_data(record: ContractRecord) -> ContractMatchData:
        address_data = ContractMatcher._contract_address_data(record)
        return ContractMatchData(
            contract_number=record.contract_number,
            contract_date=record.contract_date,
            legal_entity_name=record.legal_entity_name,
            waste_object_name=record.waste_object_name,
            inn=record.inn,
            address=address_data["address"],
            locality=address_data["locality"],
            street=address_data["street"],
            building=address_data["building"],
            room=address_data["room"],
            contact_person=record.contact_person,
            calculation_value=ContractMatcher._format_total_volume(record.volume, record.quantity),
            calculation_unit="м3" if record.volume is not None else None,
            waste_generation_norm=record.pickup_frequency,
            billing_method=record.pickup_frequency,
            contract_start_date=record.contract_start_date,
            comment=record.comment,
        )

    @staticmethod
    def _contract_address_data(record: ContractRecord) -> dict[str, Optional[str]]:
        locality = record.locality or record.district
        return {
            "address": ContractMatcher._compose_address(
                locality=locality,
                street=record.street,
                building=record.building,
                room=record.room,
                fallback=record.address,
            ),
            "locality": locality,
            "street": record.street,
            "building": record.building,
            "room": record.room,
        }

    @staticmethod
    def _compose_address(
        locality: Optional[str],
        street: Optional[str],
        building: Optional[str],
        room: Optional[str],
        fallback: Optional[str] = None,
    ) -> Optional[str]:
        parts = [part for part in (locality, street) if part]
        if building:
            parts.append(f"д. {building}")
        if room:
            parts.append(f"пом. {room}")
        if parts:
            return ", ".join(parts)
        return normalize_text(fallback)

    @staticmethod
    def _format_total_volume(volume: Optional[float], quantity: Optional[float]) -> Optional[str]:
        if volume is None:
            return None
        total = volume
        if quantity not in (None, 0):
            total = volume * quantity
        return f"{total:g}"


class GISObjectCollection:
    def __init__(self, rows: list[ParsedImportRow], matcher: ContractMatcher) -> None:
        self.matcher = matcher
        self.candidates = [matcher._build_gis_candidate(row) for row in rows]

    def search(self, record: ContractRecord, strategy: str) -> Optional[GISObjectCandidate]:
        for candidate in self.candidates:
            if candidate.assigned or candidate.already_matched:
                continue

            if not self.matcher._city_street_building_match(record, candidate):
                continue

            names_match = self.matcher._names_match_candidate(record, candidate)
            inns_match = self.matcher._inn_sets_match(record.inn_keys, candidate.inn_keys)

            if strategy == "address_name_inn_plus" and names_match and inns_match:
                return candidate
            if strategy == "address_name_inn_minus" and names_match and not inns_match:
                return candidate
            if strategy == "address_name_minus_inn_plus" and not names_match and inns_match:
                return candidate
            if strategy == "address_plus":
                return candidate

        return None
