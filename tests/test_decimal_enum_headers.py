from decimal import Decimal

from solution.catalog import load_catalog
from solution.normalize.decimals import parse_decimal
from solution.normalize.enums import parse_enum
from solution.normalize.headers import map_headers, normalise_header


def test_decimal_currency_forms():
    assert parse_decimal("₹12,000") == Decimal("12000.00")
    assert parse_decimal("Rs. 1500") == Decimal("1500.00")
    assert parse_decimal("INR 99.1") == Decimal("99.10")
    assert parse_decimal("N/A") is None
    assert parse_decimal("-1") is None


def test_enum_case_insensitive():
    assert parse_enum("HI", ["en", "hi"]) == "hi"
    assert parse_enum("Hindi", ["en", "hi"]) is None


def test_header_normalise():
    assert normalise_header(" Mobile_No ") == "mobile no"
    assert normalise_header("Policy   Number") == "policy number"


def test_header_aliases_motor():
    catalog = load_catalog()
    schema = catalog.workflows["motor_renewal"]
    mapping = map_headers(
        ["Insured Name", "Mobile No", "Policy No", "agent_notes"],
        schema,
    )
    assert mapping["Insured Name"] == "customer_name"
    assert mapping["Mobile No"] == "phone"
    assert mapping["Policy No"] == "policy_number"
    assert mapping["agent_notes"] is None
