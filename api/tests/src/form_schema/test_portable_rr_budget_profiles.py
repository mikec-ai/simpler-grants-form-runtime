import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from src.form_schema.jsonschema_validator import validate_json_schema_for_form
from src.form_schema.portable_form_bundle import load_portable_form_bundle

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BUNDLE_ROOT = REPOSITORY_ROOT / "form-specs"
BUILDER = REPOSITORY_ROOT / "scripts/build_portable_budget_pilot.py"
COMPOSITION_BUILDER = REPOSITORY_ROOT / "scripts/build_portable_budget_composition.py"


def _walk(node: object):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _normalized_profile_schema(value: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(value)

    def normalize(node: object) -> None:
        if isinstance(node, dict):
            for key in list(node):
                if key in {
                    "$id",
                    "title",
                    "x-contract-sha256",
                    "x-cardinality",
                    "x-form-id",
                    "x-portable-form-bundle",
                    "x-portable-profile",
                    "x-question-key",
                    "x-semantic-mapping",
                    "x-simpler-form-package",
                    "x-source-path",
                }:
                    node.pop(key)
            for child in node.values():
                normalize(child)
        elif isinstance(node, list):
            for child in node:
                normalize(child)

    normalize(result)
    result["properties"]["budget_year"].pop("maxItems")
    return result


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _copied_builder(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "portable-budget"
    shutil.copytree(BUNDLE_ROOT, root / "form-specs")
    (root / "scripts").mkdir()
    shutil.copy(BUILDER, root / "scripts/build_portable_budget_pilot.py")
    shutil.copy(
        COMPOSITION_BUILDER,
        root / "scripts/build_portable_budget_composition.py",
    )
    return root, root / "form-specs"


def _remove_first_executable_rule(value: dict[str, Any]) -> None:
    index = next(
        index
        for index, rule in enumerate(value["rules"])
        if rule.get("mechanism") == "calculation"
        and rule.get("execution_class") == "executable"
    )
    value["rules"].pop(index)


def test_profiles_are_one_declarative_runtime_shape_with_one_parameter() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)
    five = bundle.to_form("RRBudget")
    ten = bundle.to_form("RRBudget10")

    assert len(bundle.forms_by_key["RRBudget"].definition["question_bindings"]) == 101
    assert len(bundle.forms_by_key["RRBudget10"].definition["question_bindings"]) == 101
    assert five.form_json_schema["properties"]["budget_year"]["maxItems"] == 5
    assert ten.form_json_schema["properties"]["budget_year"]["maxItems"] == 10
    assert _normalized_profile_schema(
        five.form_json_schema
    ) == _normalized_profile_schema(ten.form_json_schema)
    assert five.form_ui_schema == ten.form_ui_schema
    assert five.form_rule_schema == ten.form_rule_schema
    assert (
        sum(
            1
            for node in _walk(five.form_rule_schema)
            if isinstance(node, dict) and node.get("rule") == "sum_monetary"
        )
        == 30
    )
    assert (
        sum(
            1
            for node in _walk(five.form_ui_schema)
            if isinstance(node, dict) and node.get("type") == "fieldList"
        )
        == 5
    )


def test_budget_pair_analysis_is_explicitly_proposed_not_published() -> None:
    projection = load_portable_form_bundle(BUNDLE_ROOT).analysis_projection()
    pair = next(
        row
        for row in projection["pairwise_form_overlap"]
        if {row["form_a"], row["form_b"]} == {"RRBudget", "RRBudget10"}
    )

    assert pair["proposed_overlap"] == {
        "questions_in_common": 101,
        "unique_questions": 101,
        "similarity": 1.0,
        "form_a_coverage": 1.0,
        "form_b_coverage": 1.0,
    }
    assert pair["accepted_overlap"]["questions_in_common"] == 0
    assert pair["published_overlap"]["questions_in_common"] == 0
    assert pair["published_overlap"]["eligible"] is False


def test_budget_profile_evidence_reconciles_the_question_count_discrepancy() -> None:
    evidence = json.loads(
        (BUNDLE_ROOT / "evidence/rr-budget-family-profile.json").read_text(
            encoding="utf-8"
        )
    )

    assert evidence["template"] == {
        "only_runtime_parameter": "budget_year.maxItems",
        "profile_id": "profile:rr-budget-family:v1",
        "shared_executable_rule_graph": True,
        "shared_question_count": 101,
        "shared_ui": True,
    }
    assert evidence["source_question_count_discrepancy"] == {
        "previous_semantic_counts": {"RRBudget": 97, "RRBudget10": 107},
        "resolution": (
            "portable declarations classify identical input structure consistently; "
            "semantic acceptance remains agent_proposed"
        ),
        "structural_applicant_input_count_each": 101,
    }
    assert evidence["behavior_boundary"]["executable_exact_sums_each"] == 30
    assert evidence["behavior_boundary"]["blocked_each"] == 26
    assert (
        "exact native custom-widget parity is not claimed"
        in evidence["runtime_boundaries"]["nested_repeating_ui"]
    )
    assert (
        "attachment upload/runtime parity is not established"
        in evidence["runtime_boundaries"]["attachment_fields"]
    )
    assert evidence["xml_projection"] == (
        "not_available_in_pinned_implementation_oracle"
    )
    assert evidence["accepted_mappings"] == 0
    assert evidence["published_coverage_eligible"] is False


def test_budget_period_cardinality_is_enforced_by_each_profile() -> None:
    bundle = load_portable_form_bundle(BUNDLE_ROOT)
    five = bundle.to_form("RRBudget")
    ten = bundle.to_form("RRBudget10")

    five_issues = validate_json_schema_for_form({"budget_year": [{}] * 6}, five)
    ten_issues = validate_json_schema_for_form({"budget_year": [{}] * 11}, ten)

    assert any(issue.type == "maxItems" for issue in five_issues)
    assert any(issue.type == "maxItems" for issue in ten_issues)


def test_budget_builder_is_reproducible_in_an_isolated_copy(tmp_path: Path) -> None:
    root, specs = _copied_builder(tmp_path)
    before = _tree_digest(specs)

    subprocess.run(
        [sys.executable, "scripts/build_portable_budget_pilot.py"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/build_portable_budget_composition.py"],
        cwd=root,
        check=True,
    )

    assert _tree_digest(specs) == before


@pytest.mark.parametrize(
    ("relative_path", "mutation", "message"),
    [
        (
            "oracles/budget/rr-budget10-v3.candidate.json",
            lambda value: value["artifacts"]["json_schema"]["properties"][
                "budget_year"
            ].update({"maxItems": 11}),
            "budget period drift",
        ),
        (
            "oracles/budget/rr-budget-v3.runtime-rules.json",
            _remove_first_executable_rule,
            "expected 30 executable sums",
        ),
    ],
)
def test_budget_builder_fails_closed_on_oracle_drift(
    tmp_path: Path,
    relative_path: str,
    mutation,
    message: str,
) -> None:
    root, specs = _copied_builder(tmp_path)
    path = specs / relative_path
    value = json.loads(path.read_text(encoding="utf-8"))
    mutation(value)
    path.write_text(json.dumps(value), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/build_portable_budget_pilot.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert message in result.stdout


def test_budget_builder_cli_is_structured_and_fail_closed(tmp_path: Path) -> None:
    root, _ = _copied_builder(tmp_path)

    version = subprocess.run(
        [sys.executable, "scripts/build_portable_budget_pilot.py", "--version"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    unknown = subprocess.run(
        [sys.executable, "scripts/build_portable_budget_pilot.py", "--wat"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    success = subprocess.run(
        [sys.executable, "scripts/build_portable_budget_pilot.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert version.returncode == 0
    assert version.stdout == "0.1.0\n"
    assert unknown.returncode == 2
    assert "code: usage" in unknown.stdout
    assert "unknown argument: --wat" in unknown.stdout
    assert unknown.stderr == ""
    assert success.returncode == 0
    assert "status: generated" in success.stdout
    assert "shared_questions: 101" in success.stdout


def test_budget_runtime_adapter_contains_no_budget_form_branch() -> None:
    sources = "\n".join(
        (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "api/src/form_schema/portable_form_kernel.py",
            "api/src/form_schema/portable_form_bundle.py",
            "api/src/form_schema/resolved_form_package.py",
        )
    )

    assert "RRBudget" not in sources
    assert "rr_budget" not in sources
