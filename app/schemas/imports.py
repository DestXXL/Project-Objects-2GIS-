from datetime import date
from typing import Optional

from pydantic import BaseModel


class ParsedImportRow(BaseModel):
    source_row_index: int
    postal_code: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    settlement: Optional[str] = None
    street: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    office: Optional[str] = None
    block: Optional[str] = None
    structure: Optional[str] = None
    room: Optional[str] = None
    cadastral_number: Optional[str] = None
    area: Optional[float] = None
    floors: Optional[int] = None
    purpose: Optional[str] = None
    object_type: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    waste_type: Optional[str] = None
    waste_generation_norm: Optional[str] = None
    calculation_unit: Optional[str] = None
    calculation_value: Optional[str] = None
    billing_method: Optional[str] = None
    inn: Optional[str] = None
    contract_number: Optional[str] = None
    contract_date: Optional[date] = None
    legal_entity_name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    contract_start_date: Optional[date] = None
    comment: Optional[str] = None


class ContractMatchData(BaseModel):
    contract_number: Optional[str] = None
    contract_date: Optional[date] = None
    legal_entity_name: Optional[str] = None
    waste_object_name: Optional[str] = None
    contact_person: Optional[str] = None
    calculation_value: Optional[str] = None
    calculation_unit: Optional[str] = None
    waste_generation_norm: Optional[str] = None
    billing_method: Optional[str] = None
    contract_start_date: Optional[date] = None
    comment: Optional[str] = None


class ImportResult(BaseModel):
    processed_rows: int
    unique_addresses: int
    real_estates_created: int
    waste_objects_created: int
    legal_entities_created: int
    skipped_rows: int = 0
    contracts_loaded: int = 0
    contracts_matched: int = 0


class ResetDataResult(BaseModel):
    real_estates_deleted: int
    waste_objects_deleted: int
    legal_entities_deleted: int
