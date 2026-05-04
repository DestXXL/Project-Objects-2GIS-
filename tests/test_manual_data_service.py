from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import ContractRow, LegalEntity, RealEstate, WasteObject
from app.repositories.legal_entity_repository import LegalEntityRepository
from app.repositories.real_estate_repository import RealEstateRepository
from app.repositories.waste_object_repository import WasteObjectRepository
from app.services.manual_data_service import ManualDataService
from app.utils.normalization import normalize_address_key


def test_manual_data_service_updates_real_estate_fields_and_address_key():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ManualDataService()

    with Session(engine) as session:
        real_estate = RealEstate(
            address="Старый адрес",
            address_key=normalize_address_key("Старый адрес"),
            city="Рубцовск",
        )
        session.add(real_estate)
        session.flush()

        service.update_real_estate(
            session,
            real_estate,
            {
                "address": "658200, Алтайский край, Рубцовск, ул. Комсомольская, д. 256",
                "district": "Рубцовский район",
                "city": "Рубцовск",
                "street": "Комсомольская",
                "building": "256",
                "area": "124.5",
                "floors": "2",
                "purpose": "Торговое",
                "object_type": "Нежилое здание",
            },
        )
        session.commit()

        updated = session.scalar(select(RealEstate).where(RealEstate.id == real_estate.id))

    assert updated is not None
    assert updated.address == "658200, Алтайский край, Рубцовск, ул. Комсомольская, д. 256"
    assert updated.address_key == normalize_address_key(updated.address)
    assert updated.area == 124.5
    assert updated.floors == 2
    assert updated.object_type == "Нежилое здание"


def test_manual_data_service_creates_and_links_legal_entity_from_waste_object():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ManualDataService()

    with Session(engine) as session:
        real_estate = RealEstate(
            address="Рубцовск, Комсомольская, 256",
            address_key=normalize_address_key("Рубцовск, Комсомольская, 256"),
        )
        waste_object = WasteObject(
            real_estate=real_estate,
            name="Маяк",
            source_row_index=1,
        )
        session.add_all([real_estate, waste_object])
        session.flush()

        service.update_waste_object(
            session,
            waste_object,
            {
                "name": 'Магазин стройматериалов "Формула М2"',
                "category": "Магазин стройматериалов",
                "waste_type": "ТКО",
                "calculation_value": "1.1",
                "billing_method": "по нормативу",
                "inn": "5408186470",
                "legal_entity_name": 'ООО "ИКТОНИКС ТРЕЙД"',
                "contact_person": "Иван Петров",
                "phone": "+7 999 000-00-00",
                "email": "office@example.com",
                "contract_number": "Р/891",
                "contract_date": "16.07.2024",
                "comment": "Дополнено вручную",
            },
        )
        session.commit()

        updated = session.scalar(select(WasteObject).where(WasteObject.id == waste_object.id))
        entity = session.scalar(select(LegalEntity).where(LegalEntity.inn == "5408186470"))

    assert updated is not None
    assert entity is not None
    assert updated.legal_entity_id == entity.id
    assert updated.inn == "5408186470"
    assert updated.contract_number == "Р/891"
    assert str(updated.contract_date) == "2024-07-16"
    assert entity.name == 'ООО "ИКТОНИКС ТРЕЙД"'
    assert entity.contact_person == "Иван Петров"


def test_manual_data_service_creates_multiple_legal_entities_from_split_inn_value():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ManualDataService()

    with Session(engine) as session:
        real_estate = RealEstate(
            address="Рубцовск, Комсомольская, 256",
            address_key=normalize_address_key("Рубцовск, Комсомольская, 256"),
        )
        waste_object = WasteObject(
            real_estate=real_estate,
            name="Объект с несколькими ИНН",
            source_row_index=1,
        )
        session.add_all([real_estate, waste_object])
        session.flush()

        service.update_waste_object(
            session,
            waste_object,
            {
                "name": "Объект с несколькими ИНН",
                "category": "Категория",
                "inn": "2209011216|2209019999",
                "legal_entity_name": "Организация",
            },
        )
        session.commit()

        updated = session.scalar(select(WasteObject).where(WasteObject.id == waste_object.id))
        entities = session.scalars(select(LegalEntity).order_by(LegalEntity.inn)).all()

    assert updated is not None
    assert updated.inn == "2209011216|2209019999"
    assert len(entities) == 2
    assert [entity.inn for entity in entities] == ["2209011216", "2209019999"]
    assert updated.legal_entity_id == entities[0].id


