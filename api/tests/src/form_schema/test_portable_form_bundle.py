import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

from src.form_schema.portable_form_bundle import (
    CONTRACT,
    PortableFormBundleError,
    load_portable_form_bundle,
)
from src.form_schema.registry.form_template_registry import FormTemplateKey, FormTemplateRegistry

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
    bundle = load_portable_form_bundle(BUNDLE_ROOT)

    assert bundle.manifest["contract"] == CONTRACT
    assert {"KeyContacts", "SF424"} <= set(bundle.forms_by_key)

    key_contacts = bundle.to_form("KeyContacts")
    sf424 = bundle.to_form("SF424")

    key_question = key_contacts.form_json_schema["properties"]["applicant_organization_name"]
    sf424_question = sf424.form_json_schema["properties"]["organization_name"]
    assert key_question["allOf"][0]["x-question-id"] == "question:organization:legal-name"
    assert sf424_question["allOf"][0]["x-question-id"] == "question:organization:legal-name"
    assert key_question["allOf"][0] == sf424_question["allOf"][0]
    assert key_question["title"] == "Applicant Organization Name"
    assert sf424_question["title"] == "Legal Name"

    assert key_contacts.form_ui_schema[0]["children"][0] == {
        "type": "field",
        "definition": "/properties/applicant_organization_name",
    }
    assert "/properties/organization_name" in json.dumps(sf424.form_ui_schema)
    assert key_contacts.form_json_schema["x-mapping-from-cg"] == {}
    assert sf424.form_json_schema["x-mapping-from-cg"] == {}
    assert key_contacts.form_json_schema["x-portable-form-bundle"]["bundle_digest"] == (
        bundle.bundle_digest
    )


def test_analysis_projection_is_derived_from_the_same_bindings() -> None:
    projection = load_portable_form_bundle(BUNDLE_ROOT).analysis_projection()

    assert projection["contract"] == "portable-grants-form-analysis/v2"
    assert projection["summary"] == {
        "forms": 4,
        "proposed_unique_questions": 167,
        "accepted_unique_questions": 0,
        "published_unique_questions": 0,
        "proposed_associations": 295,
        "accepted_associations": 0,
        "published_associations": 0,
    }
    legal_name = next(
        row
        for row in projection["questions"]
        if row["question_id"] == "question:organization:legal-name"
    )
    assert legal_name == {
        "question_id": "question:organization:legal-name",
        "proposed_form_count": 2,
        "accepted_form_count": 0,
        "published_form_count": 0,
    }
    associations = projection["form_question_associations"]
    assert {row["xml_path"] for row in associations} >= {
        "/Key_Contacts_2_0/ApplicantOrganizationName",
        "/SF424_4_0/OrganizationName",
    }
    assert all(row["mapping_status"] == "agent_proposed" for row in associations)
    assert all(row["included_in_proposed_overlap"] for row in associations)
    assert not any(row["included_in_accepted_overlap"] for row in associations)
    assert not any(row["included_in_published_overlap"] for row in associations)

    pair = next(
        row
        for row in projection["pairwise_form_overlap"]
        if (row["form_a"], row["form_b"]) == ("KeyContacts", "SF424")
    )
    assert (pair["form_a"], pair["form_b"]) == ("KeyContacts", "SF424")
    assert pair["proposed_overlap"]["questions_in_common"] == 19
    assert pair["proposed_overlap"]["form_a_coverage"] == pytest.approx(0.95)
    assert pair["accepted_overlap"]["questions_in_common"] == 0
    assert pair["published_overlap"] == {
        "eligible": False,
        "questions_in_common": 0,
        "unique_questions": 0,
        "similarity": 0.0,
        "form_a_coverage": 0.0,
        "form_b_coverage": 0.0,
    }


