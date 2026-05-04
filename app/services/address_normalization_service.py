from __future__ import annotations

import re
from typing import Optional

from app.utils.normalization import normalize_text


class AddressNormalizationService:
    STREET_PATTERN = re.compile(
        r"\b(улица|ул|переулок|пер|проспект|просп|пр-т|пр|проезд|шоссе|тракт|бульвар|площадь|пл|набережная|наб)\.?\s+([^,]+)",
        re.IGNORECASE,
    )
    LOCALITY_PATTERNS = (
        re.compile(r"(?:^|,)\s*(?:город|г)\.?\s*([a-zа-я0-9\- ]+)", re.IGNORECASE),
        re.compile(r"(?:^|,)\s*(?:село|с)\.?\s*([a-zа-я0-9\- ]+)", re.IGNORECASE),
        re.compile(r"(?:^|,)\s*(?:пос[её]лок|пгт|деревня|д)\.?\s*([a-zа-я0-9\- ]+)", re.IGNORECASE),
    )
    ROOM_PATTERN = re.compile(r"\b(?:пом(?:ещение)?|офис|каб(?:инет)?|кв(?:артира)?)\.?\s*([0-9a-zа-я\-]+)", re.IGNORECASE)
    BUILDING_WITH_PREFIX_PATTERN = re.compile(r"\b(?:д(?:ом)?|здание)\.?\s*([0-9a-zа-я\/\-]+)", re.IGNORECASE)
    BUILDING_AFTER_STREET_PATTERN = re.compile(r"(?:,|\s)([0-9a-zа-я\/\-]+)\b", re.IGNORECASE)

    def normalize(
        self,
        address: Optional[str],
        postal_code: Optional[str] = None,
        region: Optional[str] = None,
        district: Optional[str] = None,
        city: Optional[str] = None,
        settlement: Optional[str] = None,
        street: Optional[str] = None,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        office: Optional[str] = None,
        block: Optional[str] = None,
        structure: Optional[str] = None,
        room: Optional[str] = None,
    ) -> Optional[str]:
        if address:
            return normalize_text(address)

        parts = [
            normalize_text(postal_code),
            normalize_text(region),
            normalize_text(city),
            normalize_text(district),
            normalize_text(settlement),
            normalize_text(street),
            self._with_prefix(building, "д."),
            self._with_prefix(floor, "эт."),
            self._with_prefix(office, "оф."),
            self._with_prefix(block, "корп."),
            self._with_prefix(structure, "стр."),
            self._with_prefix(room, "пом."),
        ]
        parts = self._compact_parts([part for part in parts if part])
        if not parts:
            return None
        return ", ".join(parts)

    def parse_freeform_address(
        self,
        address: Optional[str],
        default_locality: Optional[str] = None,
    ) -> Optional[dict[str, Optional[str]]]:
        text = normalize_text(address)
        if not text:
            return None

        locality = self._extract_locality(text) or normalize_text(default_locality)
        street = None
        building = None
        room = None

        street_match = self.STREET_PATTERN.search(text)
        if street_match:
            street_type, street_name = street_match.groups()
            street = f"{street_type} {street_name}".strip()
            tail = text[street_match.end() :]
            room_match = self.ROOM_PATTERN.search(tail)
            if room_match:
                room = room_match.group(1)

            building_match = self.BUILDING_WITH_PREFIX_PATTERN.search(tail)
            if not building_match:
                building_match = self.BUILDING_AFTER_STREET_PATTERN.search(tail)
            if building_match:
                building = building_match.group(1)

        if not any((locality, street, building, room)):
            return None

        return {
            "locality": locality,
            "street": street,
            "building": building,
            "room": room,
        }

    @staticmethod
    def _with_prefix(value: Optional[str], prefix: str) -> Optional[str]:
        text = normalize_text(value)
        if not text:
            return None

        lowered = text.lower()
        known_prefixes = ("д.", "дом", "эт.", "этаж", "оф.", "офис", "корп.", "корпус", "стр.", "строение", "пом.", "помещение")
        if lowered.startswith(known_prefixes):
            return text
        return f"{prefix} {text}"

    @staticmethod
    def _compact_parts(parts: list[str]) -> list[str]:
        compacted: list[str] = []
        normalized_parts: list[str] = []

        for part in parts:
            normalized = re.sub(r"\s+", " ", part.lower().replace("ё", "е")).strip()
            if not normalized:
                continue

            replaced = False
            for index, existing in enumerate(normalized_parts):
                if normalized == existing or normalized in existing:
                    replaced = True
                    break
                if existing in normalized:
                    normalized_parts[index] = normalized
                    compacted[index] = part
                    replaced = True
                    break

            if replaced:
                continue

            compacted.append(part)
            normalized_parts.append(normalized)

        return compacted

    def build_search_key(
        self,
        locality: Optional[str],
        street: Optional[str],
        building: Optional[str],
        office: Optional[str] = None,
        room: Optional[str] = None,
    ) -> Optional[str]:
        locality_key = self._clean_locality(locality)
        street_key = self._clean_street(street)
        building_key = self._clean_generic(building)
        room_key = self._clean_generic(room or office)

        parts = [part for part in (locality_key, street_key, building_key, room_key) if part]
        if not parts:
            return None
        return "|".join(parts)

    def build_search_key_from_freeform(
        self,
        address: Optional[str],
        default_locality: Optional[str] = None,
    ) -> Optional[str]:
        parts = self.parse_freeform_address(address=address, default_locality=default_locality)
        if not parts:
            return None
        return self.build_search_key(
            locality=parts.get("locality"),
            street=parts.get("street"),
            building=parts.get("building"),
            room=parts.get("room"),
        )

    def parse_compact_address(
        self,
        address: Optional[str],
    ) -> Optional[dict[str, Optional[str]]]:
        text = normalize_text(address)
        if not text:
            return None

        tokens = [token.strip() for token in text.split(",") if normalize_text(token)]
        if len(tokens) < 3:
            return None

        room = None
        if len(tokens) >= 4 and "район" not in tokens[-4].lower():
            locality = tokens[-4]
            street = tokens[-3]
            building = tokens[-2]
            room = tokens[-1]
        else:
            locality = tokens[-3]
            street = tokens[-2]
            building = tokens[-1]

        return {
            "locality": normalize_text(locality),
            "street": normalize_text(street),
            "building": normalize_text(building),
            "room": normalize_text(room),
        }

    def build_search_key_from_compact(
        self,
        address: Optional[str],
    ) -> Optional[str]:
        parts = self.parse_compact_address(address=address)
        if not parts:
            return None
        return self.build_search_key(
            locality=parts.get("locality"),
            street=parts.get("street"),
            building=parts.get("building"),
            room=parts.get("room"),
        )

    @staticmethod
    def _clean_locality(value: Optional[str]) -> Optional[str]:
        text = normalize_text(value)
        if not text:
            return None
        text = re.sub(r"\(.*?\)", "", text)
        text = text.lower().replace("ё", "е")
        text = re.sub(r"\b(город|г|село|с|поселок|поселок|пгт|деревня|д)\b\.?", " ", text)
        text = re.sub(r"[^a-z0-9а-я]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    @staticmethod
    def _clean_street(value: Optional[str]) -> Optional[str]:
        text = normalize_text(value)
        if not text:
            return None
        text = text.lower().replace("ё", "е")
        text = re.sub(
            r"\b(улица|ул|переулок|пер|проспект|просп|пр-т|пр|проезд|шоссе|тракт|бульвар|площадь|пл|набережная|наб)\b\.?",
            " ",
            text,
        )
        text = re.sub(r"[^a-z0-9а-я]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    @staticmethod
    def _clean_generic(value: Optional[str]) -> Optional[str]:
        text = normalize_text(value)
        if not text:
            return None
        text = text.lower().replace("ё", "е")
        text = re.sub(r"[^a-z0-9а-я]+", "", text)
        return text or None

    @classmethod
    def _extract_locality(cls, text: str) -> Optional[str]:
        for pattern in cls.LOCALITY_PATTERNS:
            match = pattern.search(text)
            if match:
                return normalize_text(match.group(1))
        return None
