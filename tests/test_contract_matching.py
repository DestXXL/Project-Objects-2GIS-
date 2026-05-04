from datetime import date, datetime

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import ContractRow, LegalEntity, WasteObject
from app.repositories.contract_row_repository import ContractRowRepository
from app.schemas.imports import ParsedImportRow
from app.services.contract_matching_service import ContractMatchingService
from app.services.import_service import ImportService
from app.utils.dates import parse_date


def match_single_row(matcher, row: ParsedImportRow):
    batch = matcher.assign_rows([row])
    return batch.row_results[row.source_row_index]


def test_contract_matcher_matches_by_inn_and_address():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/1",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Горизонт" Алейский мясокомбинат',
                "Наименование ИОО": 'магазин"Алейский мясокомбинат"',
                "ИНН": "2222057844",
                "адрес объекта": "г.Рубцовск, ул.Комсомольская, 71А",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
                "объем": 1.11,
                "периодичность вывоза": "по нормативу",
                "контактное лицо": "Инженер",
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    row = ParsedImportRow(
        source_row_index=2,
        name="Алейский мясокомбинат, магазин",
        city="Рубцовск (Рубцовск городской округ)",
        street="Комсомольская",
        building="71А",
        inn="2222057844",
    )

    match = match_single_row(matcher, row)

    assert match.matched is True
    assert match.status == "matched"
    assert match.strategy == "address_name_inn_plus"
    assert match.data is not None
    assert match.data.contract_number == "Р/1"


def test_contract_matcher_matches_on_third_pass_when_address_and_inn_coincide():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/530",
                "Дата": "22.05.2023",
                "Наименование потребителя": "ИП Саблин Андрей Дмитриевич",
                "Наименование ИОО": "Автомойка 24",
                "ИНН": "220910592205",
                "адрес объекта": "г.Рубцовск, проспект Ленина, 200",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "проспект",
                "улица": "Ленина",
                "дом": "200",
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    row = ParsedImportRow(
        source_row_index=2,
        name="Студия депиляции",
        city="Рубцовск (Рубцовск городской округ)",
        street="проспект Ленина",
        building="200",
        inn="220910592205",
    )

    match = match_single_row(matcher, row)

    assert match.matched is True
    assert match.status == "matched"
    assert match.strategy == "address_name_minus_inn_plus"
    assert match.data is not None
    assert match.data.contract_number == "Р/530"


def test_import_service_enriches_empty_fields_from_contract():
    row = ParsedImportRow(
        source_row_index=2,
        name="Горизонт",
        legal_entity_name='ООО "Горизонт"',
        city="Рубцовск",
        street="Комсомольская",
        building="71А",
        inn="2222057844",
    )
    contract = ContractMatchingService().build_matcher(
        pd.DataFrame(
            [
                {
                    "№ ": "Р/1",
                    "Дата": "14.12.2022",
                    "Наименование потребителя": 'ООО "Горизонт"',
                    "Наименование ИОО": "Объект по договору",
                    "ИНН": "2222057844",
                    "тип населенного пункта": "город",
                    "населенный пункт": "Рубцовск",
                    "тип улицы": "ул",
                    "улица": "Комсомольская",
                    "дом": "71А",
                    "объем": 1.11,
                    "периодичность вывоза": "по нормативу",
                    "контактное лицо": "Инженер",
                    "дата начала": "01.01.2023",
                    "комментарии": "подписано",
                }
            ]
        )
    )

    contract = match_single_row(contract, row)

    assert contract.matched is True
    assert contract.data is not None

    ImportService._enrich_from_contract(row, contract.data)

    assert row.contract_number == "Р/1"
    assert str(row.contract_date) == "2022-12-14"
    assert row.legal_entity_name == 'ООО "Горизонт"'
    assert row.calculation_value == "1.11"
    assert row.calculation_unit == "м3"
    assert row.billing_method == "по нормативу"
    assert row.waste_generation_norm == "по нормативу"
    assert row.contact_person == "Инженер"
    assert str(row.contract_start_date) == "2023-01-01"
    assert row.comment == "подписано"


