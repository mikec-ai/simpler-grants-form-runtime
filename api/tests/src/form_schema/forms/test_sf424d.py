import importlib

import pytest

from src.form_schema.jsonschema_validator import validate_json_schema_for_form
from tests.src.form_schema.forms.conftest import validate_required

_FORM_MODULE = importlib.import_module("src.form_schema.forms.sf424d.1.0.form_json")


def test_sf424d_shared_composition_preserves_the_native_oracle() -> None:
    assert _FORM_MODULE.FORM_JSON_SCHEMA == _FORM_MODULE._ORACLE_FORM_JSON_SCHEMA
    assert _FORM_MODULE.FORM_UI_SCHEMA == _FORM_MODULE._ORACLE_FORM_UI_SCHEMA
    assert _FORM_MODULE.FORM_RULE_SCHEMA == _FORM_MODULE._ORACLE_FORM_RULE_SCHEMA
    assert (
        _FORM_MODULE.FORM_JSON_SCHEMA["properties"]
        == _FORM_MODULE._ASSURANCES_SIGNATURE.json_schema_properties
    )
    source_plan = _FORM_MODULE.FORM_XML_TRANSFORM_RULES["_xml_config"]["source_plan"]
    assert source_plan["contract"] == "source-pinned-xml-plan/v1"
    assert source_plan["runtime_profile"]["profile_id"] == "sf424d-native-v1"


@pytest.fixture
def minimal_valid_sf424d_v1_1() -> dict:
    return {
        "signature": "Jane Doe",
        "title": "Mrs.",
        "applicant_organization": "Place Business",
    }


@pytest.fixture
def full_valid_sf424d_v1_1(minimal_valid_sf424d_v1_1) -> dict:
    return minimal_valid_sf424d_v1_1 | {"date_signed": "2025-06-15"}


def test_sf424d_v1_1_minimal_valid_json(minimal_valid_sf424d_v1_1, sf424d_v1_1):
    validation_issues = validate_json_schema_for_form(minimal_valid_sf424d_v1_1, sf424d_v1_1)
    assert len(validation_issues) == 0


def test_sf424d_v1_1_full_valid_json(full_valid_sf424d_v1_1, sf424d_v1_1):
    validation_issues = validate_json_schema_for_form(full_valid_sf424d_v1_1, sf424d_v1_1)
    assert len(validation_issues) == 0


def test_sf424d_v1_1_empty_json(sf424d_v1_1):
    EXPECTED_REQUIRED_FIELDS = [
        "$.title",
        "$.applicant_organization",
    ]

    validate_required({}, EXPECTED_REQUIRED_FIELDS, sf424d_v1_1)


def test_sf424d_v1_1_min_length(sf424d_v1_1):
    data = {
        "signature": "",
        "title": "",
        "applicant_organization": "",
        "date_signed": "2025-01-01",
    }
    validation_issues = validate_json_schema_for_form(data, sf424d_v1_1)

    EXPECTED_ERROR_FIELDS = [
        "$.signature",
        "$.title",
        "$.applicant_organization",
    ]

    assert len(validation_issues) == len(EXPECTED_ERROR_FIELDS)
    for validation_issue in validation_issues:
        assert validation_issue.type == "minLength"
        assert validation_issue.field in EXPECTED_ERROR_FIELDS


def test_sf424d_v1_1_max_length(sf424d_v1_1):
    data = {
        "signature": "a" * 145,
        "title": "b" * 46,
        "applicant_organization": "c" * 61,
        "date_signed": "2025-01-01",
    }
    validation_issues = validate_json_schema_for_form(data, sf424d_v1_1)

    EXPECTED_ERROR_FIELDS = [
        "$.signature",
        "$.title",
        "$.applicant_organization",
    ]

    assert len(validation_issues) == len(EXPECTED_ERROR_FIELDS)
    for validation_issue in validation_issues:
        assert validation_issue.type == "maxLength"
        assert validation_issue.field in EXPECTED_ERROR_FIELDS


def test_sf424d_v1_1_date_field(minimal_valid_sf424d_v1_1, sf424d_v1_1):
    data = minimal_valid_sf424d_v1_1
    data["date_signed"] = "not-a-date"
    validation_issues = validate_json_schema_for_form(data, sf424d_v1_1)

    assert len(validation_issues) == 1
    assert validation_issues[0].type == "format"
    assert validation_issues[0].message == "'not-a-date' is not a 'date'"