def test_manual_data_service_updates_legal_entity_inn_for_linked_waste_objects():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ManualDataService()

    with Session(engine) as session:
        entity = LegalEntity(inn="2209011216", name="БИС")
        real_estate = RealEstate(
            address="Рубцовск, Гражданский, 41",
            address_key=normalize_address_key("Рубцовск, Гражданский, 41"),
        )
        waste_object = WasteObject(
            real_estate=real_estate,
            legal_entity=entity,
            inn="2209011216",
            name="Библиотека",
            source_row_index=1,
        )
        session.add_all([entity, real_estate, waste_object])
        session.flush()

        service.update_legal_entity(
            session,
            entity,
            {
                "inn": "2209019999",
                "name": "Библиотечная информационная система",
                "contact_person": "Секретарь",
                "phone": "8-38557-00-00",
                "email": "bis@example.com",
            },
        )
        session.commit()

        updated_entity = session.scalar(select(LegalEntity).where(LegalEntity.id == entity.id))
        updated_waste = session.scalar(select(WasteObject).where(WasteObject.id == waste_object.id))

    assert updated_entity is not None
    assert updated_waste is not None
    assert updated_entity.inn == "2209019999"
    assert updated_entity.name == "Библиотечная информационная система"
    assert updated_waste.inn == "2209019999"


def test_repository_filters_support_exact_and_partial_search():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        entity = LegalEntity(inn="2209011216", name="Библиотечная информационная система")
        real_estate = RealEstate(
            address="658200, Алтайский край, Рубцовск, Гражданский переулок, д. 41",
            address_key=normalize_address_key("658200, Алтайский край, Рубцовск, Гражданский переулок, д. 41"),
        )
        waste_object = WasteObject(
            real_estate=real_estate,
            legal_entity=entity,
            inn="2209011216",
            name="Спецбиблиотека для незрячих",
            category="Библиотеки, архивы",
            contract_number="Р/351/24",
            source_row_index=1,
        )
        session.add_all([entity, real_estate, waste_object])
        session.commit()

        waste_exact = WasteObjectRepository.list(session, {"name": "Спецбиблиотека для незрячих"})
        waste_partial = WasteObjectRepository.list(session, {"name": "библиотека незрячих"})
        address_partial = RealEstateRepository.list_with_counts(session, {"address": "Рубцовск 41 гражданский"})
        legal_partial = LegalEntityRepository.list_with_counts(session, {"name": "информационная библиотечная"})

    assert len(waste_exact) == 1
    assert len(waste_partial) == 1
    assert len(address_partial) == 1
    assert len(legal_partial) == 1


def test_manual_data_service_binds_contract_row_to_waste_object():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = ManualDataService()

    with Session(engine) as session:
        real_estate = RealEstate(
            address="Рубцовск, проспект Ленина, 206",
            address_key=normalize_address_key("Рубцовск, проспект Ленина, 206"),
        )
        waste_object = WasteObject(
            real_estate=real_estate,
            name="Jump, фитнес-центр",
            category="Спортивные клубы",
            source_row_index=1,
        )
        contract_row = ContractRow(
            source_row_index=10,
            contract_number="Р/564",
            contract_date=None,
            legal_entity_name="ИП Польников Евгений Викторович",
            waste_object_name='Фитнес клуб "Джамп"',
            inn="220908543465",
            address="г. Рубцовск, пр-т Ленина, 206",
            volume=1.5,
            quantity=1,
            pickup_frequency="по нормативу",
            comment="подписано",
            link_mode="none",
        )
        session.add_all([real_estate, waste_object, contract_row])
        session.flush()

        service.bind_contract_row_to_waste_object(session, contract_row, waste_object)
        session.commit()

        updated_row = session.scalar(select(ContractRow).where(ContractRow.id == contract_row.id))
        updated_waste = session.scalar(select(WasteObject).where(WasteObject.id == waste_object.id))
        entity = session.scalar(select(LegalEntity).where(LegalEntity.inn == "220908543465"))

    assert updated_row is not None
    assert updated_waste is not None
    assert entity is not None
    assert updated_row.linked_waste_object_id == updated_waste.id
    assert updated_row.link_mode == "manual"
    assert updated_row.contract_link_status == "matched"
    assert updated_waste.contract_number == "Р/564"
    assert updated_waste.calculation_value == "1.5"
    assert updated_waste.billing_method == "по нормативу"
    assert updated_waste.contract_link_strategy == "manual"
    assert updated_waste.legal_entity_id == entity.id
