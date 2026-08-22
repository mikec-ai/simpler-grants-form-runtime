import json
import shutil
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from src.form_schema.portable_form_bundle import (
    PortableFormBundleError,
    load_portable_form_bundle,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BUNDLE_ROOT = REPOSITORY_ROOT / "form-specs"
COMPILER = REPOSITORY_ROOT / "scripts/compile_portable_form_bundle.py"


def _copy_compiler_bundle(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "portable-authoring"
    shutil.copytree(BUNDLE_ROOT, root / "form-specs")
    (root / "scripts").mkdir()
    shutil.copy(COMPILER, root / "scripts/compile_portable_form_bundle.py")
    kernel = root / "api/src/form_schema/portable_form_kernel.py"
    kernel.parent.mkdir(parents=True)
    shutil.copy(
        REPOSITORY_ROOT / "api/src/form_schema/portable_form_kernel.py",
        kernel,
    )
    return root, root / "form-specs"


def test_generic_compiler_reproduces_the_runtime_manifest_exactly(
    tmp_path: Path,
) -> None:
    root, bundle = _copy_compiler_bundle(tmp_path)
    before = (bundle / "manifest.json").read_bytes()
    (bundle / "manifest.json").unlink()

    result = subprocess.run(
        [sys.executable, "scripts/compile_portable_form_bundle.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "status: compiled" in result.stdout
    assert (bundle / "manifest.json").read_bytes() == before


def test_generic_compiler_check_and_bundle_remain_loadable(tmp_path: Path) -> None:
    root, bundle = _copy_compiler_bundle(tmp_path)

    result = subprocess.run(
        [sys.executable, "scripts/compile_portable_form_bundle.py", "--check"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "status: current" in result.stdout
    assert len(load_portable_form_bundle(bundle).forms_by_key) == 8


def test_portable_contract_independently_validates_every_authoring_and_runtime_document() -> (
    None
):
    catalog = json.loads((BUNDLE_ROOT / "catalog.json").read_text(encoding="utf-8"))
    contract = json.loads(
        (BUNDLE_ROOT / catalog["contract_schema"]["path"]).read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator.check_schema(contract)
    validator = jsonschema.Draft202012Validator(
        contract,
        format_checker=jsonschema.FormatChecker(),
    )

    validator.validate(catalog)
    for descriptor in catalog["form_declarations"]:
        validator.validate(
            json.loads((BUNDLE_ROOT / descriptor["path"]).read_text(encoding="utf-8"))
        )
    validator.validate(
        json.loads((BUNDLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    )


def test_contract_rejects_an_occurrence_without_its_role(tmp_path: Path) -> None:
    root, bundle = _copy_compiler_bundle(tmp_path)
    catalog_path = bundle / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    descriptor = catalog["form_declarations"][0]
    declaration_path = bundle / descriptor["path"]
    declaration = json.loads(declaration_path.read_text(encoding="utf-8"))
    del declaration["question_bindings"][0]["role"]
    encoded = (json.dumps(declaration, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    declaration_path.write_bytes(encoded)
    descriptor["sha256"] = __import__("hashlib").sha256(encoded).hexdigest()
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/compile_portable_form_bundle.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "form declaration violates the portable contract" in result.stderr


def test_compiler_fails_closed_when_the_governing_contract_drifts(
    tmp_path: Path,
) -> None:
    root, bundle = _copy_compiler_bundle(tmp_path)
    catalog = json.loads((bundle / "catalog.json").read_text(encoding="utf-8"))
    contract = bundle / catalog["contract_schema"]["path"]
    contract.write_bytes(contract.read_bytes() + b"\n")

    result = subprocess.run(
        [sys.executable, "scripts/compile_portable_form_bundle.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "contract schema hash mismatch" in result.stderr


def test_generic_compiler_fails_closed_on_declaration_drift(tmp_path: Path) -> None:
    root, bundle = _copy_compiler_bundle(tmp_path)
    catalog = json.loads((bundle / "catalog.json").read_text(encoding="utf-8"))
    declaration = bundle / catalog["form_declarations"][0]["path"]
    declaration.write_bytes(declaration.read_bytes() + b"\n")

    result = subprocess.run(
        [sys.executable, "scripts/compile_portable_form_bundle.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "code: compile_failed" in result.stdout
    assert "form declaration hash mismatch" in result.stderr


def test_generic_compiler_runs_full_kernel_validation_before_writing(
    tmp_path: Path,
) -> None:
    root, bundle = _copy_compiler_bundle(tmp_path)
    catalog_path = bundle / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    descriptor = catalog["form_declarations"][0]
    declaration = bundle / descriptor["path"]
    form = json.loads(declaration.read_text(encoding="utf-8"))
    form["review_boundary"]["published_coverage_eligible"] = True
    encoded = (json.dumps(form, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    declaration.write_bytes(encoded)
    descriptor["sha256"] = __import__("hashlib").sha256(encoded).hexdigest()
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    original_manifest = (bundle / "manifest.json").read_bytes()

    result = subprocess.run(
        [sys.executable, "scripts/compile_portable_form_bundle.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "compiled bundle failed kernel validation" in result.stderr
    assert (bundle / "manifest.json").read_bytes() == original_manifest


def test_simpler_adapter_rejects_duplicate_form_ids(tmp_path: Path) -> None:
    root, bundle = _copy_compiler_bundle(tmp_path)
    catalog_path = bundle / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    first_path = bundle / catalog["form_declarations"][0]["path"]
    second_descriptor = catalog["form_declarations"][1]
    second_path = bundle / second_descriptor["path"]
    first = json.loads(first_path.read_text(encoding="utf-8"))
    second = json.loads(second_path.read_text(encoding="utf-8"))
    second["adapters"]["simpler"]["configuration"]["form_id"] = first["adapters"][
        "simpler"
    ]["configuration"]["form_id"]
    encoded = (json.dumps(second, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    second_path.write_bytes(encoded)
    second_descriptor["sha256"] = __import__("hashlib").sha256(encoded).hexdigest()
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/compile_portable_form_bundle.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    with pytest.raises(PortableFormBundleError, match="duplicate Simpler form_id"):
        load_portable_form_bundle(bundle)


def test_generic_compiler_preserves_oracle_drift_assurance(tmp_path: Path) -> None:
    root, bundle = _copy_compiler_bundle(tmp_path)
    catalog = json.loads((bundle / "catalog.json").read_text(encoding="utf-8"))
    budget_descriptor = next(
        descriptor
        for descriptor in catalog["form_declarations"]
        if descriptor["path"].endswith("rr-budget.form.json")
    )
    budget = json.loads(
        (bundle / budget_descriptor["path"]).read_text(encoding="utf-8")
    )
    oracle = bundle / budget["supplemental_evidence"][0]["path"]
    oracle.write_bytes(oracle.read_bytes() + b"\n")

    result = subprocess.run(
        [sys.executable, "scripts/compile_portable_form_bundle.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "sha256 does not match" in result.stderr


def test_compiler_passes_through_new_consumer_adapter_without_code_changes(
    tmp_path: Path,
) -> None:
    root, bundle = _copy_compiler_bundle(tmp_path)
    catalog_path = bundle / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    descriptor = catalog["form_declarations"][0]
    declaration = bundle / descriptor["path"]
    form = json.loads(declaration.read_text(encoding="utf-8"))
    form["adapters"] = {
        "reference_renderer": {
            "artifacts": {"behavior_notes": form["supplemental_evidence"][0]}
        }
    }
    encoded = (json.dumps(form, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    declaration.write_bytes(encoded)
    descriptor["sha256"] = __import__("hashlib").sha256(encoded).hexdigest()
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/compile_portable_form_bundle.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert (
        manifest["forms"][0]["adapters"]["reference_renderer"]
        == form["adapters"]["reference_renderer"]
    )


def test_generic_compiler_cli_is_agent_friendly_and_strict(tmp_path: Path) -> None:
    root, _ = _copy_compiler_bundle(tmp_path)
    unknown = subprocess.run(
        [sys.executable, "scripts/compile_portable_form_bundle.py", "--wat"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    version = subprocess.run(
        [sys.executable, "scripts/compile_portable_form_bundle.py", "--version"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert unknown.returncode == 2
    assert "code: usage" in unknown.stdout
    assert "unrecognized arguments: --wat" in unknown.stderr
    assert version.returncode == 0
    assert version.stdout == "0.2.0\n"


def test_compiler_contains_no_form_or_question_semantic_authority() -> None:
    source = COMPILER.read_text(encoding="utf-8")
    manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    forbidden = {form["form_key"] for form in manifest["forms"]}
    forbidden.update(
        schema["question_id"]
        for schema in manifest["schemas"]
        if schema["kind"] == "question"
    )

    assert not [value for value in forbidden if value in source]
