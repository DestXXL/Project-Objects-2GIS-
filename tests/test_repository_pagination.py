from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.repositories.legal_entity_repository import LegalEntityRepository
from app.repositories.real_estate_repository import RealEstateRepository
from app.repositories.waste_object_repository import WasteObjectRepository


def test_real_estate_repository_page_returns_total_and_slice():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        for index in range(5):
            RealEstateRepository.create(
                session,
                address=f"Адрес {index}",
                address_key=f"address-{index}",
            )
        session.commit()

        rows, total = RealEstateRepository.list_with_counts_page(session, limit=2, offset=2)

    assert total == 5
    assert len(rows) == 2
    assert [entity.address for entity, _count in rows] == ["Адрес 2", "Адрес 3"]


def test_waste_object_repository_page_orders_contracts_first():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        real_estate = RealEstateRepository.create(
            session,
            address="г. Рубцовск, ул. Комсомольская, д. 1",
            address_key="rubtsovsk|komsomolskaya|1",
        )
        WasteObjectRepository.create(
            session,
            real_estate_id=real_estate.id,
            legal_entity_id=None,
            name="Без договора",
            contract_number=None,
            source_row_index=2,
        )
        WasteObjectRepository.create(
            session,
            real_estate_id=real_estate.id,
            legal_entity_id=None,
            name="С договором",
            contract_number="Р/1",
            source_row_index=3,
        )
        session.commit()

        rows, total = WasteObjectRepository.list_page(session, limit=10, offset=0)

    assert total == 2
    assert [item.name for item in rows] == ["С договором", "Без договора"]


def test_waste_object_repository_filters_by_link_strategy_label_and_code():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        real_estate = RealEstateRepository.create(
            session,
            address="г. Рубцовск, ул. Комсомольская, д. 1",
            address_key="rubtsovsk|komsomolskaya|1",
        )
        WasteObjectRepository.create(
            session,
            real_estate_id=real_estate.id,
            legal_entity_id=None,
            name="Только адрес",
            source_row_index=2,
            contract_link_strategy="address_plus",
            contract_link_status="review_required",
        )
        WasteObjectRepository.create(
            session,
            real_estate_id=real_estate.id,
            legal_entity_id=None,
            name="Полное совпадение",
            source_row_index=3,
            contract_link_strategy="address_name_inn_plus",
            contract_link_status="matched",
        )
        session.commit()

        by_label = WasteObjectRepository.list(session, {"link_strategy": "адрес+"})
        by_code = WasteObjectRepository.list(session, {"link_strategy": "address_plus"})
        by_checked_values = WasteObjectRepository.list(
            session,
            {"link_strategy": "address_plus|address_name_inn_minus"},
        )

    assert [item.name for item in by_label] == ["Только адрес"]
    assert [item.name for item in by_code] == ["Только адрес"]
    assert [item.name for item in by_checked_values] == ["Только адрес"]


def test_legal_entity_repository_page_returns_total_and_slice():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        for index in range(4):
            LegalEntityRepository.create(
                session,
                inn=f"220900000{index}",
                name=f"Юрлицо {index}",
            )
        session.commit()

        rows, total = LegalEntityRepository.list_with_counts_page(session, limit=2, offset=1)

    assert total == 4
    assert len(rows) == 2
    assert [entity.inn for entity, _count in rows] == ["2209000001", "2209000002"]
