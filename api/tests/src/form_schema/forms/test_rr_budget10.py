import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.constants.lookup_constants import FormType
from src.form_schema.components.budget_family import (
    BudgetFamilyConfig,
    BudgetFamilyError,
    build_budget_family_form,
)
from src.form_schema.forms.rr_budget import RRBudget_v3_0
from src.form_schema.forms.rr_budget10 import RRBudget10_v3_0
from src.form_schema.rule_processing.json_rule_context import JsonRuleConfig, JsonRuleContext
from src.form_schema.rule_processing.json_rule_processor import process_rule_schema_for_context

_PACKAGE_DIR = (
    Path(__file__).parents[4]
    / "src"
    / "form_schema"
    / "forms"
    / "rr_budget10"
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


def _runtime_schema(value: object, *, root: bool = True) -> object:
    if isinstance(value, dict):
        return {
            key: _runtime_schema(child, root=False)
            for key, child in value.items()
            if not key.startswith("x-") and not (root and key in {"$id", "title"})
        }
    if isinstance(value, list):
        return [_runtime_schema(child, root=False) for child in value]
    return value


def _canonical_hash(value: object) -> str:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def test_rr_budget10_is_the_ten_period_native_budget_profile() -> None:
    assert RRBudget10_v3_0.form_type == FormType.RR_BUDGET_10
    assert RRBudget10_v3_0.short_form_name == "RR_Budget10_3_0"
    assert RRBudget10_v3_0.form_json_schema["properties"]["budget_year"]["maxItems"] == 10
    assert RRBudget10_v3_0.json_to_xml_schema is None

    ui_nodes = list(_walk_ui(RRBudget10_v3_0.form_ui_schema))
    assert len([item for item in ui_nodes if item[0] == "field"]) == 157
    assert len([item for item in ui_nodes if item[0] == "array"]) == 5
    assert _count_rules(RRBudget10_v3_0.form_rule_schema, "gg_pre_population") == 30
    assert _count_rules(RRBudget10_v3_0.form_rule_schema, "gg_validation") == 3


def test_budget_profiles_differ_only_by_period_limit_after_source_metadata() -> None:
    five_year = _runtime_schema(RRBudget_v3_0.form_json_schema)
    ten_year = _runtime_schema(RRBudget10_v3_0.form_json_schema)
    assert isinstance(five_year, dict)
    assert isinstance(ten_year, dict)
    ten_year["properties"]["budget_year"]["maxItems"] = 5
    assert ten_year == five_year
    assert RRBudget10_v3_0.form_ui_schema == RRBudget_v3_0.form_ui_schema
    assert RRBudget10_v3_0.form_rule_schema == RRBudget_v3_0.form_rule_schema


def test_shared_builder_preserves_the_original_five_year_runtime_artifacts() -> None:
    form_module = importlib.reload(
        importlib.import_module("src.form_schema.forms.rr_budget.1.0.form_json")
    )
    fresh_rr_budget = form_module.RRBudget_v3_0

    assert _canonical_hash(fresh_rr_budget.form_json_schema) == (
        "a69d80c8d23072284101bc3798196be2cbaf9ec8c4f9f775fab94f0069d978e7"
    )
    assert _canonical_hash(fresh_rr_budget.form_ui_schema) == (
        "b8f59435180c791fc312de7c83da127a5b8f0ec0233f17ec83aaf58d3437ebed"
    )
    assert _canonical_hash(fresh_rr_budget.form_rule_schema) == (
        "4e2239d4c53f21247b5d4f337d1d89c66d8d9e6059b4c70733ee3e50469195b5"
    )


def test_rr_budget10_executes_the_reused_calculation_graph() -> None:
    application_response = {
        "budget_year": [
            {"travel": {"domestic_travel_cost": "10.00"}},
            {"travel": {"domestic_travel_cost": "15.25"}},
        ],
        "budget_summary": {},
    }
    application_form = SimpleNamespace(
        application_response=application_response,
        form=RRBudget10_v3_0,
        application_form_id="draft-budget10-test",
        form_id=RRBudget10_v3_0.form_id,
    )
    context = JsonRuleContext(
        application_form,
        JsonRuleConfig(do_pre_population=True, do_post_population=False, do_field_validation=False),
    )
    process_rule_schema_for_context(context)
    assert context.json_data["budget_summary"]["cumulative_domestic_travel_costs"] == "25.25"


def test_rr_budget10_package_is_pinned_and_keeps_target_behavior_gap_explicit() -> None:
    manifest = json.loads((_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest["artifacts"].items():
        assert hashlib.sha256((_PACKAGE_DIR / name).read_bytes()).hexdigest() == expected_hash
    assert manifest["source_evidence"]["nodes"] == 199
    assert manifest["source_evidence"]["countable_questions"] == 107
    assert manifest["source_evidence"]["behavior_model"] == {
        "status": "inherited_source_bound_budget_family_evidence",
        "target_form_dat_parity": "not_established",
    }
    assert manifest["review_boundary"]["published_coverage_eligible"] is False
    assert manifest["review_boundary"]["production_ready"] is False
    assert manifest["review_boundary"]["target_form_behavior_parity"] == "not_established"


@pytest.mark.parametrize("field,value", [("source_form_id", "wrong"), ("budget_periods", 9)])
def test_budget_family_builder_rejects_profile_drift(field: str, value: object) -> None:
    values = {
        "source_form_id": "RRBudget10",
        "form_id": RRBudget10_v3_0.form_id,
        "form_name": RRBudget10_v3_0.form_name,
        "short_form_name": RRBudget10_v3_0.short_form_name,
        "form_version": "3.0",
        "form_type": FormType.RR_BUDGET_10,
        "form_instruction_id": RRBudget10_v3_0.form_instruction_id,
        "budget_periods": 10,
        "countable_questions": 107,
    }
    values[field] = value
    with pytest.raises(BudgetFamilyError):
        build_budget_family_form(_PACKAGE_DIR, BudgetFamilyConfig(**values))
