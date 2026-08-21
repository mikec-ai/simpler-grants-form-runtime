import hashlib
import importlib
import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from src.constants.lookup_constants import FormType
from src.db.models.competition_models import ApplicationForm
from src.form_schema.components.budget_family import (
    BudgetFamilyConfig,
    BudgetFamilyError,
    build_budget_family_form,
)
from src.form_schema.forms.rr_mp_budget import RRMPBudget_v3_0
from src.form_schema.forms.rr_mp_subaward_budget import RRMPSubawardBudget_v3_0
from src.form_schema.rule_processing.json_rule_context import JsonRuleConfig, JsonRuleContext
from src.form_schema.rule_processing.json_rule_processor import process_rule_schema_for_context

_FORM_MODULE = importlib.import_module("src.form_schema.forms.rr_mp_budget.1.0.form_json")

_PACKAGE_DIR = (
    Path(__file__).parents[4]
    / "src"
    / "form_schema"
    / "forms"
    / "rr_mp_budget"
    / "1"
    / "0"
    / "draft_package"
)


def _walk_ui(nodes: list[dict[str, Any]]) -> Iterator[tuple[str, dict[str, Any]]]:
    for node in nodes:
        if node["type"] in {"section", "fieldList"}:
            if node["type"] == "fieldList":
                yield "array", node
            yield from _walk_ui(node["children"])
        else:
            yield "field", node


def _count_rules(node: object, handler: str) -> int:
    if not isinstance(node, dict):
        return 0
    return (handler in node) + sum(_count_rules(value, handler) for value in node.values())


def _runtime_schema(value: object, *, root: bool = True) -> object:
    if isinstance(value, dict):
        return {
            key: _runtime_schema(child, root=False)
            for key, child in value.items()
            if not key.startswith("x-") and not (root and key in {"$id", "$schema", "title"})
        }
    if isinstance(value, list):
        return [_runtime_schema(child, root=False) for child in value]
    return value


def test_rr_mp_budget_is_a_standalone_ten_period_multi_project_profile() -> None:
    assert RRMPBudget_v3_0.form_type == FormType.RR_MP_BUDGET
    assert RRMPBudget_v3_0.short_form_name == "RR_MP_Budget_3_0"
    assert RRMPBudget_v3_0.form_version == "3.0"
    assert RRMPBudget_v3_0.json_to_xml_schema is None

    schema = RRMPBudget_v3_0.form_json_schema
    assert schema["properties"]["budget_year"]["maxItems"] == 10
    ui_nodes = list(_walk_ui(RRMPBudget_v3_0.form_ui_schema))
    assert len([node for kind, node in ui_nodes if kind == "field"]) == 157
    assert len([node for kind, node in ui_nodes if kind == "array"]) == 5
    assert len([node for kind, node in ui_nodes if kind == "field" and node.get("widget")]) == 3
    assert _count_rules(RRMPBudget_v3_0.form_rule_schema, "gg_pre_population") == 10
    assert _count_rules(RRMPBudget_v3_0.form_rule_schema, "gg_validation") == 3
    assert len(_FORM_MODULE._BUILD.compiled_rule_ids) == 10
    assert len(_FORM_MODULE._BUILD.structurally_satisfied_rule_ids) == 1


def test_standalone_profile_matches_the_previously_embedded_runtime_structure() -> None:
    embedded = RRMPSubawardBudget_v3_0.form_json_schema["properties"]["budget_attachments"][
        "properties"
    ]["rr_mp_budget_3_0"]["items"]
    assert _runtime_schema(RRMPBudget_v3_0.form_json_schema) == _runtime_schema(embedded)


def test_multi_project_cardinality_differences_remain_source_specific() -> None:
    period = RRMPBudget_v3_0.form_json_schema["properties"]["budget_year"]["items"]
    assert period["properties"]["key_persons"]["properties"]["key_person"]["maxItems"] == 100
    assert period["properties"]["equipment"]["properties"]["equipment_list"]["maxItems"] == 100


