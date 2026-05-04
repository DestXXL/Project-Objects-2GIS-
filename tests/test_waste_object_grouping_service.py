from types import SimpleNamespace

from app.services.waste_object_grouping_service import WasteObjectGroupingService


def test_split_by_enrichment_groups_items_by_data_completeness():
    enriched = SimpleNamespace(
        inn="2222222222",
        legal_entity_id=1,
        contract_number="Р/1",
        contract_date="2024-01-01",
        contract_start_date=None,
        billing_method="по графику",
        calculation_value="1.1",
        comment="подписано",
    )
    incomplete = SimpleNamespace(
        inn=None,
        legal_entity_id=None,
        contract_number=None,
        contract_date=None,
        contract_start_date=None,
        billing_method=None,
        calculation_value=None,
        comment=None,
    )

    result = WasteObjectGroupingService.split_by_enrichment([enriched, incomplete])

    assert result.enriched_items == [enriched]
    assert result.incomplete_items == [incomplete]