def test_import_service_enriches_missing_address_fields_from_contract():
    row = ParsedImportRow(
        source_row_index=2,
        name="Горизонт",
        legal_entity_name='ООО "Горизонт"',
        inn="2222057844",
    )
    contract = ContractMatchingService().build_matcher(
        pd.DataFrame(
            [
                {
                    "№ ": "Р/1",
                    "Дата": "14.12.2022",
                    "Наименование потребителя": 'ООО "Горизонт"',
                    "Наименование ИОО": "Объект по договору",
                    "ИНН": "2222057844",
                    "адрес объекта": "г.Рубцовск, ул.Комсомольская, 71А",
                    "тип населенного пункта": "город",
                    "населенный пункт": "Рубцовск",
                    "тип улицы": "ул",
                    "улица": "Комсомольская",
                    "дом": "71А",
                }
            ]
        )
    )

    contract = match_single_row(
        contract,
        ParsedImportRow(
            source_row_index=2,
            name="Горизонт",
            legal_entity_name='ООО "Горизонт"',
            city="Рубцовск",
            street="Комсомольская",
            building="71А",
            inn="2222057844",
        ),
    )

    assert contract.matched is True
    assert contract.data is not None

    ImportService._enrich_from_contract(row, contract.data)

    assert row.address == "город Рубцовск, ул Комсомольская, д. 71А"
    assert row.city == "город Рубцовск"
    assert row.street == "ул Комсомольская"
    assert row.building == "71А"


def test_contract_matcher_marks_contract_without_address_for_manual_review():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/351/24",
                "Дата": "18.01.2024",
                "Наименование потребителя": 'МБУК "Библиотечная информационная система"',
                "Наименование ИОО": "библиотека",
                "ИНН": "2209011216",
                "периодичность вывоза": "по нормативу",
                "комментарии": "подписано",
            },
            {
                "№ ": "Р/351/24",
                "Дата": "18.01.2024",
                "Наименование потребителя": 'МБУК "Библиотечная информационная система"',
                "Наименование ИОО": "библиотека",
                "ИНН": "2209011216",
                "периодичность вывоза": "по нормативу",
            },
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    row = ParsedImportRow(
        source_row_index=2,
        name="Спецбиблиотека для незрячих и слабовидящих граждан",
        city="Рубцовск",
        street="Гражданский переулок",
        building="41",
        inn="2209011216",
    )

    match = match_single_row(matcher, row)

    assert match.matched is False
    assert match.status == "unmatched"
    assert match.strategy is None
    assert match.data is None


def test_contract_matcher_uses_raw_address_when_structured_columns_are_wrong():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/129",
                "Дата": "13.01.2023",
                "Наименование потребителя": 'ООО Торгсервис 22',
                "Наименование ИОО": 'магазин "Светофор"',
                "ИНН": "2224156015",
                "адрес объекта": "Магазин Светофор 22, ул. Сельмашская, 02",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Сельмашская",
                "дом": "22",
                "периодичность вывоза": "6 раз в неделю",
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    row = ParsedImportRow(
        source_row_index=2,
        name="Светофор, супермаркет",
        city="Рубцовск (Рубцовск городской округ)",
        street="Сельмашская",
        building="02а",
        inn="2224156015",
    )

    match = match_single_row(matcher, row)

    assert match.matched is True
    assert match.status == "matched"
    assert match.strategy == "address_name_inn_plus"
    assert match.data is not None
    assert match.data.contract_number == "Р/129"


