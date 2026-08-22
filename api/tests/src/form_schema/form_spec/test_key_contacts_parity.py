"""Key Contacts, authored declaratively, must behave exactly like the hand-written form.

The hand-written `form_json.py` is the oracle. Nothing about it is modified; the projected
artifacts have to meet it.
"""

import copy

import pytest

from src.form_schema.form_spec.loader import load_form
from src.form_schema.forms._loader import load_versioned_form
from src.form_schema.jsonschema_resolver import resolve_jsonschema
from tests.src.form_schema.form_spec import parity

FORM_DIR = "key_contacts"

#: Differences that are deliberate. Each key is a pointer suffix; each value says why the
#: projected artifact is allowed to differ. Anything not listed here fails the test.
ALLOWED = {
    # The bank names and documents its questions; several of SGG's shared primitives
    # carry no description at all, and the form-level title and description still win at
    # render time because they sit on the property rather than the definition.
    "/properties/phone/allOf/0/description": "bank question carries a description",
    "/properties/fax/allOf/0/description": "bank question carries a description",
    "/properties/email/allOf/0/description": "bank question carries a description",
    "/properties/organizational_affiliation/allOf/0/description": (
        "bank question carries a description"
    ),
    "/properties/applicant_organization_name/allOf/0/description": (
        "bank question carries a description"
    ),
    "/properties/name/allOf/0/description": (
        "the golden's shared person_name has an empty description; the bank states one"
    ),
    "/properties/name/allOf/0/title": (
        "the golden titles the shared definition 'Name and Contact Information', which "
        "describes neither; the bank calls a name a name"
    ),
    # Block-level metadata the bank adds. Additive, and not rendered: the section and
    # fieldList labels come from the UI schema, which matches the golden exactly.
    "/$defs/key_contact_person/title": "block label",
    "/$defs/key_contact_person/description": "block description",
    "/properties/key_contacts/items/title": "block label",
    "/properties/key_contacts/items/description": "block description",
    "/description": (
        "the form's own description; the golden carries the form name only in its "
        "registry row"
    ),
}


@pytest.fixture(scope="module")
def golden():
    from pathlib import Path

    import src.form_schema.forms as forms_package

    root = Path(forms_package.__file__).parent / FORM_DIR
    return load_versioned_form(root, "1.0")


@pytest.fixture(scope="module")
def projected():
    return load_form("key-contacts")


@pytest.fixture(scope="module")
def resolved_golden(golden):
    return resolve_jsonschema(copy.deepcopy(golden.FORM_JSON_SCHEMA))


@pytest.fixture(scope="module")
def resolved_projected(projected):
    return resolve_jsonschema(copy.deepcopy(projected.form_json_schema))


@pytest.fixture
def seeds():
    """The golden's own fixtures: one fully populated contact and one minimal one."""
    full = {
        "project_role": "Principal Investigator",
        "name": {
            "prefix": "Doctor",
            "first_name": "Sue",
            "middle_name": "Sally",
            "last_name": "Storm",
            "suffix": "Esquire",
        },
        "title": "Director",
        "organizational_affiliation": "Acme University",
        "address": {
            "street1": "123 Main Street",
            "street2": "Apt 123",
            "city": "Placeville",
            "county": "Placeville County",
            "state": "WY: Wyoming",
            "province": "Nowhere",
            "zip_code": "56789-1234",
            "country": "USA: UNITED STATES",
        },
        "phone": "1234567890",
        "fax": "1112223333",
        "email": "example@example.com",
    }
    minimal = {
        "project_role": "Project Manager",
        "name": {"first_name": "Joe", "last_name": "Smithers"},
        "address": {"street1": "456 Rio", "city": "Montevideo", "country": "URY: URUGUAY"},
        "phone": "1234567890",
        "email": "person@place.com",
    }
    return [
        {"applicant_organization_name": "Acme Corporation", "key_contacts": [full, minimal]},
        {"applicant_organization_name": "Acme Corporation", "key_contacts": [minimal]},
    ]


def test_ui_schema_is_identical(projected, golden):
    assert projected.form_ui_schema == golden.FORM_UI_SCHEMA


def test_rule_schema_is_identical(projected, golden):
    assert projected.form_rule_schema == getattr(golden, "FORM_RULE_SCHEMA", None)


def test_structural_differences_are_all_accounted_for(resolved_projected, resolved_golden):
    differences = parity.schema_differences(resolved_projected, resolved_golden)
    assert parity.unexplained(differences, ALLOWED) == []


def test_allow_list_has_no_dead_entries(resolved_projected, resolved_golden):
    """An explanation for a difference that no longer exists is an explanation to delete."""
    differences = parity.schema_differences(resolved_projected, resolved_golden)
    assert parity.unused(differences, ALLOWED) == []


def test_validation_verdicts_are_identical(resolved_projected, resolved_golden, seeds):
    payloads = parity.corpus(resolved_golden, seeds)
    assert len(payloads) > 100, "the corpus should exercise every field"
    assert parity.behavioural_differences(resolved_projected, resolved_golden, payloads) == []


def test_every_bank_question_resolves(resolved_projected):
    """A reference that failed to resolve would leave a `$ref` behind."""

    def refs(node):
        if isinstance(node, dict):
            return ("$ref" in node) or any(refs(v) for v in node.values())
        if isinstance(node, list):
            return any(refs(v) for v in node)
        return False

    assert not refs(resolved_projected)