def test_exact_source_resolved_multi_project_sums_execute() -> None:
    application_response = {
        "budget_year": [
            {
                "travel": {
                    "domestic_travel_cost": "10.00",
                    "foreign_travel_cost": "2.50",
                },
                "indirect_costs": {
                    "indirect_cost": [
                        {"fund_requested": "4.00"},
                        {"fund_requested": "6.25"},
                    ]
                },
            },
            {
                "travel": {
                    "domestic_travel_cost": "15.25",
                    "foreign_travel_cost": "1.00",
                },
                "indirect_costs": {"indirect_cost": [{"fund_requested": "3.00"}]},
            },
        ],
        "budget_summary": {},
    }
    application_form = SimpleNamespace(
        application_response=application_response,
        form=RRMPBudget_v3_0,
        application_form_id="draft-rr-mp-budget-test",
        form_id=RRMPBudget_v3_0.form_id,
    )
    context = JsonRuleContext(
        cast(ApplicationForm, application_form),
        JsonRuleConfig(
            do_pre_population=True,
            do_post_population=False,
            do_field_validation=False,
        ),
    )
    process_rule_schema_for_context(context)

    first, second = context.json_data["budget_year"]
    assert first["travel"]["total_travel_cost"] == "12.50"
    assert second["travel"]["total_travel_cost"] == "16.25"
    assert first["indirect_costs"]["total_indirect_costs"] == "10.25"
    assert second["indirect_costs"]["total_indirect_costs"] == "3.00"
    assert context.json_data["budget_summary"]["cumulative_domestic_travel_costs"] == "25.25"
    assert context.json_data["budget_summary"]["cumulative_foreign_travel_costs"] == "3.50"


def test_package_pins_sources_and_keeps_unresolved_behavior_explicit() -> None:
    manifest = json.loads((_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest["artifacts"].items():
        assert hashlib.sha256((_PACKAGE_DIR / name).read_bytes()).hexdigest() == expected_hash
    evidence = manifest["source_evidence"]
    assert evidence["nodes"] == 199
    assert evidence["countable_questions"] == 157
    assert evidence["xsd"]["sha256"] == (
        "8ee3867971d4030582ff4c4cd906cd1a086c2d2491fb6f05b33cdd07ae435846"
    )
    assert evidence["executable_source_resolved_sums"] == 10
    assert evidence["blocked_calculations"] == 46
    assert evidence["source_resolved_conditions"] == 1
    assert evidence["conditions_satisfied_by_structure"] == 1
    assert evidence["projected_source_resolved_conditions"] == 0
    assert manifest["review_boundary"]["calculation_projection"] == ("source_bound_resolved_subset")
    assert manifest["review_boundary"]["condition_projection"] == (
        "source_bound_reconciled_to_structural_requiredness"
    )
    assert manifest["review_boundary"]["published_coverage_eligible"] is False
    assert manifest["review_boundary"]["production_ready"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("budget_periods", 5),
        ("countable_questions", 156),
        ("source_calculations", 55),
        ("executable_sums", 30),
        ("source_resolved_conditions", 2),
        ("projected_conditions", 1),
        ("subaward_items", 1),
    ],
)
def test_builder_rejects_multi_project_profile_drift(field: str, value: object) -> None:
    values = {
        "source_form_id": "RRMPBudget",
        "form_id": RRMPBudget_v3_0.form_id,
        "form_name": RRMPBudget_v3_0.form_name,
        "short_form_name": RRMPBudget_v3_0.short_form_name,
        "form_version": "3.0",
        "form_type": FormType.RR_MP_BUDGET,
        "form_instruction_id": RRMPBudget_v3_0.form_instruction_id,
        "budget_periods": 10,
        "countable_questions": 157,
        "executable_sums": 10,
        "source_resolved_conditions": 1,
    }
    values[field] = value
    with pytest.raises(BudgetFamilyError):
        build_budget_family_form(_PACKAGE_DIR, BudgetFamilyConfig(**values))