def test_contract_matcher_uses_compact_address_but_does_not_relax_inn():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/124",
                "Дата": "12.01.2023",
                "Наименование потребителя": 'ООО Торгсервис 22, Светофор, Рубцовск 5',
                "Наименование ИОО": 'магазин "Светофор"',
                "ИНН": "22224156015",
                "адрес объекта": "г.Рубцовск, ул. Карла Маркса, 214",
                "Unnamed: 6": "Рубцовск,Карла Маркса,214,",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Карла Маркса",
                "дом": "214",
                "периодичность вывоза": "2 раза в неделю",
                "объем": 1.1,
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    row = ParsedImportRow(
        source_row_index=2,
        name="Светофор, супермаркет",
        city="Рубцовск (Рубцовск городской округ)",
        street="Карла Маркса",
        building="214",
        inn="2224156015",
    )

    match = match_single_row(matcher, row)

    assert match.matched is True
    assert match.strategy == "address_name_inn_minus"
    assert match.data is not None
    assert match.data.contract_number == "Р/124"
    assert str(match.data.contract_date) == "2023-01-12"
    assert match.data.calculation_value == "1.1"
    assert match.data.billing_method == "2 раза в неделю"


def test_contract_matcher_prefers_name_candidates_before_address_inn_candidates():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/1",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Горизонт"',
                "Наименование ИОО": "Точный объект",
                "ИНН": "1111111111",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            },
            {
                "№ ": "Р/2",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Другой контрагент"',
                "Наименование ИОО": "Совсем другое имя",
                "ИНН": "2222057844",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            },
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    row = ParsedImportRow(
        source_row_index=2,
        name="Точный объект",
        city="Рубцовск",
        street="Комсомольская",
        building="71А",
        inn="2222057844",
    )

    match = match_single_row(matcher, row)

    assert match.matched is True
    assert match.status == "matched"
    assert match.strategy == "address_name_inn_minus"
    assert match.data is not None
    assert match.data.contract_number == "Р/1"


def test_contract_matcher_marks_address_only_match_for_review_without_enrichment_data():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/77",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Контрагент"',
                "Наименование ИОО": "Совсем другое имя",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    row = ParsedImportRow(
        source_row_index=2,
        name="Точный объект",
        city="Рубцовск",
        street="Комсомольская",
        building="71А",
    )

    match = match_single_row(matcher, row)

    assert match.matched is False
    assert match.status == "review_required"
    assert match.strategy == "address_plus"
    assert match.data is None


def test_contract_matcher_does_not_treat_locality_word_as_name_match():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/126",
                "Дата": "08.11.2023",
                "Наименование потребителя": 'ООО "ТС Аникс"',
                "Наименование ИОО": 'Магазин "Аникс Новоегорьевское"',
                "тип населенного пункта": "село",
                "населенный пункт": "Новоегорьевское",
                "тип улицы": "ул",
                "улица": "Машинцева",
                "дом": "1",
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    row = ParsedImportRow(
        source_row_index=2,
        name="Новоегорьевское, автостанция",
        city="Новоегорьевское",
        street="Машинцева",
        building="1",
    )

    match = match_single_row(matcher, row)

    assert match.matched is False
    assert match.status == "review_required"
    assert match.strategy == "address_plus"


def test_contract_matcher_does_not_match_city_only_address_variant():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/11/25",
                "Дата": "19.12.2024",
                "Наименование потребителя": "КГУЗ Центр диагностики",
                "Наименование ИОО": "Центр диагностики",
                "ИНН": "2209022345",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Федоренко",
                "дом": "21а",
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    row = ParsedImportRow(
        source_row_index=2,
        name="Джамп, фитнес-центр",
        legal_entity_name="Польников Евгений Викторович",
        city="Рубцовск (Рубцовск городской округ)",
        street="проспект Ленина",
        building="206",
        floor="5",
        inn="220908543465",
    )

    match = match_single_row(matcher, row)

    assert match.matched is False
    assert match.status == "unmatched"
    assert match.strategy is None