def test_existing_simpler_shared_schema_is_explicitly_reconciled() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)

    assert bundle.compatibility_records == (
        {
            "portable_schema_id": "urn:grants-form-kernel:questions:organization:legal-name:v1",
            "existing_schema_ref": (
                "https://files.simpler.grants.gov/schemas/common_shared_v1.json#/organization_name"
            ),
            "relation": "candidate_alias",
            "mapping_status": "agent_proposed",
            "comparison": {
                "type": "exact",
                "minLength": "exact",
                "maxLength": "exact",
                "portable_description_is_additional": True,
                "portable_question_identity_is_additional": True,
            },
            "evidence": {
                "kind": "implementation_oracle",
                "repository": "https://github.com/mikec-ai/simpler-grants-form-runtime.git",
                "revision": "e1739ee54e2d1c964d48b0386a3c0246d3c621d7",
                "path": "api/src/form_schema/shared/common_shared.py",
                "sha256": "a4944116280586d541d3f0afb77c67acb123e2004911646d7b98fadd7e701935",
                "source_version": "COMMON_SHARED_V1",
            },
        },
    )


def test_standard_json_schema_consumer_uses_portable_refs_without_simpler_adapter() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)
    registry = Registry().with_resources(
        (schema_id, Resource.from_contents(schema))
        for schema_id, schema in bundle.schemas_by_id.items()
    )
    question_schema = bundle.schemas_by_id[
        "urn:grants-form-kernel:questions:organization:legal-name:v1"
    ]
    validator = jsonschema.Draft202012Validator(question_schema, registry=registry)

    assert not list(validator.iter_errors("Example Organization"))
    errors = list(validator.iter_errors(""))
    assert [error.validator for error in errors] == ["minLength"]


def test_native_registry_accepts_generic_adapter_result() -> None:
    form = load_portable_form_bundle(BUNDLE_ROOT).to_form("KeyContacts")
    registry = FormTemplateRegistry()

    registry.register(form, major_version=1)

    registered = registry.get_by_id_and_major_version(FormTemplateKey(form.form_id, 1))
    question = registered.form_json_schema["properties"]["applicant_organization_name"]
    assert question["allOf"][0]["x-question-id"] == "question:organization:legal-name"


def test_adapter_compiles_through_the_resolved_package_seam() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)

    package = bundle.to_resolved_package("SF424")
    form = package.to_form()

    assert package.manifest["contract"] == "portable-grants-resolved-form-package/v1"
    assert package.manifest["source_set"]["bundle_digest"] == bundle.bundle_digest
    assert form.form_json_schema["x-simpler-form-package"]["package_digest"] == (
        package.package_digest
    )
    assert form.form_json_schema["x-portable-form-bundle"]["form_key"] == ("SF424")


def test_native_forms_are_independent_snapshots() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)
    first = bundle.to_form("KeyContacts")
    second = bundle.to_form("KeyContacts")

    first.form_json_schema["properties"]["applicant_organization_name"]["title"] = "Changed"
    first.form_json_schema["x-portable-form-bundle"]["question_bindings"][0]["role"] = "changed"

    assert second.form_json_schema["properties"]["applicant_organization_name"]["title"] == (
        "Applicant Organization Name"
    )
    assert second.form_json_schema["x-portable-form-bundle"]["question_bindings"][0]["role"] == (
        "applicant_organization"
    )


def test_portable_specs_do_not_depend_on_simpler_python() -> None:
    assert not list(BUNDLE_ROOT.rglob("*.py"))
    kernel_source = (REPOSITORY_ROOT / "api/src/form_schema/portable_form_kernel.py").read_text(
        encoding="utf-8"
    )
    assert "from src." not in kernel_source
    assert "import src." not in kernel_source
    adapter_source = (REPOSITORY_ROOT / "api/src/form_schema/portable_form_bundle.py").read_text(
        encoding="utf-8"
    )
    assert "KeyContactsOrganizationCanary" not in adapter_source
    assert "SF424OrganizationCanary" not in adapter_source


