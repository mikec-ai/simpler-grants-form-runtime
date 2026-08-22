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

#: Fields the golden spells out inline and the bank now owns as questions. Every one is a
#: question a later form will ask again, which is the whole point; the consequence here is
#: that the field's constraints live in the reference rather than on the property.
COMPOSED = {
    "submission_type": "SF-424's own enum, referenced rather than inlined",
    "application_type": "SF-424's own enum, referenced rather than inlined",
    "revision_type": "SF-424's own enum, referenced rather than inlined",
    "applicant_type_code": "SF-424's own enum, referenced rather than inlined",
    "state_review": "SF-424's own enum, referenced rather than inlined",
    "employer_taxpayer_identification_number": "new question primary-org/ein",
    "agency_name": "new question opportunity/agency-name",
    "assistance_listing_number": "new question opportunity/assistance-listing-number",
    "assistance_listing_program_title": "new question opportunity/assistance-listing-title",
    "funding_opportunity_number": "new question opportunity/number",
    "funding_opportunity_title": "new question opportunity/title",
    "competition_identification_number": "new question opportunity/competition-number",
    "competition_identification_title": "new question opportunity/competition-title",
    "project_title": "new question project/title",
    "congressional_district_applicant": "new question project/congressional-district",
    "congressional_district_program_project": "new question project/congressional-district",
    "authorized_representative_title": "the contact-title question, reused here",
    "authorized_representative_email": "the email question, reused here",
    "date_received": (
        "the submitted-date question. The golden shares a definition for date_signed and "
        "inlines the identical field here; the bank has one question for both"
    ),
    "project_start_date": "a plain date, referenced through the form's own declaration",
    "project_end_date": "a plain date, referenced through the form's own declaration",
    "state_receive_date": "a plain date, referenced through the form's own declaration",
    "state_application_id": "form-local string, referenced through its own declaration",
    "areas_affected": "the attachment question, reused here",
    "additional_project_title": "the attachment question, reused here",
    "additional_congressional_districts": "the attachment question, reused here",
    "debt_explanation": "the attachment question, reused here",
    "federal_estimated_funding": "new question generics/monetary-amount",
    "applicant_estimated_funding": "new question generics/monetary-amount",
    "state_estimated_funding": "new question generics/monetary-amount",
    "local_estimated_funding": "new question generics/monetary-amount",
    "other_estimated_funding": "new question generics/monetary-amount",
    "program_income_estimated_funding": "new question generics/monetary-amount",
    "total_estimated_funding": "new question generics/monetary-amount",
}

#: Differences decided one at a time, as opposed to the systematic class above.
HAND_WRITTEN = {
    # Bank questions name and document themselves where several of SGG's shared primitives
    # do not. The form-level title and description sit on the property and still win.
    "*/properties/organization_name/allOf/0/description": "bank question carries a description",
    "*/properties/contact_person/allOf/0/title": (
        "the golden titles the shared definition 'Name and Contact Information', which "
        "describes neither; the bank calls a name a name"
    ),
    "*/properties/contact_person/allOf/0/description": (
        "the golden's shared person_name has an empty description; the bank states one"
    ),
    "*/properties/authorized_representative/allOf/0/title": "as contact_person, same question",
    "*/properties/authorized_representative/allOf/0/description": (
        "as contact_person, same question"
    ),
    "*/properties/phone_number/allOf/0/description": "bank question carries a description",
    "*/properties/fax/allOf/0/description": "bank question carries a description",
    "*/properties/authorized_representative_phone_number/allOf/0/description": (
        "bank question carries a description"
    ),
    "*/properties/authorized_representative_fax/allOf/0/description": (
        "bank question carries a description"
    ),
    "/properties/authorized_representative/description": (
        "the golden gives box 21's name an empty description; an absent description and "
        "an empty one render the same"
    ),
    "*/properties/email/allOf/0/description": "bank question carries a description",
    "*/properties/sam_uei/allOf/0/description": "bank question carries a description",
    "/description": "the form's own description",
    "/$defs": (
        "the form's five enums are declarations held in $defs and referenced; the golden "
        "repeats each list inline. Nothing reads a $defs entry once the references are "
        "resolved, and the golden keeps its own $defs on other forms"
    ),
    # The golden marks two of its six read-only fields `readOnly` in the schema as well as
    # `null` in the UI schema. Nothing reads the keyword -- the renderer takes read-only
    # from the UI schema's `null` node, and the API never looks -- so it is vestigial, and
    # emitting it on two of six would be reproducing an inconsistency.
    "*/properties/state_application_id/readOnly": "vestigial; the UI schema carries read-only",
    "*/properties/state_receive_date/readOnly": "vestigial; the UI schema carries read-only",
}

ALLOWED = {**parity.composed(COMPOSED), **HAND_WRITTEN}

#: The one place where this form and the golden reach different verdicts on the same data.
#:
#: Boxes 8f and 21 both ask for an email address. The golden caps 8f at 60 characters, via
#: `common_shared_v1#/contact_email`, and leaves 21 uncapped, because 21 is written out
#: inline. One question cannot be two lengths, so composing it applies the cap to both --
#: which rejects an AOR email longer than 60 characters that the form accepts today.
#:
#: Recorded rather than worked around: it is a real behaviour change, it is small, and
#: which of the two boxes is right is a decision for the form's owners.
ALLOWED_BEHAVIOUR = {
    ("authorized_representative_email", "maxLength"): (
        "the golden caps the contact email at 60 and the AOR email not at all; one "
        "question means one cap"
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
    assert projected.form_ui_schema == golden.FORM_UI_SCHEMA


def test_rule_schema_is_identical(projected, golden):
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
    assert len(payloads) > 500, "the corpus should exercise every field"
    assert (
        parity.behavioural_differences(
            resolved_projected, resolved_golden, payloads, ALLOWED_BEHAVIOUR
        )
        == []
    )


def test_conditional_requiredness_matches(resolved_projected, resolved_golden):
    """The six root conditionals are the form's real logic; compare them as a set.

    `allOf` is a conjunction, so the order the branches happen to be written in carries no
    meaning -- ours follows declaration order and the golden's is hand-arranged.
    """
    import json

    def branches(schema):
        return sorted(json.dumps(b, sort_keys=True) for b in schema.get("allOf", []))

    assert branches(resolved_projected) == branches(resolved_golden)
