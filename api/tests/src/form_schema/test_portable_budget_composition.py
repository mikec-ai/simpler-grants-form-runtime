import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from src.form_schema.portable_form_bundle import load_portable_form_bundle
from src.form_schema.portable_form_kernel import PortableFormKernelError

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BUNDLE_ROOT = REPOSITORY_ROOT / "form-specs"


def _walk(node):
    yield node
    if isinstance(node, dict):
        for child in node.values():
            yield from _walk(child)
    elif isinstance(node, list):
        for child in node:
            yield from _walk(child)


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _copy_builders(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "portable-composition"
    shutil.copytree(BUNDLE_ROOT, root / "form-specs")
    (root / "scripts").mkdir()
    for name in (
        "build_portable_budget_pilot.py",
        "build_portable_budget_composition.py",
    ):
        shutil.copy(REPOSITORY_ROOT / "scripts" / name, root / "scripts" / name)
    return root, root / "form-specs"


def test_subaward_composes_exact_budget_payload_and_separates_mechanisms() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)
    form = bundle.forms_by_key["RRSubawardBudget30"]
    semantic = [
        binding
        for binding in form.definition["question_bindings"]
        if binding.get("analysis_classification", "semantic_question")
        == "semantic_question"
    ]
    mechanisms = [
        binding
        for binding in form.definition["question_bindings"]
        if binding.get("analysis_classification") == "content_capture_mechanism"
    ]

    assert len(semantic) == 101
    assert len(mechanisms) == 30
    assert {binding["context"]["ordinal"] for binding in mechanisms} == set(
        range(1, 31)
    )
    assert all(binding["context"]["outer_repeat_max"] == 30 for binding in semantic)
    assert (
        bundle.to_form("RRSubawardBudget30").form_json_schema["properties"][
            "budget_attachments"
        ]["properties"]["rr_budget_3_0"]["maxItems"]
        == 30
    )


def test_composition_overlap_is_derived_from_semantic_identities_only() -> None:
    projection = load_portable_form_bundle(BUNDLE_ROOT).analysis_projection()

    def pair(form_a: str, form_b: str):
        return next(
            row
            for row in projection["pairwise_form_overlap"]
            if {row["form_a"], row["form_b"]} == {form_a, form_b}
        )

    subaward = pair("RRBudget", "RRSubawardBudget30")
    multi_project = pair("RRBudget", "RRMPBudget")

    assert subaward["proposed_overlap"]["questions_in_common"] == 101
    assert subaward["proposed_overlap"]["similarity"] == pytest.approx(1.0)
    assert multi_project["proposed_overlap"]["questions_in_common"] == 101
    assert multi_project["proposed_overlap"]["similarity"] == pytest.approx(1.0)
    assert subaward["accepted_overlap"]["questions_in_common"] == 0
    assert projection["summary"]["content_capture_mechanism_associations"] == 30


def test_multi_project_preserves_validation_variants_under_shared_identity() -> None:
    manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    evidence = json.loads(
        (BUNDLE_ROOT / "evidence/rr-budget-composition-wave.json").read_text(
            encoding="utf-8"
        )
    )
    mp = next(form for form in manifest["forms"] if form["form_key"] == "RRMPBudget")
    base = next(form for form in manifest["forms"] if form["form_key"] == "RRBudget")
    base_schemas = {
        binding["question_id"]: binding["schema_id"]
        for binding in base["question_bindings"]
    }

    variants = [
        binding
        for binding in mp["question_bindings"]
        if binding["schema_id"] != base_schemas[binding["question_id"]]
    ]
    assert len(variants) == 14
    assert len(mp["question_bindings"]) == 101
    assert evidence["forms"]["RRMPBudget"]["exact_schema_reuse"] == 87
    assert evidence["forms"]["RRMPBudget"]["validation_profile_variants"] == 14
    assert evidence["semantic_identity_status"] == "agent_proposed"


def test_composed_forms_project_only_source_resolved_calculations() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)

    def sums(form_key: str) -> int:
        return sum(
            1
            for node in _walk(bundle.to_form(form_key).form_rule_schema)
            if isinstance(node, dict) and node.get("rule") == "sum_monetary"
        )

    assert sums("RRSubawardBudget30") == 30
    assert sums("RRMPBudget") == 10
    evidence = json.loads(
        (BUNDLE_ROOT / "evidence/rr-budget-composition-wave.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["forms"]["RRMPBudget"]["calculations_preserved_not_projected"] == 46
    assert (
        evidence["forms"]["RRSubawardBudget30"]["conditions_source_bound_not_projected"]
        == 20
    )


def test_question_schema_variants_are_supported_but_schema_ids_remain_unique() -> None:
    manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    questions = [item for item in manifest["schemas"] if item["kind"] == "question"]
    prefix = [
        item
        for item in questions
        if item["question_id"] == "question:person:name:prefix"
    ]

    assert len(prefix) == 2
    assert len({item["id"] for item in questions}) == len(questions)
    load_portable_form_bundle(BUNDLE_ROOT)


def test_unknown_analysis_classification_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    shutil.copytree(BUNDLE_ROOT, root)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    form = next(
        item for item in manifest["forms"] if item["form_key"] == "RRSubawardBudget30"
    )
    form["question_bindings"][0]["analysis_classification"] = "looks_like_a_question"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(
        PortableFormKernelError, match="analysis_classification is unknown"
    ):
        load_portable_form_bundle(root)


def test_composition_build_chain_is_reproducible(tmp_path: Path) -> None:
    root, specs = _copy_builders(tmp_path)
    before = _tree_digest(specs)

    subprocess.run(
        [sys.executable, "scripts/build_portable_budget_pilot.py"], cwd=root, check=True
    )
    subprocess.run(
        [sys.executable, "scripts/build_portable_budget_composition.py"],
        cwd=root,
        check=True,
    )

    assert _tree_digest(specs) == before


def test_composition_builder_fails_closed_on_variant_drift(tmp_path: Path) -> None:
    root, specs = _copy_builders(tmp_path)
    path = specs / "oracles/budget/rr-mp-budget-v3.candidate.json"
    candidate = json.loads(path.read_text(encoding="utf-8"))
    candidate["artifacts"]["json_schema"]["properties"]["organization_name"][
        "maxLength"
    ] = 59
    path.write_text(json.dumps(candidate), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/build_portable_budget_composition.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "unexpected multi-project reuse partition" in result.stdout
