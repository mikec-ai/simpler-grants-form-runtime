import copy
import hashlib
import json
import shutil
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

from src.form_schema.registry.form_template_registry import FormTemplateKey, FormTemplateRegistry
from src.form_schema.portable_form_bundle import (
    CONTRACT,
    PortableFormBundleError,
    load_portable_form_bundle,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BUNDLE_ROOT = REPOSITORY_ROOT / "form-specs"


def _copy_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "form-specs"
    shutil.copytree(BUNDLE_ROOT, root)
    return root


def _rewrite_manifest_hash(root: Path, relative_path: str) -> None:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256((root / relative_path).read_bytes()).hexdigest()
    for descriptor in manifest["schemas"]:
        if descriptor["artifact"]["path"] == relative_path:
            descriptor["artifact"]["sha256"] = digest
    for form in manifest["forms"]:
        for key in ("ui", "mappings"):
            if form[key]["path"] == relative_path:
                form[key]["sha256"] = digest
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_referenced_question_compiles_into_two_native_forms() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT, REPOSITORY_ROOT)

    assert bundle.manifest["contract"] == CONTRACT
    assert set(bundle.forms_by_key) == {
        "KeyContactsOrganizationCanary",
        "SF424OrganizationCanary",
    }

    key_contacts = bundle.to_form("KeyContactsOrganizationCanary")
    sf424 = bundle.to_form("SF424OrganizationCanary")

    key_question = key_contacts.form_json_schema["properties"]["applicant_organization_name"]
    sf424_question = sf424.form_json_schema["properties"]["organization_name"]
    assert key_question["allOf"][0]["x-question-id"] == "question:organization:legal-name"
    assert sf424_question["allOf"][0]["x-question-id"] == "question:organization:legal-name"
    assert key_question["allOf"][0] == sf424_question["allOf"][0]
    assert key_question["title"] == "Applicant Organization Name"
    assert sf424_question["title"] == "Legal Name"

    assert key_contacts.form_ui_schema == [
        {
            "type": "section",
            "label": "Applicant organization",
            "name": "applicant_organization",
            "children": [
                {
                    "type": "field",
                    "definition": "/properties/applicant_organization_name",
                    "label": "Applicant Organization Name",
                }
            ],
        }
    ]
    assert sf424.form_ui_schema[0]["children"][0]["definition"] == ("/properties/organization_name")
    assert key_contacts.form_json_schema["x-mapping-from-cg"] == {
        "applicant_organization_name": {"field": "organizations.primary.name"}
    }
    assert sf424.form_json_schema["x-mapping-from-cg"] == {
        "organization_name": {"field": "organizations.primary.name"}
    }
    assert key_contacts.form_json_schema["x-portable-form-bundle"]["bundle_digest"] == (
        bundle.bundle_digest
    )


def test_analysis_projection_is_derived_from_the_same_bindings() -> None:
    projection = load_portable_form_bundle(BUNDLE_ROOT, REPOSITORY_ROOT).analysis_projection()

    assert projection["summary"] == {
        "forms": 2,
        "unique_questions": 1,
        "associations": 2,
        "accepted_mappings": 0,
    }
    assert projection["questions"] == [
        {"question_id": "question:organization:legal-name", "form_count": 2}
    ]
    assert projection["pairwise_form_overlap"] == [
        {
            "form_a": "KeyContactsOrganizationCanary",
            "form_b": "SF424OrganizationCanary",
            "questions_in_common": 1,
            "unique_questions": 1,
            "similarity": 1.0,
            "form_a_coverage": 1.0,
            "form_b_coverage": 1.0,
        }
    ]
    associations = projection["form_question_associations"]
    assert [row["xml_path"] for row in associations] == [
        "/Key_Contacts_2_0/ApplicantOrganizationName",
        "/SF424_4_0/OrganizationName",
    ]
    assert all(row["mapping_status"] == "agent_proposed" for row in associations)


def test_standard_json_schema_consumer_uses_portable_refs_without_simpler_adapter() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT, REPOSITORY_ROOT)
    registry = Registry().with_resources(
        (schema_id, Resource.from_contents(schema))
        for schema_id, schema in bundle.schemas_by_id.items()
    )
    form_schema = bundle.forms_by_key["SF424OrganizationCanary"].schema
    validator = jsonschema.Draft202012Validator(form_schema, registry=registry)

    assert not list(validator.iter_errors({"organization_name": "Example Organization"}))
    errors = list(validator.iter_errors({"organization_name": ""}))
    assert [error.validator for error in errors] == ["minLength"]


def test_native_registry_accepts_generic_adapter_result() -> None:
    form = load_portable_form_bundle(BUNDLE_ROOT, REPOSITORY_ROOT).to_form(
        "KeyContactsOrganizationCanary"
    )
    registry = FormTemplateRegistry()

    registry.register(form, major_version=1)

    registered = registry.get_by_id_and_major_version(FormTemplateKey(form.form_id, 1))
    question = registered.form_json_schema["properties"]["applicant_organization_name"]
    assert question["allOf"][0]["x-question-id"] == "question:organization:legal-name"


def test_native_forms_are_independent_snapshots() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT, REPOSITORY_ROOT)
    first = bundle.to_form("KeyContactsOrganizationCanary")
    second = bundle.to_form("KeyContactsOrganizationCanary")

    first.form_json_schema["x-mapping-from-cg"]["applicant_organization_name"]["field"] = (
        "changed.path"
    )
    first.form_json_schema["x-portable-form-bundle"]["question_bindings"][0]["role"] = "changed"

    assert second.form_json_schema["x-mapping-from-cg"] == {
        "applicant_organization_name": {"field": "organizations.primary.name"}
    }
    assert second.form_json_schema["x-portable-form-bundle"]["question_bindings"][0]["role"] == (
        "applicant_organization"
    )


def test_portable_specs_do_not_depend_on_simpler_python() -> None:
    assert not list(BUNDLE_ROOT.rglob("*.py"))
    adapter_source = (REPOSITORY_ROOT / "api/src/form_schema/portable_form_bundle.py").read_text(
        encoding="utf-8"
    )
    assert "KeyContactsOrganizationCanary" not in adapter_source
    assert "SF424OrganizationCanary" not in adapter_source


def test_rejects_tampered_schema(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    schema_path = root / "schemas/questions/organization-legal-name.schema.json"
    schema_path.write_text(schema_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(PortableFormBundleError, match="sha256 does not match"):
        load_portable_form_bundle(root, REPOSITORY_ROOT)


def test_rejects_dangling_question_reference(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    relative_path = "schemas/forms/sf424-organization-canary.schema.json"
    schema_path = root / relative_path
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["properties"]["organization_name"]["allOf"][0]["$ref"] = (
        "https://schemas.simpler.grants.gov/questions/missing/v1"
    )
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    _rewrite_manifest_hash(root, relative_path)

    with pytest.raises(PortableFormBundleError, match="unbundled schema reference"):
        load_portable_form_bundle(root, REPOSITORY_ROOT)


def test_rejects_unknown_manifest_fields(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["forms"][0]["custom_python_builder"] = "not allowed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PortableFormBundleError, match="invalid keys"):
        load_portable_form_bundle(root, REPOSITORY_ROOT)


def test_rejects_source_evidence_drift(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed = copy.deepcopy(manifest)
    changed["forms"][0]["source_evidence"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(PortableFormBundleError, match="sha256 does not match source"):
        load_portable_form_bundle(root, REPOSITORY_ROOT)
