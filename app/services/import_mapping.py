from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from app.utils.normalization import normalize_header


COLUMN_ALIASES: dict[str, list[str]] = {
    "postal_code": ["postal_code", "индекс", "почтовый индекс"],
    "region": ["region", "субъект", "субъект рф", "область", "край", "республика", "регион"],
    "address": [
        "address",
        "адрес",
        "полный адрес",
        "адрес объекта",
        "местонахождение объекта",
        "фактический адрес",
        "точный адрес",
        "адрес местонахождения",
        "адрес места осуществления деятельности",
        "место осуществления деятельности",
    ],
    "district": [
        "district",
        "регион",
        "район",
        "административный район",
        "муниципальный район",
        "городской округ",
    ],
    "city": ["city", "город", "населенный пункт", "населённый пункт", "г_город"],
    "settlement": ["settlement", "поселение", "поселок", "посёлок", "село", "деревня"],
    "street": ["street", "улица", "проспект", "переулок", "шоссе", "бульвар", "проезд"],
    "building": ["building", "дом", "номер дома", "№ дома", "здание"],
    "floor": ["floor", "этаж"],
    "office": ["office", "офис", "кабинет"],
    "block": ["block", "корпус", "литер", "блок"],
    "structure": ["structure", "строение", "сооружение"],
    "room": ["room", "помещение", "квартира"],
    "cadastral_number": ["cadastral_number", "кадастровый номер"],
    "area": ["area", "площадь", "общая площадь"],
    "floors": ["floors", "этажность", "количество этажей"],
    "purpose": ["purpose", "назначение"],
    "object_type": ["object_type", "тип объекта", "вид объекта"],
    "name": [
        "name",
        "наименование",
        "название объекта",
        "объект образования отходов",
        "наименование объекта",
        "наименование организации",
        "наименование ооо",
        "наименование точки",
        "наименование площадки",
        "объект",
    ],
    "category": [
        "category",
        "категория",
        "категория объекта",
        "категория объекта по нормативу",
        "категория негативного воздействия",
        "категория нвос",
        "класс объекта",
        "рубрики",
    ],
    "waste_type": ["waste_type", "вид отходов", "тип отходов"],
    "waste_generation_norm": ["waste_generation_norm", "норма образования отходов"],
    "calculation_unit": ["calculation_unit", "единица расчета", "единица расчёта"],
    "calculation_value": ["calculation_value", "значение расчета", "значение расчёта", "объем", "объём"],
    "billing_method": [
        "billing_method",
        "как начисляется",
        "периодичность вывоза",
        "период вывоза",
        "график вывоза",
    ],
    "inn": ["inn", "инн"],
    "inn_1": ["inn_1", "инн_1"],
    "inn_2": ["inn_2", "инн_2"],
    "inn_3": ["inn_3", "инн_3"],
    "inn_4": ["inn_4", "инн_4"],
    "inn_5": ["inn_5", "инн_5"],
    "contract_number": ["contract_number", "номер договора", "договор", "договор номер"],
    "contract_date": ["contract_date", "дата договора"],
    "legal_entity_name": [
        "legal_entity_name",
        "юридическое наименование",
        "наименование юрлица",
        "юридическое лицо",
        "организация",
        "наименование организации",
        "контрагент",
        "владелец",
    ],
    "contact_person": ["contact_person", "контактное лицо"],
    "phone": ["phone", "телефон"],
    "email": ["email", "e-mail", "электронная почта"],
}


def resolve_column_mapping(columns: Iterable[str]) -> dict[str, str]:
    normalized_columns = {normalize_header(column): str(column) for column in columns}
    resolved: dict[str, str] = {}
    for target_field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize_header(alias)
            if normalized_alias in normalized_columns:
                resolved[target_field] = normalized_columns[normalized_alias]
                break
    return resolved


def canonicalize_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    column_mapping = resolve_column_mapping(df.columns)
    renamed = df.rename(columns={source: target for target, source in column_mapping.items()})

    for target_field in COLUMN_ALIASES:
        if target_field not in renamed.columns:
            renamed[target_field] = None

    return renamed[list(COLUMN_ALIASES.keys())], column_mapping