def test_contract_matcher_prefers_exact_inn_match_for_jump_case():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/339",
                "Дата": "01.01.2023",
                "Наименование потребителя": "ИП Маньшин Александр Викторович",
                "Наименование ИОО": "офис",
                "ИНН": "220901144863",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "111",
                "тип пом": "пом",
                "помещение": "3",
            },
            {
                "№ ": "Р/564",
                "Дата": "30.05.2023",
                "Наименование потребителя": "ИП Польников Евгений Викторович",
                "Наименование ИОО": 'Фитнес клуб "Джамп"',
                "ИНН": "220908543465",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "проспект",
                "улица": "Ленина",
                "дом": "206",
            },
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    row = ParsedImportRow(
        source_row_index=2,
        name="Джамп, фитнес-центр",
        legal_entity_name="Польников Евгений Викторович",
        city="Рубцовск (Рубцовск городской округ)",
        street="проспект Ленина",
        building="206",
        floor="5",
        inn="220908543465",
    )

    match = match_single_row(matcher, row)

    assert match.matched is True
    assert match.strategy == "address_name_inn_plus"
    assert match.data is not None
    assert match.data.contract_number == "Р/564"


def test_contract_matcher_chooses_first_candidate_when_multiple_candidates_exist_on_same_stage():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/1",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Горизонт"',
                "Наименование ИОО": "Точный объект",
                "ИНН": "2222057844",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    rows = [
        ParsedImportRow(
            source_row_index=2,
            name="Точный объект",
            city="Рубцовск",
            street="Комсомольская",
            building="71А",
            inn="2222057844",
        ),
        ParsedImportRow(
            source_row_index=3,
            name="Точный объект",
            city="Рубцовск",
            street="Комсомольская",
            building="71А",
            inn="2222057844",
        ),
    ]

    batch = matcher.assign_rows(rows)

    assert batch.row_results[2].status == "matched"
    assert batch.row_results[2].strategy == "address_name_inn_plus"
    assert batch.row_results[3].status == "unmatched"


def test_import_service_splits_concatenated_inns():
    result = ImportService._extract_inn_candidates(["222200228886222300573501"])

    assert result == ["222200228886", "222300573501"]


def test_parse_date_accepts_datetime_with_time_component():
    parsed = parse_date(datetime(1900, 1, 10, 1, 58, 6, 787000))

    assert parsed == date(1900, 1, 10)


def test_import_service_maps_billing_method_from_main_table_period_column():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Объект 1",
                "Рубрики": "Категория",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск (Рубцовск городской округ)",
                "Улица": "Комсомольская",
                "Номер дома": "10",
                "Период вывоза": "каждую пятницу",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        result = service.import_dataframe(session, main_df)
        item = session.scalars(select(WasteObject)).first()

    assert result.waste_objects_created == 1
    assert item is not None
    assert item.billing_method == "каждую пятницу"


def test_import_service_reports_progress_updates():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Объект 1",
                "Рубрики": "Категория",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск",
                "Улица": "Комсомольская",
                "Номер дома": "10",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()
    progress_events: list[dict] = []

    with Session(engine) as session:
        result = service.import_dataframe(session, main_df, progress_callback=progress_events.append)

    assert result.waste_objects_created == 1
    stages = [event["stage"] for event in progress_events]
    assert "prepare" in stages
    assert "entities" in stages
    assert "write" in stages
    assert "commit" in stages


def test_import_service_uses_category_from_rubrics_column_only():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Объект 1",
                "Рубрики": "Магазины стройматериалов",
                "Тип объекта": "Нежилое помещение",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск (Рубцовск городской округ)",
                "Улица": "Комсомольская",
                "Номер дома": "10",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        result = service.import_dataframe(session, main_df)
        item = session.scalars(select(WasteObject)).first()

    assert result.waste_objects_created == 1
    assert item is not None
    assert item.category == "Магазины стройматериалов"


def test_import_service_leaves_category_empty_when_rubrics_column_missing():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Объект 1",
                "Тип объекта": "Нежилое помещение",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск (Рубцовск городской округ)",
                "Улица": "Комсомольская",
                "Номер дома": "10",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        result = service.import_dataframe(session, main_df)
        item = session.scalars(select(WasteObject)).first()

    assert result.waste_objects_created == 1
    assert item is not None
    assert item.category is None


