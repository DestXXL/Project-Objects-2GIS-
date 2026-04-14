from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import LegalEntity, RealEstate, WasteObject
from app.repositories.legal_entity_repository import LegalEntityRepository
from app.repositories.real_estate_repository import RealEstateRepository
from app.repositories.waste_object_repository import WasteObjectRepository
from app.schemas.imports import ResetDataResult


class DataResetService:
    def reset_all_imported_data(self, db: Session) -> ResetDataResult:
        result = ResetDataResult(
            real_estates_deleted=RealEstateRepository.count(db),
            waste_objects_deleted=WasteObjectRepository.count(db),
            legal_entities_deleted=LegalEntityRepository.count(db),
        )

        db.execute(delete(WasteObject))
        db.execute(delete(LegalEntity))
        db.execute(delete(RealEstate))
        db.commit()

        return result
