from __future__ import annotations

import re
from typing import Optional

from app.utils.normalization import normalize_text


class AddressNormalizationService:
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
            r"\b(улица|ул|переулок|пер|проспект|просп|пр т|проезд|шоссе|бульвар|площадь|набережная|наб)\b\.?",
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