def test_import_service_does_not_assign_carwash_contract_when_name_differs():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Студия депиляции",
                "Рубрики": "Эпиляция",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск (Рубцовск городской округ)",
                "Улица": "проспект Ленина",
                "Номер дома": "200",
                "Этаж": "2",
            }
        ]
    )
    contract_df = pd.DataFrame(
        [
            {
                "№ ": "Р/530",
                "Дата": "22.05.2023",
                "Наименование потребителя": "ИП Саблин Андрей Дмитриевич",
                "Наименование ИОО": "Автомойка 24",
                "ИНН": "220910592205",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "проспект",
                "улица": "Ленина",
                "дом": "200",
                "объем": 0.75,
                "периодичность вывоза": "2 раза в месяц",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        service.import_dataframe(session, main_df, contract_dataframe=contract_df)
        item = session.scalars(select(WasteObject)).first()

    assert item is not None
    assert item.name == "Студия депиляции"
    assert item.inn is None
    assert item.contract_number is None
    assert item.contract_link_status == "review_required"
    assert item.contract_link_strategy == "address_plus"


def test_import_service_does_not_assign_building_material_store_contract_when_name_differs():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Маяк, автомойка самообслуживания",
                "Рубрики": "Автомойки",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск (Рубцовск городской округ)",
                "Улица": "Комсомольская",
                "Номер дома": "256",
            }
        ]
    )
    contract_df = pd.DataFrame(
        [
            {
                "№ ": "Р/891",
                "Дата": "16.07.2024",
                "Наименование потребителя": 'ООО "ИКТОНИКС ТРЕЙД"',
                "Наименование ИОО": 'Магазин стройматериалов "Формула М2"',
                "ИНН": "5408186470",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "256",
                "периодичность вывоза": "по нормативу",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        service.import_dataframe(session, main_df, contract_dataframe=contract_df)
        item = session.scalars(select(WasteObject)).first()

    assert item is not None
    assert item.name == "Маяк, автомойка самообслуживания"
    assert item.inn is None
    assert item.contract_number is None
    assert item.contract_link_status == "review_required"
    assert item.contract_link_strategy == "address_plus"


def test_import_service_creates_waste_object_for_each_duplicate_source_row():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Мировые судьи г. Рубцовска",
                "Рубрики": "Административные, офисные учреждения",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск (Рубцовск городской округ)",
                "Улица": "Октябрьская",
                "Номер дома": "159",
                "Этаж": "1",
            },
            {
                "Наименование организации": "Мировые судьи г. Рубцовска",
                "Рубрики": "Административные, офисные учреждения",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск (Рубцовск городской округ)",
                "Улица": "Октябрьская",
                "Номер дома": "159",
                "Этаж": "1",
            },
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        result = service.import_dataframe(session, main_df)
        items = session.scalars(select(WasteObject).order_by(WasteObject.id)).all()

    assert result.processed_rows == 2
    assert result.waste_objects_created == 2
    assert len(items) == 2
    assert items[0].source_row_index != items[1].source_row_index


def test_import_service_creates_legal_entities_for_multiple_inns():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Объект 1",
                "Рубрики": "Административные, офисные учреждения",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск",
                "Улица": "Комсомольская",
                "Номер дома": "10",
                "ИНН_1": "2209011216",
                "ИНН_2": "2209019999",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        result = service.import_dataframe(session, main_df)
        entities = session.scalars(select(LegalEntity).order_by(LegalEntity.inn)).all()
        waste_object = session.scalars(select(WasteObject)).first()

    assert result.legal_entities_created == 2
    assert [entity.inn for entity in entities] == ["2209011216", "2209019999"]
    assert waste_object is not None
    assert waste_object.inn == "2209011216|2209019999"


def test_import_service_creates_legal_entity_even_when_address_is_missing():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Организация без адреса",
                "ИНН": "2209011216",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        result = service.import_dataframe(session, main_df)
        entities = session.scalars(select(LegalEntity).order_by(LegalEntity.inn)).all()
        waste_objects = session.scalars(select(WasteObject)).all()

    assert result.legal_entities_created == 1
    assert result.waste_objects_created == 0
    assert result.skipped_rows == 1
    assert [entity.inn for entity in entities] == ["2209011216"]
    assert len(waste_objects) == 0


def test_import_service_does_not_create_legal_entity_from_contract_only_inn():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Объект без ИНН",
                "Рубрики": "Административные, офисные учреждения",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск",
                "Улица": "Комсомольская",
                "Номер дома": "10",
            }
        ]
    )
    contract_df = pd.DataFrame(
        [
            {
                "№ ": "Р/1",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Горизонт"',
                "Наименование ИОО": "Объект без ИНН",
                "ИНН": "2222057844",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "10",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        result = service.import_dataframe(session, main_df, contract_dataframe=contract_df)
        entities = session.scalars(select(LegalEntity).order_by(LegalEntity.inn)).all()
        waste_object = session.scalars(select(WasteObject)).first()

    assert result.legal_entities_created == 0
    assert entities == []
    assert waste_object is not None
    assert waste_object.inn == "2222057844"
    assert waste_object.legal_entity_id is None


def test_reimport_updates_existing_waste_object_without_duplicate():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Рубцовский районный суд",
                "Рубрики": "Административные, офисные учреждения",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск (Рубцовск городской округ)",
                "Улица": "Бульварный переулок",
                "Номер дома": "13",
            }
        ]
    )
    contract_df = pd.DataFrame(
        [
            {
                "№ ": "Р/238/24",
                "Дата": "02.02.2024",
                "Наименование потребителя": "УСД в Алтайском крае",
                "Наименование ИОО": "суд",
                "ИНН": "2225045607",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "переулок",
                "улица": "Бульварный",
                "дом": "13",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        first = service.import_dataframe(session, main_df)
        second = service.import_dataframe(session, main_df, contract_dataframe=contract_df)
        items = session.scalars(select(WasteObject)).all()

    assert first.waste_objects_created == 1
    assert second.waste_objects_created == 0
    assert len(items) == 1
    assert items[0].contract_number == "Р/238/24"
    assert items[0].contract_link_status == "matched"
    assert items[0].contract_link_strategy == "address_name_inn_minus"


def test_contract_matcher_skips_already_matched_gis_rows_in_batch():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/1",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Горизонт"',
                "Наименование ИОО": "Точный объект",
                "ИНН": "2222057844",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    rows = [
        ParsedImportRow(
            source_row_index=2,
            name="Точный объект",
            city="Рубцовск",
            street="Комсомольская",
            building="71А",
            inn="2222057844",
            contract_link_status="matched",
            contract_link_strategy="address_name_inn_plus",
            contract_link_reason="Ранее уже сопоставлено.",
            contract_link_score=100,
        ),
        ParsedImportRow(
            source_row_index=3,
            name="Точный объект",
            city="Рубцовск",
            street="Комсомольская",
            building="71А",
            inn="2222057844",
        ),
    ]

    batch = matcher.assign_rows(rows)

    assert batch.matched_contracts == 1
    assert batch.row_results[2].status == "matched"
    assert batch.row_results[2].data is None
    assert batch.row_results[3].status == "matched"
    assert batch.row_results[3].strategy == "address_name_inn_plus"


def test_contract_matcher_allows_review_required_row_in_batch():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/1",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Горизонт"',
                "Наименование ИОО": "Точный объект",
                "ИНН": "2222057844",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    rows = [
        ParsedImportRow(
            source_row_index=2,
            name="Точный объект",
            city="Рубцовск",
            street="Комсомольская",
            building="71А",
            inn="2222057844",
            contract_link_status="review_required",
        ),
        ParsedImportRow(
            source_row_index=3,
            name="Точный объект",
            city="Рубцовск",
            street="Комсомольская",
            building="71А",
            inn="2222057844",
        ),
    ]

    batch = matcher.assign_rows(rows)

    assert batch.row_results[2].status == "matched"
    assert batch.row_results[2].strategy == "address_name_inn_plus"


def test_contract_matcher_allows_unmatched_row_in_batch():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/1",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Горизонт"',
                "Наименование ИОО": "Точный объект",
                "ИНН": "2222057844",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    rows = [
        ParsedImportRow(
            source_row_index=2,
            name="Точный объект",
            city="Рубцовск",
            street="Комсомольская",
            building="71А",
            inn="2222057844",
            contract_link_status="unmatched",
        )
    ]

    batch = matcher.assign_rows(rows)

    assert batch.row_results[2].status == "matched"
    assert batch.row_results[2].strategy == "address_name_inn_plus"


def test_contract_matcher_does_not_block_on_source_contract_number_without_matched_status():
    contracts = pd.DataFrame(
        [
            {
                "№ ": "Р/1",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Горизонт"',
                "Наименование ИОО": "Точный объект",
                "ИНН": "2222057844",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            }
        ]
    )
    matcher = ContractMatchingService().build_matcher(contracts)
    rows = [
        ParsedImportRow(
            source_row_index=2,
            name="Точный объект",
            city="Рубцовск",
            street="Комсомольская",
            building="71А",
            inn="2222057844",
            source_contract_number="Р/старый",
        )
    ]

    batch = matcher.assign_rows(rows)

    assert batch.row_results[2].status == "matched"
    assert batch.row_results[2].strategy == "address_name_inn_plus"


def test_reimport_does_not_reassign_already_auto_matched_row():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Точный объект",
                "Рубрики": "Категория",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск",
                "Улица": "Комсомольская",
                "Номер дома": "71А",
                "ИНН": "2222057844",
            }
        ]
    )
    first_contract_df = pd.DataFrame(
        [
            {
                "№ ": "Р/1",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Горизонт"',
                "Наименование ИОО": "Точный объект",
                "ИНН": "2222057844",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            }
        ]
    )
    second_contract_df = pd.DataFrame(
        [
            {
                "№ ": "Р/2",
                "Дата": "15.12.2022",
                "Наименование потребителя": 'ООО "Другой контрагент"',
                "Наименование ИОО": "Точный объект",
                "ИНН": "2222057844",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        first = service.import_dataframe(session, main_df, contract_dataframe=first_contract_df)
        second = service.import_dataframe(session, main_df, contract_dataframe=second_contract_df)
        item = session.scalars(select(WasteObject)).first()

    assert first.contracts_matched == 1
    assert second.contracts_matched == 0
    assert item is not None
    assert item.contract_number == "Р/1"
    assert item.contract_link_status == "matched"
    assert item.contract_link_strategy == "address_name_inn_plus"


def test_import_service_persists_contract_rows_and_shows_only_unresolved_ones():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    main_df = pd.DataFrame(
        [
            {
                "name": "Алейский мясокомбинат, магазин",
                "category": "Продовольственный магазин",
                "city": "Рубцовск",
                "street": "Комсомольская",
                "building": "71А",
                "inn": "2222057844",
            }
        ]
    )
    contract_df = pd.DataFrame(
        [
            {
                "№ ": "Р/1",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Горизонт" Алейский мясокомбинат',
                "Наименование ИОО": 'магазин"Алейский мясокомбинат"',
                "ИНН": "2222057844",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            },
            {
                "№ ": "Р/2",
                "Дата": "15.12.2022",
                "Наименование потребителя": 'ООО "Тест"',
                "Наименование ИОО": "Не найденный объект",
                "ИНН": "1234567890",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Ленина",
                "дом": "1",
            },
        ]
    )

    with Session(engine) as session:
        result = ImportService().import_dataframe(session, main_df, contract_df)
        unresolved_rows = ContractRowRepository.list_unresolved(session)
        all_rows = session.scalars(select(ContractRow).order_by(ContractRow.source_row_index)).all()

    assert result.contracts_loaded == 2
    assert len(all_rows) == 2
    assert all_rows[0].linked_waste_object_id is not None
    assert all_rows[0].link_mode == "auto"
    assert all_rows[1].linked_waste_object_id is None
    assert all_rows[1].link_mode == "none"
    assert len(unresolved_rows) == 1
    assert unresolved_rows[0].contract_number == "Р/2"


def test_import_service_marks_address_only_match_as_review_without_contract_data_transfer():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    main_df = pd.DataFrame(
        [
            {
                "name": "Точный объект",
                "category": "Категория",
                "city": "Рубцовск",
                "street": "Комсомольская",
                "building": "71А",
            }
        ]
    )
    contract_df = pd.DataFrame(
        [
            {
                "№ ": "Р/77",
                "Дата": "14.12.2022",
                "Наименование потребителя": 'ООО "Контрагент"',
                "Наименование ИОО": "Совсем другое имя",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "71А",
            }
        ]
    )

    with Session(engine) as session:
        result = ImportService().import_dataframe(session, main_df, contract_df)
        item = session.scalars(select(WasteObject)).first()
        unresolved_rows = ContractRowRepository.list_unresolved(session)

    assert result.contracts_matched == 0
    assert item is not None
    assert item.contract_link_status == "review_required"
    assert item.contract_link_strategy == "address_plus"
    assert item.contract_number is None
    assert item.contract_date is None
    assert len(unresolved_rows) == 1
    assert unresolved_rows[0].contract_link_status == "review_required"
    assert unresolved_rows[0].contract_link_strategy == "address_plus"


def test_reimport_recalculates_old_inexact_match_and_replaces_with_exact():
    main_df = pd.DataFrame(
        [
            {
                "Наименование организации": "Джамп, фитнес-центр",
                "Рубрики": "Спортивные клубы, центры, комплексы",
                "Субъект": "Алтайский край",
                "Регион": "Рубцовск городской округ",
                "Город": "Рубцовск (Рубцовск городской округ)",
                "Улица": "проспект Ленина",
                "Номер дома": "206",
                "Этаж": "5",
                "ИНН": "220908543465",
                "Юридическое наименование": "Польников Евгений Викторович",
            }
        ]
    )
    first_contract_df = pd.DataFrame(
        [
            {
                "№ ": "Р/339",
                "Дата": "01.01.2023",
                "Наименование потребителя": "ИП Маньшин Александр Викторович",
                "Наименование ИОО": "офис",
                "ИНН": "220901144863",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "ул",
                "улица": "Комсомольская",
                "дом": "111",
                "тип пом": "пом",
                "помещение": "3",
            }
        ]
    )
    second_contract_df = pd.DataFrame(
        [
            {
                "№ ": "Р/564",
                "Дата": "30.05.2023",
                "Наименование потребителя": "ИП Польников Евгений Викторович",
                "Наименование ИОО": 'Фитнес клуб "Джамп"',
                "ИНН": "220908543465",
                "тип населенного пункта": "город",
                "населенный пункт": "Рубцовск",
                "тип улицы": "проспект",
                "улица": "Ленина",
                "дом": "206",
            }
        ]
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ImportService()

    with Session(engine) as session:
        first = service.import_dataframe(session, main_df, contract_dataframe=first_contract_df)
        second = service.import_dataframe(session, main_df, contract_dataframe=second_contract_df)
        item = session.scalars(select(WasteObject)).first()

    assert first.contracts_matched == 0
    assert second.contracts_matched == 1
    assert item is not None
    assert item.contract_number == "Р/564"
    assert item.contract_link_status == "matched"
    assert item.contract_link_strategy == "address_name_inn_plus"