def test_copied_bundle_and_neutral_kernel_work_without_simpler_checkout(tmp_path: Path) -> None:
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    shutil.copytree(BUNDLE_ROOT, isolated / "form-specs")
    shutil.copy(
        REPOSITORY_ROOT / "api/src/form_schema/portable_form_kernel.py",
        isolated / "portable_form_kernel.py",
    )
    script = """
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from portable_form_kernel import load_portable_form_kernel
kernel = load_portable_form_kernel(Path('form-specs'))

def resolve_pointer(document, pointer):
    value = document
    for token in pointer.removeprefix('#/').split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value

def consume_ui(node, schema):
    node_type = node['type']
    if node_type == 'Control':
        target = resolve_pointer(schema, node['scope'])
        assert isinstance(target, dict)
        detail = node.get('options', {}).get('detail')
        if detail is None:
            return 1
        assert target.get('type') == 'array'
        return 1 + consume_ui(detail, target['items'])
    assert node_type in {'Group', 'VerticalLayout'}
    return sum(consume_ui(child, schema) for child in node['elements'])

consumed = {}
for form_key, form in kernel.forms_by_key.items():
    resolved = kernel.resolved_schema(form_key)
    assert resolved['type'] == 'object'
    assert resolved['properties']
    consumed[form_key] = {
        'resolved_properties': len(resolved['properties']),
        'ui_controls': consume_ui(form.ui, form.schema),
    }

print(json.dumps({
    'summary': kernel.analysis_projection()['summary'],
    'consumed': consumed,
}, sort_keys=True))
"""

    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=isolated,
        check=True,
        capture_output=True,
        text=True,
    )

    output = json.loads(result.stdout)
    summary = output["summary"]
    assert summary["accepted_associations"] == 0
    assert summary["published_associations"] == 0
    assert summary["forms"] == 4
    assert summary["proposed_unique_questions"] == 167
    assert output["consumed"] == {
        "KeyContacts": {"resolved_properties": 2, "ui_controls": 21},
        "RRBudget": {"resolved_properties": 6, "ui_controls": 162},
        "RRBudget10": {"resolved_properties": 6, "ui_controls": 162},
        "SF424": {"resolved_properties": 58, "ui_controls": 72},
    }


