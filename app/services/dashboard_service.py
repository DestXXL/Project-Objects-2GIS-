from sqlalchemy.orm import Session

from app.repositories.legal_entity_repository import LegalEntityRepository
from app.repositories.real_estate_repository import RealEstateRepository
from app.repositories.waste_object_repository import WasteObjectRepository
from app.schemas.dashboard import DashboardStats


class DashboardService:
    def get_stats(self, db: Session) -> DashboardStats:
        return DashboardStats(
            real_estates=RealEstateRepository.count(db),
            waste_objects=WasteObjectRepository.count(db),
            legal_entities=LegalEntityRepository.count(db),
        )

