from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import LegalEntity, RealEstate, WasteObject
from app.services.data_reset_service import DataResetService


def test_data_reset_service_removes_imported_entities():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        real_estate = RealEstate(address="Адрес", address_key="адрес")
        legal_entity = LegalEntity(inn="1234567890", name="Тест")
        session.add_all([real_estate, legal_entity])
        session.flush()
        session.add(
            WasteObject(
                real_estate_id=real_estate.id,
                legal_entity_id=legal_entity.id,
                name="Объект",
                source_row_index=1,
            )
        )
        session.commit()

        result = DataResetService().reset_all_imported_data(session)

        assert result.real_estates_deleted == 1
        assert result.waste_objects_deleted == 1
        assert result.legal_entities_deleted == 1
        assert session.query(RealEstate).count() == 0
        assert session.query(WasteObject).count() == 0
        assert session.query(LegalEntity).count() == 0
