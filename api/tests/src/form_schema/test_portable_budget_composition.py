import hashlib
import json
import shutil
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


def test_subaward_composes_exact_budget_payload_and_separates_mechanisms() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)
    form = bundle.forms_by_key["RRSubawardBudget30"]
    semantic = [
        binding
        for binding in form.definition["question_bindings"]
        if binding.get("analysis_classification", "semantic_question") == "semantic_question"
    ]
    mechanisms = [
        binding
        for binding in form.definition["question_bindings"]
        if binding.get("analysis_classification") == "content_capture_mechanism"
    ]

    assert len(semantic) == 101
    assert len(mechanisms) == 30
    assert {binding["context"]["ordinal"] for binding in mechanisms} == set(range(1, 31))
    assert all(binding["context"]["outer_repeat_max"] == 30 for binding in semantic)
    assert (
        bundle.to_form("RRSubawardBudget30").form_json_schema["properties"]["budget_attachments"][
            "properties"
        ]["rr_budget_3_0"]["maxItems"]
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
    assert projection["summary"]["content_capture_mechanism_associations"] == 90


def test_multi_project_preserves_validation_variants_under_shared_identity() -> None:
    manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    evidence = json.loads(
        (BUNDLE_ROOT / "evidence/rr-budget-composition-wave.json").read_text(encoding="utf-8")
    )
    mp = next(form for form in manifest["forms"] if form["form_key"] == "RRMPBudget")
    base = next(form for form in manifest["forms"] if form["form_key"] == "RRBudget")
    base_schemas = {
        binding["question_id"]: binding["schema_id"] for binding in base["question_bindings"]
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
        (BUNDLE_ROOT / "evidence/rr-budget-composition-wave.json").read_text(encoding="utf-8")
    )
    assert evidence["forms"]["RRMPBudget"]["calculations_preserved_not_projected"] == 46
    assert evidence["forms"]["RRSubawardBudget30"]["conditions_source_bound_not_projected"] == 20


def test_question_schema_variants_are_supported_but_schema_ids_remain_unique() -> None:
    manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    questions = [item for item in manifest["schemas"] if item["kind"] == "question"]
    prefix = [item for item in questions if item["question_id"] == "question:person:name:prefix"]

    assert len(prefix) == 2
    assert len({item["id"] for item in questions}) == len(questions)
    load_portable_form_bundle(BUNDLE_ROOT)


def test_unknown_analysis_classification_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    shutil.copytree(BUNDLE_ROOT, root)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    form = next(item for item in manifest["forms"] if item["form_key"] == "RRSubawardBudget30")
    form["question_bindings"][0]["analysis_classification"] = "looks_like_a_question"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PortableFormKernelError, match="analysis_classification is unknown"):
        load_portable_form_bundle(root)


def test_declaration_only_expansion_composes_existing_form_schemas() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)
    ten_subaward_schema = json.loads(
        (BUNDLE_ROOT / "schemas/forms/rr-subaward-budget10-30-v3.schema.json").read_text(
            encoding="utf-8"
        )
    )
    mp_subaward_schema = json.loads(
        (BUNDLE_ROOT / "schemas/forms/rr-mp-subaward-budget-v3.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert ten_subaward_schema["properties"]["budget_attachments"]["properties"][
        "rr_budget_10_3_0"
    ]["items"] == {"$ref": "urn:grants-form-kernel:forms:rrbudget10:v3"}
    assert mp_subaward_schema["properties"]["budget_attachments"]["properties"]["rr_mp_budget_3_0"][
        "items"
    ] == {"$ref": "urn:grants-form-kernel:forms:rr-mp-budget:v1"}

    ten = bundle.to_form("RRSubawardBudget10_30")
    mp = bundle.to_form("RRMPSubawardBudget")
    assert (
        ten.form_json_schema["properties"]["budget_attachments"]["properties"]["rr_budget_10_3_0"][
            "items"
        ]["properties"]["budget_year"]["maxItems"]
        == 10
    )
    assert (
        mp.form_json_schema["properties"]["budget_attachments"]["properties"]["rr_mp_budget_3_0"][
            "items"
        ]["properties"]["budget_year"]["maxItems"]
        == 10
    )


def test_expansion_preserves_behavior_boundaries_and_analysis_status() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)
    projection = bundle.analysis_projection()

    ten = bundle.forms_by_key["RRSubawardBudget10_30"].definition
    mp = bundle.forms_by_key["RRMPSubawardBudget"].definition
    for form in (ten, mp):
        semantic = [
            item
            for item in form["question_bindings"]
            if item["analysis_classification"] == "semantic_question"
        ]
        capture = [
            item
            for item in form["question_bindings"]
            if item["analysis_classification"] == "content_capture_mechanism"
        ]
        assert len(semantic) == 101
        assert len(capture) == 30
        assert form["review_boundary"]["published_coverage_eligible"] is False

    assert bundle.to_form("RRSubawardBudget10_30").form_rule_schema is not None
    assert bundle.to_form("RRMPSubawardBudget").form_rule_schema is None
    pair = next(
        row
        for row in projection["pairwise_form_overlap"]
        if {row["form_a"], row["form_b"]} == {"RRSubawardBudget30", "RRSubawardBudget10_30"}
    )
    assert pair["proposed_overlap"]["questions_in_common"] == 101
    assert pair["proposed_overlap"]["similarity"] == pytest.approx(1.0)
    assert pair["accepted_overlap"]["questions_in_common"] == 0
    assert pair["published_overlap"]["eligible"] is False

    evidence = json.loads(
        (BUNDLE_ROOT / "evidence/declarative-expansion-wave.json").read_text(encoding="utf-8")
    )
    assert (
        evidence["forms"]["RRMPSubawardBudget"]["behavior"]["sibling_calculation_inheritance"]
        == "explicitly_forbidden"
    )


def test_form_composition_rejects_sibling_keywords_and_cycles(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    shutil.copytree(BUNDLE_ROOT, root)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def rewrite(relative: str, mutation) -> None:
        path = root / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        mutation(value)
        path.write_text(json.dumps(value), encoding="utf-8")
        descriptor = next(
            item for item in manifest["schemas"] if item["artifact"]["path"] == relative
        )
        descriptor["artifact"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    rewrite(
        "schemas/forms/rr-mp-subaward-budget-v3.schema.json",
        lambda value: value["properties"]["budget_attachments"]["properties"]["rr_mp_budget_3_0"][
            "items"
        ].update({"title": "not allowed"}),
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PortableFormKernelError, match="cannot have sibling keywords"):
        load_portable_form_bundle(root)

    root = tmp_path / "cycle"
    shutil.copytree(BUNDLE_ROOT, root)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema_path = root / "schemas/forms/rr-mp-budget-v3.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["properties"]["cycle"] = {
        "$ref": "urn:grants-form-kernel:forms:rr-mp-subaward-budget:v1"
    }
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    descriptor = next(
        item
        for item in manifest["schemas"]
        if item["artifact"]["path"] == "schemas/forms/rr-mp-budget-v3.schema.json"
    )
    descriptor["artifact"]["sha256"] = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PortableFormKernelError, match="circular form schema composition"):
        load_portable_form_bundle(root)
