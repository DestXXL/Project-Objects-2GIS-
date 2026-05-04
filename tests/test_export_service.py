from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.repositories.legal_entity_repository import LegalEntityRepository
from app.repositories.real_estate_repository import RealEstateRepository
from app.repositories.waste_object_repository import WasteObjectRepository
from app.services.export_service import ExportService


def test_export_service_builds_expected_frames():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ExportService()

    with Session(engine) as session:
        real_estate = RealEstateRepository.create(
            session,
            address="658200, Алтайский край, Рубцовск, Комсомольская, д. 10",
            address_key="rubtsovsk|komsomolskaya|10",
            district="Рубцовский",
            city="Рубцовск",
            street="Комсомольская",
            building="10",
        )
        legal_entity = LegalEntityRepository.create(
            session,
            inn="2209000000",
            name='ООО "Тест"',
            contact_person="Иванов И.И.",
        )
        WasteObjectRepository.create(
            session,
            real_estate_id=real_estate.id,
            legal_entity_id=legal_entity.id,
            name="Магазин",
            category="Продовольственный магазин",
            inn="2209000000",
            contract_number="Р/10",
            source_row_index=2,
            contract_link_status="matched",
        )
        session.commit()

        frames = service.build_export_frames(session)

    assert set(frames) == {"Сводная выгрузка", "Объекты отходов", "Недвижимость", "Юрлица"}
    assert len(frames["Сводная выгрузка"]) == 1
    assert frames["Сводная выгрузка"].iloc[0]["Адрес"] == "658200, Алтайский край, Рубцовск, Комсомольская, д. 10"
    assert frames["Сводная выгрузка"].iloc[0]["Наименование юрлица"] == 'ООО "Тест"'
    assert frames["Недвижимость"].iloc[0]["Количество связанных объектов отходов"] == 1
    assert frames["Юрлица"].iloc[0]["Количество связанных объектов отходов"] == 1


def test_export_service_writes_excel_file(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ExportService()
    output_path = tmp_path / "export.xlsx"

    with Session(engine) as session:
        real_estate = RealEstateRepository.create(
            session,
            address="г. Рубцовск, ул. Северная, д. 1",
            address_key="rubtsovsk|severnaya|1",
        )
        WasteObjectRepository.create(
            session,
            real_estate_id=real_estate.id,
            legal_entity_id=None,
            name="Объект без юрлица",
            category="Категория",
            source_row_index=2,
        )
        session.commit()
        service.export_to_excel(session, output_path)

    workbook = pd.ExcelFile(output_path)
    assert set(workbook.sheet_names) == {"Сводная выгрузка", "Объекты отходов", "Недвижимость", "Юрлица"}


def test_export_service_builds_reference_comparison_frame(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ExportService()
    reference_path = tmp_path / "reference.xlsx"

    pd.DataFrame(
        [
            {
                "Наименование организации": "Эталонный объект",
                24: 3,
                "Город": "Рубцовск",
                "Улица": "Комсомольская",
                "Номер дома": "10",
                "Номер договора": "Р/10",
            }
        ]
    ).to_excel(reference_path, index=False)

    with Session(engine) as session:
        real_estate = RealEstateRepository.create(
            session,
            address="Рубцовск, Комсомольская, д. 10",
            address_key="rubtsovsk|komsomolskaya|10",
        )
        WasteObjectRepository.create(
            session,
            real_estate_id=real_estate.id,
            legal_entity_id=None,
            name="Мой объект",
            category="Категория",
            contract_number="Р/10",
            contract_link_strategy="address_name_inn_plus",
            source_row_index=2,
        )
        session.commit()

        frame = service.build_comparison_frame(session, reference_path)

    row = frame.iloc[0]
    assert row["№ строки 2GIS"] == 2
    assert row["Адрес"] == "Рубцовск, Комсомольская, 10"
    assert row["Эталон: номер договора"] == "Р/10"
    assert row["Моя база: номер договора"] == "Р/10"
    assert row["Эталон: 24 столбец"] == 3
    assert row["Моя база: 24 столбец"] == 3
    assert row["Эталон: наименование объекта"] == "Эталонный объект"
    assert row["Моя база: наименование объекта"] == "Мой объект"
