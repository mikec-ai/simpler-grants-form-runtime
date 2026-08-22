"""SF-424-Short: the form that asks one question twice.

Boxes 7 and 8 both ask for a contact -- name, title, address, telephone, fax, email -- about
two different people. The golden does it with a `$defs/contact_person_group` plus two Python
helpers that parameterise the UI children and the XML target by base path. Here it is
`poc/details`, composed twice, with this form's own member order and its own requirement that
a contact have a title.
"""

import copy
from pathlib import Path

import pytest

import src.form_schema.forms as forms_package
from src.form_schema.form_spec.loader import load_form
from src.form_schema.forms._loader import load_versioned_form
from src.form_schema.jsonschema_resolver import resolve_jsonschema
from tests.src.form_schema.form_spec import parity

FORM_DIR = "sf424_short"
FORM_ID = "sf424-short"

#: Differences between what this form renders and what the golden renders. Each key is
#: `<pointer>#<keyword>`, each value says why the difference is deliberate, and anything not
#: listed fails the test.
RENDERED = {
    # The golden marks three of its nine read-only fields `readOnly` in the schema as well as
    # `null` in the UI schema. Nothing reads the keyword -- the renderer takes read-only from
    # the UI schema and the API never looks -- so emitting it on three of nine would be
    # reproducing an inconsistency.
    "/properties/date_received#readOnly": "vestigial; the UI schema carries read-only",
    "/properties/aor_signature#readOnly": "vestigial; the UI schema carries read-only",
    "/properties/authorized_representative_date_signed#readOnly": (
        "vestigial; the UI schema carries read-only"
    ),
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
    def contact(first: str):
        return {
            "name": {"first_name": first, "last_name": "Richards"},
            "title": "Director",
            "address": {
                "street1": "123 Main Street",
                "city": "Placeville",
                "state": "WY: Wyoming",
                "zip_code": "56789-1234",
                "country": "USA: UNITED STATES",
            },
            "phone_number": "1234567890",
            "fax": "1112223333",
            "email": f"{first.lower()}@example.com",
        }

    full = {
        "agency_name": "Department of Everything",
        "assistance_listing_number": "12.345",
        "assistance_listing_program_title": "Everything Program",
        "date_received": "2026-01-05",
        "funding_opportunity_number": "EVERY-2026-001",
        "funding_opportunity_title": "Everything Opportunity",
        "organization_name": "Acme University",
        "applicant": {
            "street1": "1 Campus Drive",
            "street2": "Suite 4",
            "city": "Placeville",
            "county": "Place County",
            "state": "WY: Wyoming",
            "province": "Nowhere",
            "country": "USA: UNITED STATES",
            "zip_code": "56789-1234",
        },
        "applicant_web_address": "https://example.edu",
        "applicant_type_code": ["A: State Government", "X: Other (specify)"],
        "applicant_type_other_specify": "Consortium",
        "employer_taxpayer_identification_number": "123456789",
        "sam_uei": "ABCDEFGHIJKL",
        "congressional_district_applicant": "CA-005",
        "project_title": "A Study of Everything",
        "project_description": "Everything, studied.",
        "project_start_date": "2026-06-01",
        "project_end_date": "2027-05-31",
        "project_director": contact("Sue"),
        "same_as_project_director": False,
        "contact_person": contact("Joe"),
        "application_certification": True,
        "authorized_representative": {"first_name": "Reed", "last_name": "Richards"},
        "authorized_representative_title": "Provost",
        "authorized_representative_email": "provost@example.edu",
        "authorized_representative_phone_number": "5556667777",
        "authorized_representative_fax": "5556667778",
        "aor_signature": "Reed Richards",
        "authorized_representative_date_signed": "2026-02-02",
    }
    minimal = {
        "agency_name": "Department of Everything",
        "funding_opportunity_number": "EVERY-2026-001",
        "funding_opportunity_title": "Everything Opportunity",
        "organization_name": "Acme University",
        "applicant": {
            "street1": "456 Rio",
            "city": "Montevideo",
            "country": "URY: URUGUAY",
        },
        "applicant_type_code": ["P: Individual"],
        "employer_taxpayer_identification_number": "123456789",
        "sam_uei": "ABCDEFGHIJKL",
        "congressional_district_applicant": "00-000",
        "project_title": "A Study of Everything",
        "project_description": "Everything, studied.",
        "project_start_date": "2026-06-01",
        "project_end_date": "2027-05-31",
        "project_director": contact("Sue"),
        "contact_person": contact("Joe"),
        "application_certification": True,
        "authorized_representative": {"first_name": "Reed", "last_name": "Richards"},
        "authorized_representative_title": "Provost",
        "authorized_representative_email": "provost@example.edu",
        "authorized_representative_phone_number": "5556667777",
    }
    return [full, minimal]


def test_ui_schema_is_identical(projected, golden):
    """Same fields, in the same order, in the same sections -- including both contacts."""
    assert projected.form_ui_schema == golden.FORM_UI_SCHEMA


def test_rule_schema_is_identical(projected, golden):
    assert projected.form_rule_schema == getattr(golden, "FORM_RULE_SCHEMA", None)


def test_every_rendered_field_matches(resolved_projected, resolved_golden, golden):
    differences = parity.rendered_differences(
        resolved_projected, resolved_golden, golden.FORM_UI_SCHEMA
    )
    assert parity.unexplained(differences, RENDERED) == []


def test_allow_list_has_no_dead_entries(resolved_projected, resolved_golden, golden):
    differences = parity.rendered_differences(
        resolved_projected, resolved_golden, golden.FORM_UI_SCHEMA
    )
    assert parity.unused(differences, RENDERED) == []


def test_conditional_requiredness_matches(resolved_projected, resolved_golden):
    assert parity.conditional_branches(resolved_projected) == parity.conditional_branches(
        resolved_golden
    )


def test_a_contact_must_have_a_title_on_this_form(resolved_projected):
    """The question leaves the title optional; this form narrows it, in both boxes."""
    for box in ("project_director", "contact_person"):
        field = parity.rendered_field(resolved_projected, f"/properties/{box}/properties/title")
        assert field is not None
        assert field.required, f"{box}.title should be required on this form"


def test_no_reference_is_left_unresolved(resolved_projected):
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
