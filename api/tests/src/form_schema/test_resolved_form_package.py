import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from src.form_schema.registry.form_template_registry import FormTemplateKey, FormTemplateRegistry
from src.form_schema.resolved_form_package import (
    CONTRACT,
    ResolvedFormPackageError,
    load_resolved_form_package,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "form_schema" / "commongrants_key_contact_org"
COMPLETE_FIXTURE = (
    Path(__file__).parents[2] / "fixtures" / "form_schema" / "commongrants_key_contact_complete"
)


def _copy_fixture(tmp_path: Path) -> Path:
    package_root = tmp_path / "package"
    shutil.copytree(FIXTURE, package_root)
    return package_root


def _copy_complete_fixture(tmp_path: Path) -> Path:
    package_root = tmp_path / "complete-package"
    shutil.copytree(COMPLETE_FIXTURE, package_root)
    return package_root


def test_loads_source_pinned_common_grants_question_as_native_form() -> None:
    package = load_resolved_form_package(FIXTURE)
    form = package.to_form()

    assert package.manifest["contract"] == CONTRACT
    assert package.manifest["source_set"]["revision"] == (
        "65a4de852c96d35e946e8dde9f7a9864f718d8bb"
    )
    assert package.manifest["question_bindings"] == [
        {
            "question_id": "QuestionOrgName",
            "form_pointer": "/properties/org",
            "overrides": {"uiSchema": {"name": {"label": "Applicant Organization Name"}}},
        }
    ]
    assert form.form_json_schema["properties"]["org"]["required"] == ["name"]
    assert form.form_ui_schema[0]["children"][0] == {
        "type": "field",
        "definition": "/properties/org/properties/name",
        "label": "Applicant Organization Name",
    }
    assert form.form_json_schema["x-mapping-from-cg"] == {
        "org": {"name": {"field": "organizations.primary.name"}}
    }
    assert form.form_json_schema["x-mapping-to-cg"] == {
        "organizations": {"primary": {"name": {"field": "org.name"}}}
    }
    assert form.form_json_schema["x-simpler-form-package"] == {
        "contract": CONTRACT,
        "package_digest": package.package_digest,
        "source_set": package.manifest["source_set"],
        "compiler": package.manifest["compiler"],
        "question_bindings": package.manifest["question_bindings"],
        "review_boundary": package.manifest["review_boundary"],
        "projection_report": None,
    }
    assert {path.relative_to(FIXTURE).as_posix() for path in package.dependency_paths} == {
        "manifest.json",
        "json-schema.json",
        "ui-schema.json",
        "mappings.json",
        "sources/key-contact.tsp",
        "sources/org-name.tsp",
    }


def test_loads_complete_content_addressed_key_contact_package() -> None:
    package = load_resolved_form_package(COMPLETE_FIXTURE)
    form = package.to_form()

    assert package.manifest["source_set"]["closure"] == "complete"
    assert len(package.manifest["source_set"]["questions"]) == 2
    assert len(package.manifest["source_set"]["dependencies"]) == 61
    assert package.manifest["compiler"]["verification"] == "content_addressed"
    assert len(package.manifest["compiler"]["dependencies"]) == 9
    assert set(form.form_json_schema["properties"]) == {
        "contact",
        "contactCounty",
        "contactFax",
        "contactOrganizationalAffiliation",
        "org",
        "projectRole",
    }
    assert form.form_json_schema["properties"]["org"]["x-question-id"] == "QuestionOrgName"
    assert form.form_json_schema["properties"]["contact"]["x-question-id"] == ("QuestionPocDetails")
    assert package.projection_report is not None
    assert len(package.projection_report["dispositions"]["omitted_controls"]) == 3
    assert package.projection_report["dispositions"]["ui_projection"] == (
        "deterministic_structural"
    )
    assert form.form_json_schema["x-simpler-form-package"]["projection_report"] == (
        package.projection_report
    )


def test_to_form_allocates_independent_runtime_snapshots() -> None:
    package = load_resolved_form_package(FIXTURE)

    first = package.to_form()
    second = package.to_form()
    first.form_json_schema["properties"]["org"]["properties"]["name"]["title"] = "Changed"
    first.form_ui_schema[0]["label"] = "Changed"

    assert "title" not in second.form_json_schema["properties"]["org"]["properties"]["name"]
    assert second.form_ui_schema[0]["label"] == "Applicant organization"


def test_native_registry_accepts_resolved_package_without_package_runtime_path() -> None:
    package = load_resolved_form_package(FIXTURE)
    form = package.to_form()
    registry = FormTemplateRegistry()

    registry.register(form, major_version=1)

    registered = registry.get_by_id_and_major_version(FormTemplateKey(form.form_id, 1))
    assert registered.form_json_schema["properties"]["org"]["properties"]["name"] == {
        "type": "string",
        "description": "The organization's legal name",
    }
    assert registered.form_json_schema["x-mapping-from-cg"]["org"]["name"] == {
        "field": "organizations.primary.name"
    }


@pytest.mark.parametrize(
    ("relative_path", "expected_fragment"),
    [
        ("json-schema.json", "artifacts.json_schema.sha256 does not match"),
        (
            "sources/org-name.tsp",
            r"source_set\.questions\[0\]\.sha256 does not match",
        ),
    ],
)
def test_rejects_tampered_artifact_or_source(
    tmp_path: Path, relative_path: str, expected_fragment: str
) -> None:
    package_root = _copy_fixture(tmp_path)
    target = package_root / relative_path
    target.write_text(target.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")

    with pytest.raises(ResolvedFormPackageError, match=expected_fragment):
        load_resolved_form_package(package_root)


@pytest.mark.parametrize(
    ("manifest_path", "expected_fragment"),
    [
        (
            ("source_set", "dependencies", 0),
            r"source_set\.dependencies\[0\]\.sha256 does not match",
        ),
        (
            ("compiler", "dependencies", 0),
            r"compiler\.dependencies\[0\]\.sha256 does not match",
        ),
    ],
)
def test_complete_package_rejects_tampered_dependency(
    tmp_path: Path, manifest_path: tuple[object, ...], expected_fragment: str
) -> None:
    package_root = _copy_complete_fixture(tmp_path)
    manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    current: Any = manifest
    for token in manifest_path:
        current = current[token]
    descriptor = current
    target = package_root / descriptor["package_path"]
    target.write_text(target.read_text(encoding="utf-8") + "\ntampered\n", encoding="utf-8")

    with pytest.raises(ResolvedFormPackageError, match=expected_fragment):
        load_resolved_form_package(package_root)


def test_rejects_unknown_manifest_keys(tmp_path: Path) -> None:
    package_root = _copy_fixture(tmp_path)
    manifest_path = package_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["unreviewed_extension"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ResolvedFormPackageError, match="manifest has invalid keys"):
        load_resolved_form_package(package_root)


def test_rejects_artifact_path_escape(tmp_path: Path) -> None:
    package_root = _copy_fixture(tmp_path)
    manifest_path = package_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["json_schema"]["path"] = "../outside.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ResolvedFormPackageError, match="must remain inside the package"):
        load_resolved_form_package(package_root)


def test_rejects_repository_source_path_escape(tmp_path: Path) -> None:
    package_root = _copy_fixture(tmp_path)
    manifest_path = package_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_set"]["form"]["source_path"] = "../different-repository/form.tsp"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ResolvedFormPackageError, match="must be repository-relative"):
        load_resolved_form_package(package_root)


def test_rejects_binding_to_unpinned_question(tmp_path: Path) -> None:
    package_root = _copy_fixture(tmp_path)
    manifest_path = package_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["question_bindings"][0]["question_id"] = "QuestionNotPinned"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ResolvedFormPackageError, match="is absent from source_set"):
        load_resolved_form_package(package_root)


def test_mutating_public_schema_copy_does_not_change_verified_mapping() -> None:
    package = load_resolved_form_package(FIXTURE)
    schema = package.json_schema
    schema["x-mapping-from-cg"] = {"org": {"name": {"field": "wrong.path"}}}

    assert package.to_form().form_json_schema["x-mapping-from-cg"] == {
        "org": {"name": {"field": "organizations.primary.name"}}
    }


def test_rejects_mapping_conflict_in_verified_artifacts(tmp_path: Path) -> None:
    package_root = _copy_fixture(tmp_path)
    schema_path = package_root / "json-schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["x-mapping-from-cg"] = {"org": {"name": {"field": "wrong.path"}}}
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    manifest_path = package_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["json_schema"]["sha256"] = hashlib.sha256(
        schema_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    package = load_resolved_form_package(package_root)
    with pytest.raises(ResolvedFormPackageError, match="conflicts with the verified mappings"):
        package.to_form()


def test_rejects_nonexistent_question_binding_pointer(tmp_path: Path) -> None:
    package_root = _copy_fixture(tmp_path)
    manifest_path = package_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["question_bindings"][0]["form_pointer"] = "/properties/does-not-exist"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ResolvedFormPackageError, match="does not resolve in json_schema"):
        load_resolved_form_package(package_root)


def test_rejects_nonexistent_mapping_form_path(tmp_path: Path) -> None:
    package_root = _copy_fixture(tmp_path)
    mappings_path = package_root / "mappings.json"
    mappings = json.loads(mappings_path.read_text(encoding="utf-8"))
    mappings["x-mapping-to-cg"]["organizations"]["primary"]["name"]["field"] = "org.doesNotExist"
    mappings_path.write_text(json.dumps(mappings), encoding="utf-8")
    manifest_path = package_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["mappings"]["sha256"] = hashlib.sha256(
        mappings_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ResolvedFormPackageError, match="does not resolve in json_schema"):
        load_resolved_form_package(package_root)


def test_rejects_published_coverage_for_agent_proposed_projection(tmp_path: Path) -> None:
    package_root = _copy_fixture(tmp_path)
    manifest_path = package_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["review_boundary"]["published_coverage_eligible"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ResolvedFormPackageError, match="published coverage requires reviewed"):
        load_resolved_form_package(package_root)


def test_public_snapshots_cannot_mutate_verified_materialization() -> None:
    package = load_resolved_form_package(FIXTURE)
    manifest = package.manifest
    schema = package.json_schema
    mappings = package.mappings
    manifest["form"]["form_name"] = "Changed"
    schema["properties"].clear()
    mappings["x-mapping-from-cg"].clear()

    form = package.to_form()
    assert form.form_name == "CommonGrants Key Contact organization compatibility canary"
    assert "org" in form.form_json_schema["properties"]
    assert form.form_json_schema["x-mapping-from-cg"]


def test_loaded_package_is_independent_from_manifest_and_artifact_inputs() -> None:
    package = load_resolved_form_package(FIXTURE)
    original_manifest = copy.deepcopy(package.manifest)
    original_schema = copy.deepcopy(package.json_schema)

    form = package.to_form()
    form.form_json_schema["properties"].clear()

    assert package.manifest == original_manifest
    assert package.json_schema == original_schema
