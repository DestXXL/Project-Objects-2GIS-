from app.utils.normalization import normalize_address_key, normalize_inn, normalize_text
from app.services.address_normalization_service import AddressNormalizationService


def test_normalize_text_trims_whitespace():
    assert normalize_text("  test   value  ") == "test value"


def test_normalize_inn_keeps_digits_only():
    assert normalize_inn("ИНН 7701234567") == "7701234567"


def test_normalize_address_key_is_case_insensitive():
    assert normalize_address_key("Москва, Улица Ленина 1") == normalize_address_key("москва, улица ленина 1")


def test_normalize_inn_from_excel_float_keeps_original_number():
    assert normalize_inn(222200228886.0) == "222200228886"


def test_address_service_builds_precise_address_from_parts():
    service = AddressNormalizationService()

    result = service.normalize(
        address=None,
        postal_code="141400",
        region="Московская область",
        city="Химки",
        street="ул. Заводская",
        building="15",
        floor="2",
        office="42",
        block="2",
        structure="1",
    )

    assert result == "141400, Московская область, Химки, ул. Заводская, д. 15, эт. 2, оф. 42, корп. 2, стр. 1"
