import json
from pathlib import Path

from lxml import etree as lxml_etree

from src.form_schema.forms.key_contacts import FORM_XML_TRANSFORM_RULES
from src.form_schema.jsonschema_validator import validate_json_schema_for_form
from src.form_schema.portable_form_bundle import load_portable_form_bundle
from src.services.xml_generation.models import XMLGenerationRequest
from src.services.xml_generation.service import XMLGenerationService
from src.services.xml_generation.validation.xsd_validator import XSDValidator

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BUNDLE_ROOT = REPOSITORY_ROOT / "form-specs"
KC_NS = "http://apply.grants.gov/forms/Key_Contacts_2_0-V2.0"
GLOB_NS = "http://apply.grants.gov/system/GlobalLibrary-V2.0"


def _minimal_contact() -> dict:
    return {
        "project_role": "Project Manager",
        "name": {"first_name": "Joe", "last_name": "Smith"},
        "address": {
            "street1": "456 Oak Ave",
            "city": "Springfield",
            "state": "IL: Illinois",
            "zip_code": "62701",
            "country": "USA: UNITED STATES",
        },
        "phone": "5555550100",
        "email": "joe.smith@example.com",
    }


def test_full_key_contacts_declaration_preserves_occurrences_and_review_boundary() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)
    declaration = bundle.forms_by_key["KeyContacts"].definition

    assert declaration["metadata"] == {
        "form_id": "f140c7db-724d-4954-bebd-081c0527908c",
        "legacy_form_id": 683,
        "form_name": "KEY CONTACTS",
        "short_form_name": "Key_Contacts",
        "form_version": "2.0",
        "agency_code": "SGG",
        "omb_number": "4040-0010",
        "form_type": "KeyContacts",
        "sgg_version": "1.0",
        "is_deprecated": False,
    }
    assert len(declaration["question_bindings"]) == 20
    assert len({binding["binding_id"] for binding in declaration["question_bindings"]}) == 20
    assert {binding["role"] for binding in declaration["question_bindings"]} == {
        "applicant_organization",
        "key_contact",
    }
    assert declaration["review_boundary"] == {
        "semantic_mappings": "agent_proposed",
        "published_coverage_eligible": False,
        "production_ready": False,
    }
    assert all(
        binding["mapping_status"] == "agent_proposed"
        for binding in declaration["question_bindings"]
    )


def test_full_key_contacts_schema_preserves_cardinality_and_requiredness() -> None:
    form = load_portable_form_bundle(BUNDLE_ROOT).to_form("KeyContacts")
    schema = form.form_json_schema
    contacts = schema["properties"]["key_contacts"]

    assert contacts["minItems"] == 1
    assert contacts["maxItems"] == 4
    assert contacts["items"]["required"] == [
        "project_role",
        "name",
        "address",
        "phone",
        "email",
    ]
    assert contacts["items"]["properties"]["name"]["required"] == [
        "first_name",
        "last_name",
    ]
    assert contacts["items"]["properties"]["address"]["required"] == [
        "street1",
        "city",
        "country",
    ]

    valid = {
        "applicant_organization_name": "Example Organization",
        "key_contacts": [_minimal_contact()],
    }
    assert validate_json_schema_for_form(valid, form) == []

    too_many = {**valid, "key_contacts": [_minimal_contact()] * 5}
    issues = validate_json_schema_for_form(too_many, form)
    assert [(issue.field, issue.type) for issue in issues] == [("$.key_contacts", "maxItems")]


def test_full_key_contacts_compiles_generic_repeated_ui() -> None:
    form = load_portable_form_bundle(BUNDLE_ROOT).to_form("KeyContacts")
    section = form.form_ui_schema[0]
    field_list = section["children"][1]

    assert section["label"] == "Key Contacts"
    assert field_list["type"] == "fieldList"
    assert field_list["name"] == "key_contacts"
    assert field_list["label"] == "Key Contact"
    assert len(field_list["children"]) == 19
    assert field_list["children"][0]["definition"] == (
        "/properties/key_contacts/items/properties/project_role"
    )
    assert field_list["children"][-1]["definition"] == (
        "/properties/key_contacts/items/properties/email"
    )


def test_full_key_contacts_xml_transform_matches_native_oracle_and_xsd() -> None:
    form = load_portable_form_bundle(BUNDLE_ROOT).to_form("KeyContacts")
    assert form.json_to_xml_schema == FORM_XML_TRANSFORM_RULES

    data = {
        "applicant_organization_name": "Example Organization",
        "key_contacts": [_minimal_contact()],
    }
    response = XMLGenerationService().generate_xml(
        XMLGenerationRequest(
            application_data=data,
            transform_config=form.json_to_xml_schema,
        )
    )
    assert response.success, response.error_message
    root = lxml_etree.fromstring(response.xml_data.encode("utf-8"))
    assert root.tag == f"{{{KC_NS}}}Key_Contacts_2_0"
    assert root.get(f"{{{KC_NS}}}FormVersion") == "2.0"
    role = root.find(f"{{{KC_NS}}}RoleOnProject")
    assert [child.tag for child in role] == [
        f"{{{KC_NS}}}ContactProjectRole",
        f"{{{KC_NS}}}ContactName",
        f"{{{KC_NS}}}ContactAddress",
        f"{{{KC_NS}}}ContactPhone",
        f"{{{KC_NS}}}ContactEmail",
    ]
    address = role.find(f"{{{KC_NS}}}ContactAddress")
    assert [child.tag for child in address] == [
        f"{{{GLOB_NS}}}Street1",
        f"{{{GLOB_NS}}}City",
        f"{{{GLOB_NS}}}State",
        f"{{{GLOB_NS}}}ZipPostalCode",
        f"{{{GLOB_NS}}}Country",
    ]

    validator = XSDValidator(REPOSITORY_ROOT / "api/src/services/xml_generation/xsds")
    result = validator.validate_xml(
        response.xml_data,
        REPOSITORY_ROOT / "api/src/services/xml_generation/xsds/Key_Contacts_2_0-V2.0.xsd",
    )
    assert result["valid"], result["error_message"]


def test_source_behavior_gaps_are_explicit_and_not_coverage_eligible() -> None:
    evidence = json.loads(
        (BUNDLE_ROOT / "evidence/key-contacts.behavior-evidence.json").read_text(encoding="utf-8")
    )

    assert evidence["review_status"] == "agent_proposed"
    assert evidence["published_coverage_eligible"] is False
    assert evidence["authoritative_source"]["sha256"] == (
        "b4856e146a424bea07ba508c5f261c5756798ed139bef4ea4c66d286fb439543"
    )
    assert {gap["disposition"] for gap in evidence["gaps"]} == {
        "source_behavior_not_yet_projected",
        "source_constraint_not_yet_projected",
        "cross_form_policy_not_yet_projected",
        "presentation_behavior_delegated_to_runtime",
    }


def test_analysis_projects_all_key_contacts_occurrences_without_published_coverage() -> None:
    projection = load_portable_form_bundle(BUNDLE_ROOT).analysis_projection()
    rows = [
        row for row in projection["form_question_associations"] if row["form_key"] == "KeyContacts"
    ]

    assert len(rows) == 20
    assert len({row["binding_id"] for row in rows}) == 20
    assert all(row["mapping_status"] == "agent_proposed" for row in rows)
    assert {row["xml_path"] for row in rows} >= {
        "/Key_Contacts_2_0/ApplicantOrganizationName",
        "/Key_Contacts_2_0/RoleOnProject[]/ContactProjectRole",
        "/Key_Contacts_2_0/RoleOnProject[]/ContactEmail",
    }
