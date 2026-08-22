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

#: Differences between what this form renders and what the golden renders. Each key is
#: `<pointer>#<keyword>`, each value says why the difference is deliberate, and anything not
#: listed fails the test.
#:
#: All four are the same decision: the golden's five budget tables are anonymous `$defs`, and
#: the bank's are questions with names and descriptions. Additive, and these four properties
#: are handed to a purpose-built component that lays out its own headings.
RENDERED = {
    "/properties/total_budget_summary#title": "bank question is named",
    "/properties/total_budget_summary#description": "bank question describes itself",
    "/properties/total_budget_categories#title": "bank question is named",
    "/properties/total_budget_categories#description": "bank question describes itself",
    "/properties/total_non_federal_resources#title": "bank question is named",
    "/properties/total_non_federal_resources#description": "bank question describes itself",
    "/properties/total_federal_fund_estimates#title": "bank question is named",
    "/properties/total_federal_fund_estimates#description": "bank question describes itself",
}

#: Verdicts that differ. Empty, and worth keeping that way.
ALLOWED_BEHAVIOR: dict[tuple[str, str], str] = {}


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
    """Same fields, in the same order, in the same sections."""
    assert projected.form_ui_schema == golden.FORM_UI_SCHEMA


def test_rule_schema_is_identical(projected, golden):
    assert projected.form_rule_schema == getattr(golden, "FORM_RULE_SCHEMA", None)


def test_every_rendered_field_matches(resolved_projected, resolved_golden, golden):
    """What an applicant reads, field by field, keyed by what the form renders."""
    differences = parity.rendered_differences(
        resolved_projected, resolved_golden, golden.FORM_UI_SCHEMA
    )
    assert parity.unexplained(differences, RENDERED) == []


def test_allow_list_has_no_dead_entries(resolved_projected, resolved_golden, golden):
    """An explanation for a difference that no longer exists is an explanation to delete."""
    differences = parity.rendered_differences(
        resolved_projected, resolved_golden, golden.FORM_UI_SCHEMA
    )
    assert parity.unused(differences, RENDERED) == []


def test_conditional_requiredness_matches(resolved_projected, resolved_golden):
    assert parity.conditional_branches(resolved_projected) == parity.conditional_branches(
        resolved_golden
    )


def test_no_reference_is_left_unresolved(resolved_projected):
    """A reference that failed to resolve would leave a `$ref` behind."""

    def refs(node):
        if isinstance(node, dict):
            return "$ref" in node or any(refs(v) for v in node.values())
        if isinstance(node, list):
            return any(refs(v) for v in node)
        return False

    assert not refs(resolved_projected)


def test_validation_verdicts_are_identical(resolved_projected, resolved_golden, seeds):
    """What an applicant may submit, over a corpus derived from the golden."""
    payloads = parity.corpus(resolved_golden, seeds)
    assert len(payloads) > 100, "the corpus should exercise every field"
    assert (
        parity.behavioral_differences(
            resolved_projected, resolved_golden, payloads, ALLOWED_BEHAVIOR
        )
        == []
    )
