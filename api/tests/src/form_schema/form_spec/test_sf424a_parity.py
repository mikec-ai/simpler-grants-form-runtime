"""SF-424A, the budget form: four questions asked twice, and 35 calculations.

This is the form the design had to survive. Its arithmetic is the part of SGG's form
definitions that the forms README says can only be recovered by reading the paper form, and
its evaluation order is hand-numbered. Both are derived here.
"""

import copy
from pathlib import Path

import pytest

import src.form_schema.forms as forms_package
from src.form_schema.form_spec.loader import load_form
from src.form_schema.forms._loader import load_versioned_form
from src.form_schema.jsonschema_resolver import resolve_jsonschema
from tests.src.form_schema.form_spec import parity

FORM_DIR = "sf424a"
FORM_ID = "sf424a"

#: Fields the golden spells out inline that the bank now owns.
COMPOSED: dict[str, str] = {}

_MONEY = "the monetary-amount question carries a description where the golden's shared primitive has none"
_TABLE = "the budget question carries a label where the golden's def has none"
_EMPTY_REQUIRED = "the golden writes an empty `required`, which asserts nothing"

HAND_WRITTEN = {
    "/description": "the form's own description",
    # The five budget tables are bank questions now, so they are referenced rather than
    # copied into this form's `$defs`. The content is the same; only where it is written
    # down moved, and the behavioural test is what checks that.
    "/$defs/*": "the five budget tables are referenced from the bank, not held locally",
    "*/properties/activity_line_items/items/properties/budget_summary/allOf/0/title": _TABLE,
    "*/properties/activity_line_items/items/properties/budget_categories/allOf/0/title": _TABLE,
    "*/properties/activity_line_items/items/properties/non_federal_resources/allOf/0/title": (
        _TABLE
    ),
    "*/properties/activity_line_items/items/properties/federal_fund_estimates/allOf/0/title": (
        _TABLE
    ),
    "*/properties/total_budget_summary/allOf/0/title": _TABLE,
    "*/properties/total_budget_categories/allOf/0/title": _TABLE,
    "*/properties/total_non_federal_resources/allOf/0/title": _TABLE,
    "*/properties/total_federal_fund_estimates/allOf/0/title": _TABLE,
    "*/federal_forecasted_cash_needs/allOf/0/title": _TABLE,
    "*/non_federal_forecasted_cash_needs/allOf/0/title": _TABLE,
    "*/total_forecasted_cash_needs/allOf/0/title": _TABLE,
    "*/allOf/0/description": _MONEY,
    "*/allOf/0/required": _EMPTY_REQUIRED,
    "/properties/forecasted_cash_needs/required": _EMPTY_REQUIRED,
}


@pytest.fixture(scope="module")
def golden():
    return load_versioned_form(Path(forms_package.__file__).parent / FORM_DIR, "1.0")


@pytest.fixture(scope="module")
def projected():
    return load_form(FORM_ID)


@pytest.fixture(scope="module")
def resolved_golden(golden):
    return resolve_jsonschema(copy.deepcopy(golden.FORM_JSON_SCHEMA))


@pytest.fixture(scope="module")
def resolved_projected(projected):
    return resolve_jsonschema(copy.deepcopy(projected.form_json_schema))


@pytest.fixture
def seeds():
    def summary(base):
        return {
            "federal_estimated_unobligated_amount": f"{base}.00",
            "non_federal_estimated_unobligated_amount": "0.00",
            "federal_new_or_revised_amount": f"{base}.00",
            "non_federal_new_or_revised_amount": "0.00",
            "total_amount": f"{base * 2}.00",
        }

    def categories(base):
        return {
            "personnel_amount": f"{base}.00",
            "fringe_benefits_amount": "0.00",
            "travel_amount": "0.00",
            "equipment_amount": "0.00",
            "supplies_amount": "0.00",
            "contractual_amount": "0.00",
            "construction_amount": "0.00",
            "other_amount": "0.00",
            "total_direct_charge_amount": f"{base}.00",
            "total_indirect_charge_amount": "0.00",
            "total_amount": f"{base}.00",
            "program_income_amount": "0.00",
        }

    def quarters():
        return {
            "first_quarter_amount": "1.00",
            "second_quarter_amount": "1.00",
            "third_quarter_amount": "1.00",
            "fourth_quarter_amount": "1.00",
            "total_amount": "4.00",
        }

    full = {
        "activity_line_items": [
            {
                "activity_title": "Outreach",
                "assistance_listing_number": "12.345",
                "budget_summary": summary(100),
                "budget_categories": categories(100),
                "non_federal_resources": {
                    "grant_program": "Outreach",
                    "applicant_amount": "10.00",
                    "state_amount": "0.00",
                    "other_amount": "0.00",
                    "total_amount": "10.00",
                },
                "federal_fund_estimates": {
                    "grant_program": "Outreach",
                    "first_year_amount": "100.00",
                    "second_year_amount": "0.00",
                    "third_year_amount": "0.00",
                    "fourth_year_amount": "0.00",
                },
            },
        ],
        "total_budget_summary": summary(100),
        "total_budget_categories": categories(100),
        "total_non_federal_resources": {
            "grant_program": "All",
            "applicant_amount": "10.00",
            "state_amount": "0.00",
            "other_amount": "0.00",
            "total_amount": "10.00",
        },
        "forecasted_cash_needs": {
            "federal_forecasted_cash_needs": quarters(),
            "non_federal_forecasted_cash_needs": quarters(),
            "total_forecasted_cash_needs": quarters(),
        },
        "total_federal_fund_estimates": {
            "grant_program": "All",
            "first_year_amount": "100.00",
            "second_year_amount": "0.00",
            "third_year_amount": "0.00",
            "fourth_year_amount": "0.00",
        },
        "direct_charges_explanation": "None",
        "indirect_charges_explanation": "Provisional 10%",
        "remarks": "No remarks.",
        "confirmation": True,
    }
    minimal = {
        "activity_line_items": [{"activity_title": "Outreach"}],
        "confirmation": True,
    }
    return [full, minimal]


def test_ui_schema_is_identical(projected, golden):
    assert projected.form_ui_schema == golden.FORM_UI_SCHEMA


def test_rule_schema_is_identical(projected, golden):
    """All 35 calculations, including every `order`, from eight declarations."""
    assert projected.form_rule_schema == golden.FORM_RULE_SCHEMA


def test_structural_differences_are_all_accounted_for(resolved_projected, resolved_golden):
    differences = parity.schema_differences(resolved_projected, resolved_golden)
    assert parity.unexplained(differences, ALLOWED) == []


def test_allow_list_has_no_dead_entries(resolved_projected, resolved_golden):
    differences = parity.schema_differences(resolved_projected, resolved_golden)
    assert parity.unused(differences, HAND_WRITTEN) == []
    assert parity.unused_fields(differences, COMPOSED) == []


def test_validation_verdicts_are_identical(resolved_projected, resolved_golden, seeds):
    payloads = parity.corpus(resolved_golden, seeds)
    assert len(payloads) > 300, "the corpus should exercise every field"
    assert parity.behavioural_differences(resolved_projected, resolved_golden, payloads) == []


ALLOWED = {**parity.composed(COMPOSED), **HAND_WRITTEN}
