"""SF-424, the widest form: 58 flat fields, 24 numbered sections, six root conditionals.

Where Key Contacts tests composition and repetition, this tests breadth: section
placement across two dozen boxes, a calculation, eight pre-population rules, four
attachments, and a form-scoped override that drops one field of a shared question.
"""

import copy
from pathlib import Path

import pytest

import src.form_schema.forms as forms_package
from src.form_schema.form_spec.loader import load_form
from src.form_schema.forms._loader import load_versioned_form
from src.form_schema.jsonschema_resolver import resolve_jsonschema
from tests.src.form_schema.form_spec import parity

FORM_DIR = "sf424"
FORM_ID = "sf424"

#: Differences between what this form renders and what the golden renders. Each key is
#: `<pointer>#<keyword>`, each value says why the difference is deliberate, and anything not
#: listed fails the test.
RENDERED = {
    # The golden marks two of its six read-only fields `readOnly` in the schema as well as
    # `null` in the UI schema. Nothing reads the keyword -- not the renderer, which takes
    # read-only from the UI schema, and not the API -- so emitting it on two of six would be
    # reproducing an inconsistency.
    "/properties/state_receive_date#readOnly": "vestigial; the UI schema carries read-only",
    "/properties/state_application_id#readOnly": "vestigial; the UI schema carries read-only",
    # The golden's text ends in a space. Reproducing a stray space would mean carrying it in
    # a doc comment, where it is invisible to the next person to edit the line.
    "/properties/project_start_date#description": "the golden's text has a trailing space",
    "/properties/project_end_date#description": "the golden's text has a trailing space",
    # The golden sets this field's description to the empty string, which renders as nothing.
    # The attachment question says what to do instead.
    "/properties/debt_explanation#description": "the golden's description is empty",
    # Boxes 8f and 21 both ask for an email address. The golden caps 8f at 60 characters via
    # `common_shared_v1#/contact_email` and leaves 21 uncapped, because 21 is written out
    # inline. One question cannot be two lengths.
    "/properties/authorized_representative_email#maxLength": (
        "the golden caps the contact email at 60 and the AOR email not at all"
    ),
}

#: The one place where this form and the golden reach different verdicts on the same data,
#: and it follows from the `maxLength` difference above: an AOR email longer than 60
#: characters is accepted today and rejected here. Recorded rather than worked around,
#: because which of the two boxes is right is a decision for the form's owners.
ALLOWED_BEHAVIOR = {
    ("authorized_representative_email", "maxLength"): (
        "the golden caps the contact email at 60 and the AOR email not at all; one question "
        "means one cap"
    ),
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
    """One complete application and one with only the required fields answered."""
    full = {
        "submission_type": "Application",
        "application_type": "Revision",
        "revision_type": "E: Other (specify)",
        "revision_other_specify": "Scope change",
        "date_received": "2026-01-05",
        "applicant_id": "APP-1",
        "federal_entity_identifier": "FED-1",
        "federal_award_identifier": "AWARD-1",
        "state_receive_date": "2026-01-06",
        "state_application_id": "ST-1",
        "organization_name": "Acme University",
        "employer_taxpayer_identification_number": "123456789",
        "sam_uei": "ABCDEFGHIJKL",
        "applicant": {
            "street1": "123 Main Street",
            "street2": "Suite 4",
            "city": "Placeville",
            "county": "Place County",
            "state": "WY: Wyoming",
            "province": "Nowhere",
            "country": "USA: UNITED STATES",
            "zip_code": "56789-1234",
        },
        "department_name": "Research",
        "division_name": "Grants",
        "contact_person": {
            "prefix": "Doctor",
            "first_name": "Sue",
            "middle_name": "Sally",
            "last_name": "Storm",
            "suffix": "Esquire",
        },
        "contact_person_title": "Director",
        "organization_affiliation": "Acme University",
        "phone_number": "1234567890",
        "fax": "1112223333",
        "email": "example@example.com",
        "applicant_type_code": ["A: State Government", "X: Other (specify)"],
        "applicant_type_other_specify": "Consortium",
        "agency_name": "Department of Everything",
        "assistance_listing_number": "12.345",
        "assistance_listing_program_title": "Everything Program",
        "funding_opportunity_number": "EVERY-2026-001",
        "funding_opportunity_title": "Everything Opportunity",
        "competition_identification_number": "COMP-1",
        "competition_identification_title": "Competition One",
        "areas_affected": "2a4e1e7a-1e4d-4a5e-9f2c-6b7c8d9e0f11",
        "project_title": "A Study of Everything",
        "additional_project_title": ["3b5f2f8b-2f5e-4b6f-8a3d-7c8d9e0f1a22"],
        "congressional_district_applicant": "CA-005",
        "congressional_district_program_project": "MD-all",
        "additional_congressional_districts": "4c6a3a9c-3a6f-4c7a-9b4e-8d9e0f1a2b33",
        "project_start_date": "2026-06-01",
        "project_end_date": "2027-05-31",
        "federal_estimated_funding": "100000.00",
        "applicant_estimated_funding": "20000.00",
        "state_estimated_funding": "0.00",
        "local_estimated_funding": "0.00",
        "other_estimated_funding": "0.00",
        "program_income_estimated_funding": "0.00",
        "total_estimated_funding": "120000.00",
        "state_review": (
            "a. This application was made available to the state under the Executive "
            "Order 12372 Process for review on"
        ),
        "state_review_available_date": "2026-02-01",
        "delinquent_federal_debt": True,
        "debt_explanation": "5d7b4b0d-4b70-4d8b-8c5f-9e0f1a2b3c44",
        "certification_agree": True,
        "authorized_representative": {"first_name": "Reed", "last_name": "Richards"},
        "authorized_representative_title": "Provost",
        "authorized_representative_phone_number": "5556667777",
        "authorized_representative_fax": "5556667778",
        "authorized_representative_email": "provost@example.com",
        "aor_signature": "Reed Richards",
        "date_signed": "2026-02-02",
    }
    minimal = {
        "submission_type": "Preapplication",
        "application_type": "New",
        "organization_name": "Acme University",
        "employer_taxpayer_identification_number": "123456789",
        "sam_uei": "ABCDEFGHIJKL",
        "applicant": {
            "street1": "456 Rio",
            "city": "Montevideo",
            "country": "URY: URUGUAY",
        },
        "contact_person": {"first_name": "Joe", "last_name": "Smithers"},
        "phone_number": "1234567890",
        "email": "person@place.com",
        "applicant_type_code": ["P: Individual"],
        "agency_name": "Department of Everything",
        "funding_opportunity_number": "EVERY-2026-001",
        "funding_opportunity_title": "Everything Opportunity",
        "project_title": "A Study of Everything",
        "congressional_district_applicant": "00-000",
        "congressional_district_program_project": "00-000",
        "project_start_date": "2026-06-01",
        "project_end_date": "2027-05-31",
        "federal_estimated_funding": "1.00",
        "applicant_estimated_funding": "0.00",
        "state_estimated_funding": "0.00",
        "local_estimated_funding": "0.00",
        "other_estimated_funding": "0.00",
        "program_income_estimated_funding": "0.00",
        "total_estimated_funding": "1.00",
        "state_review": "c. Program is not covered by E.O. 12372.",
        "delinquent_federal_debt": False,
        "certification_agree": True,
        "authorized_representative": {"first_name": "Reed", "last_name": "Richards"},
        "authorized_representative_title": "Provost",
        "authorized_representative_phone_number": "5556667777",
        "authorized_representative_email": "provost@example.com",
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