def test_same_question_can_have_distinct_occurrence_bindings(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    form = next(item for item in manifest["forms"] if item["form_key"] == "SF424")
    schema_relative = "schemas/forms/sf424-v4.schema.json"
    schema_path = root / schema_relative
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["properties"]["alternate_organization_name"] = {
        "allOf": [{"$ref": "urn:grants-form-kernel:questions:organization:legal-name:v1"}],
        "title": "Alternate organization legal name",
    }
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    schema_descriptor = next(
        descriptor
        for descriptor in manifest["schemas"]
        if descriptor["artifact"]["path"] == schema_relative
    )
    schema_descriptor["artifact"]["sha256"] = hashlib.sha256(schema_path.read_bytes()).hexdigest()

    mapping_relative = "mappings/sf424-v4.mappings.json"
    mapping_path = root / mapping_relative
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    binding_id = "binding:sf424:alternate-organization-name"
    mapping["targets"]["grants_gov_xml"]["bindings"][binding_id] = {
        "path": "/SF424_4_0/AlternateOrganizationName",
        "type_source": "GlobalLibrary-V2.0.xsd#OrganizationNameDataType",
        "type": "string",
        "xsd_source": "https://example.invalid/SF424_4_0-V4.0.xsd",
    }
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    form["mappings"]["sha256"] = hashlib.sha256(mapping_path.read_bytes()).hexdigest()
    form["question_bindings"].append(
        {
            "binding_id": binding_id,
            "question_id": "question:organization:legal-name",
            "schema_id": "urn:grants-form-kernel:questions:organization:legal-name:v1",
            "form_pointer": "/properties/alternate_organization_name",
            "role": "alternate_applicant_organization",
            "cardinality": {"min": 0, "max": 1},
            "context": {"scope": "form", "repetition": "single"},
            "mapping_refs": {"grants_gov_xml": binding_id},
            "mapping_status": "agent_proposed",
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    projection = load_portable_form_bundle(root).analysis_projection()

    sf424_rows = [
        row
        for row in projection["form_question_associations"]
        if row["form_key"] == "SF424" and row["question_id"] == "question:organization:legal-name"
    ]
    assert len(sf424_rows) == 2
    assert {row["binding_id"] for row in sf424_rows} == {
        "binding:sf424:organization_name",
        binding_id,
    }
    assert {row["role"] for row in sf424_rows} == {
        "applicant_organization",
        "alternate_applicant_organization",
    }


def test_rejects_unbound_question_occurrence(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    relative_path = "schemas/forms/sf424-v4.schema.json"
    schema_path = root / relative_path
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["properties"]["unbound_name"] = {
        "$ref": "urn:grants-form-kernel:questions:organization:legal-name:v1"
    }
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    _rewrite_manifest_hash(root, relative_path)

    with pytest.raises(PortableFormBundleError, match=r"unbound question \$ref occurrences"):
        load_portable_form_bundle(root)


def test_common_grants_mapping_profile_is_optional(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    form = load_portable_form_bundle(root).to_form("KeyContacts")

    assert form.form_json_schema["x-mapping-from-cg"] == {}
    assert form.form_json_schema["x-mapping-to-cg"] == {}


def test_accepted_mapping_count_is_derived_from_occurrence_state(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["forms"][0]["question_bindings"][0]["mapping_status"] = "accepted"
    manifest["forms"][0]["review_boundary"]["semantic_mappings"] = "accepted"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    projection = load_portable_form_bundle(root).analysis_projection()

    assert projection["summary"]["accepted_associations"] == 1
    assert projection["summary"]["published_associations"] == 0


def test_rejects_published_coverage_with_unaccepted_occurrence(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["forms"][0]["review_boundary"]["published_coverage_eligible"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PortableFormBundleError, match="unaccepted occurrence mappings"):
        load_portable_form_bundle(root)


def test_rejects_published_coverage_before_form_semantics_are_accepted(
    tmp_path: Path,
) -> None:
    root = _copy_bundle(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    form = manifest["forms"][0]
    for binding in form["question_bindings"]:
        binding["mapping_status"] = "accepted"
    form["review_boundary"]["published_coverage_eligible"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PortableFormBundleError, match="form semantic mappings are accepted"):
        load_portable_form_bundle(root)


def test_rejects_tampered_schema(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    schema_path = root / "schemas/questions/organization-legal-name.schema.json"
    schema_path.write_text(schema_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(PortableFormBundleError, match="sha256 does not match"):
        load_portable_form_bundle(root)


def test_rejects_dangling_question_reference(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    relative_path = "schemas/forms/sf424-v4.schema.json"
    schema_path = root / relative_path
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["properties"]["organization_name"][
        "$ref"
    ] = "https://schemas.simpler.grants.gov/questions/missing/v1"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    _rewrite_manifest_hash(root, relative_path)

    with pytest.raises(PortableFormBundleError, match="unbundled schema reference"):
        load_portable_form_bundle(root)


def test_rejects_unknown_manifest_fields(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["forms"][0]["custom_python_builder"] = "not allowed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PortableFormBundleError, match="invalid keys"):
        load_portable_form_bundle(root)


def test_rejects_invalid_external_source_evidence(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed = copy.deepcopy(manifest)
    changed["forms"][0]["source_evidence"][0]["revision"] = "not-a-revision"
    manifest_path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(PortableFormBundleError, match="full lowercase git SHA"):
        load_portable_form_bundle(root)


def test_every_question_descriptor_has_direct_exact_source_provenance() -> None:
    manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    questions = [schema for schema in manifest["schemas"] if schema["kind"] == "question"]

    assert len(questions) == 167
    assert all(question["source_evidence"] for question in questions)
    assert all(
        source_ref in manifest["sources"]
        for question in questions
        for source_ref in question["source_evidence"]
    )
    assert all(
        len(manifest["sources"][source_ref]["sha256"]) == 64
        for question in questions
        for source_ref in question["source_evidence"]
    )


def test_rejects_question_with_missing_source_provenance(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    question = next(schema for schema in manifest["schemas"] if schema["kind"] == "question")
    question["source_evidence"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PortableFormBundleError, match="source_evidence cannot be empty"):
        load_portable_form_bundle(root)


def test_rejects_question_with_dangling_or_malformed_source_provenance(
    tmp_path: Path,
) -> None:
    root = _copy_bundle(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    question = next(schema for schema in manifest["schemas"] if schema["kind"] == "question")
    question["source_evidence"] = ["missing-source"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PortableFormBundleError, match="does not resolve"):
        load_portable_form_bundle(root)

    manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    source_ref = next(iter(manifest["sources"]))
    manifest["sources"][source_ref]["sha256"] = "not-a-hash"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PortableFormBundleError, match="lowercase SHA-256 digest"):
        load_portable_form_bundle(root)
