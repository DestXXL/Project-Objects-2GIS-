import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.schemas.imports import ParsedImportRow
from app.db import Base
from app.models import WasteObject
from app.services.contract_matching_service import ContractMatchingService
from app.services.import_service import ImportService


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
        city="Рубцовск (Рубцовск городской округ)",
        street="Комсомольская",
        building="71А",
        inn="2222057844",
    )

    match = matcher.match(row)

    assert match is not None
    assert match.contract_number == "Р/1"
    assert match.calculation_value == "1.11"
    assert match.waste_generation_norm == "по нормативу"
    assert match.billing_method == "по нормативу"


def test_import_service_enriches_empty_fields_from_contract():
    row = ParsedImportRow(
        source_row_index=2,
        name="Магазин",
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
    ).match(row)

    ImportService._enrich_from_contract(row, contract)

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
