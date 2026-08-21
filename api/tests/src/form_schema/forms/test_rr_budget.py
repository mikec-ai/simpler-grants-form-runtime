import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from src.constants.lookup_constants import FormType
from src.form_schema.forms.rr_budget import RRBudget_v3_0
from src.form_schema.forms.rr_budget.behaviors import (
    RRBudgetBehaviorError,
    compile_source_resolved_sum_rules,
)
from src.form_schema.rule_processing.json_rule_context import JsonRuleConfig, JsonRuleContext
from src.form_schema.rule_processing.json_rule_processor import process_rule_schema_for_context

_PACKAGE_DIR = (
    Path(__file__).parents[4]
    / "src"
    / "form_schema"
    / "forms"
    / "rr_budget"
    / "1"
    / "0"
    / "draft_package"
)


def _walk_ui(nodes: list[dict]):
    for node in nodes:
        if node["type"] in {"section", "fieldList"}:
            if node["type"] == "fieldList":
                yield "array", node["definition"]
            yield from _walk_ui(node["children"])
        else:
            yield "field", node["definition"]


def _count_rules(node: object, handler: str) -> int:
    if not isinstance(node, dict):
        return 0
    return (handler in node) + sum(_count_rules(value, handler) for value in node.values())


def _walk_schema(node: object):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_schema(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_schema(value)


def test_rr_budget_is_a_renderable_native_runtime_form() -> None:
    assert RRBudget_v3_0.form_type == FormType.RR_BUDGET
    assert RRBudget_v3_0.form_version == "3.0"
    assert RRBudget_v3_0.short_form_name == "RR_Budget_3_0"
    assert RRBudget_v3_0.form_name.startswith("[Draft]")
    assert RRBudget_v3_0.json_to_xml_schema is None

    ui_nodes = list(_walk_ui(RRBudget_v3_0.form_ui_schema))
    assert len([item for item in ui_nodes if item[0] == "field"]) == 157
    assert len([item for item in ui_nodes if item[0] == "array"]) == 5
    assert len(ui_nodes) == len(set(ui_nodes))
    assert all("RrBudgetPeriods" not in json.dumps(node) for node in RRBudget_v3_0.form_ui_schema)


def test_rr_budget_uses_exact_decimal_and_attachment_runtime_shapes() -> None:
    assert (
        len([node for node in _walk_schema(RRBudget_v3_0.form_json_schema) if "pattern" in node])
        == 115
    )
    validator = Draft202012Validator(
        RRBudget_v3_0.form_json_schema["properties"]["budget_year"]["items"]["properties"]["fee"]
    )
    for value in ("0", "12345678901234", "123456789012.34", "-1.2"):
        assert list(validator.iter_errors(value)) == []
    for value in (1.2, "1234567890123.45", "1.234"):
        assert list(validator.iter_errors(value))

    ui_text = json.dumps(RRBudget_v3_0.form_ui_schema)
    assert ui_text.count('"widget": "Attachment"') == 3
    assert _count_rules(RRBudget_v3_0.form_rule_schema, "gg_validation") == 3


def test_rr_budget_executes_only_the_30_resolved_source_sums() -> None:
    assert _count_rules(RRBudget_v3_0.form_rule_schema, "gg_pre_population") == 30
    application_response = {
        "budget_year": [
            {
                "key_persons": {
                    "key_person": [
                        {"requested_salary": "100.00", "fringe_benefits": "20.00"},
                        {"requested_salary": "75.50", "fringe_benefits": "4.50"},
                    ]
                },
                "travel": {"domestic_travel_cost": "10.00"},
            },
            {"travel": {"domestic_travel_cost": "15.25"}},
        ],
        "budget_summary": {},
    }
    application_form = SimpleNamespace(
        application_response=application_response,
        form=RRBudget_v3_0,
        application_form_id="draft-test",
        form_id=RRBudget_v3_0.form_id,
    )
    context = JsonRuleContext(
        application_form,
        JsonRuleConfig(do_pre_population=True, do_post_population=False, do_field_validation=False),
    )
    process_rule_schema_for_context(context)

    people = context.json_data["budget_year"][0]["key_persons"]["key_person"]
    assert [person["funds_requested"] for person in people] == ["120.00", "80.00"]
    assert context.json_data["budget_summary"]["cumulative_domestic_travel_costs"] == "25.25"


def test_rr_budget_package_is_pinned_and_fails_closed() -> None:
    manifest = json.loads((_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest["artifacts"].items():
        assert hashlib.sha256((_PACKAGE_DIR / name).read_bytes()).hexdigest() == expected_hash
    assert manifest["source_evidence"] == {
        "contract_source_version": (
            "sha256:b318951e0686bd7978ab791bd63ad36d6fa6e93b6368747b272526360e99fedb"
        ),
        "xsd": {
            "source_ref": "https://apply07.grants.gov/apply/forms/schemas/RR_Budget_3_0-V3.0.xsd",
            "sha256": "d474010f85819549990de65fc51292bed08ba98ac0895d0dde9513fbe855cdbc",
        },
        "dat": {
            "source_ref": "grants.gov:RR_Budget_3_0:V3.0:F770",
            "sha256": "c85158ce7ddcc756d6e8a55a050e00b4a95cdfc8d9a2d91b7bd94c7f8bdb1035",
        },
        "nodes": 199,
        "countable_questions": 97,
        "decimal_fields": 115,
        "repeating_groups": 5,
        "source_calculations": 56,
        "executable_source_resolved_sums": 30,
        "blocked_calculations": 26,
    }
    assert manifest["review_boundary"]["published_coverage_eligible"] is False
    assert manifest["review_boundary"]["production_ready"] is False
    assert manifest["review_boundary"]["xml_projection"] == "not_available"

    runtime_rules = json.loads((_PACKAGE_DIR / "runtime-rules.json").read_text(encoding="utf-8"))
    calculations = [rule for rule in runtime_rules["rules"] if rule["mechanism"] == "calculation"]
    assert len([rule for rule in calculations if rule["execution_class"] == "executable"]) == 30
    assert len([rule for rule in calculations if rule["execution_class"] == "evidence"]) == 26


@pytest.mark.parametrize("tamper", ["operator", "operand"])
def test_rr_budget_calculation_compiler_rejects_runtime_evidence_drift(tamper: str) -> None:
    candidate = json.loads((_PACKAGE_DIR / "candidate.json").read_text(encoding="utf-8"))
    runtime_rules = json.loads((_PACKAGE_DIR / "runtime-rules.json").read_text(encoding="utf-8"))
    executable = next(
        rule
        for rule in runtime_rules["rules"]
        if rule["mechanism"] == "calculation" and rule["execution_class"] == "executable"
    )
    if tamper == "operator":
        executable["operator"] = "invented"
    else:
        executable["operands"][0]["path"] = "RR_Budget_3_0.Unknown.Amount"

    with pytest.raises(RRBudgetBehaviorError):
        compile_source_resolved_sum_rules(
            deepcopy(candidate["artifacts"]["json_schema"]), runtime_rules
        )
