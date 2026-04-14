from pydantic import BaseModel


class DashboardStats(BaseModel):
    real_estates: int
    waste_objects: int
    legal_entities: int

