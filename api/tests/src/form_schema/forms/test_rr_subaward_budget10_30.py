import hashlib
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
from src.form_schema.forms.rr_budget10 import RRBudget10_v3_0
from src.form_schema.forms.rr_subaward_budget10_30 import RRSubawardBudget10_30_v3_0
from src.form_schema.forms.rr_subaward_budget30 import RRSubawardBudget30_v3_0
from src.form_schema.rule_processing.json_rule_context import JsonRuleConfig, JsonRuleContext
from src.form_schema.rule_processing.json_rule_processor import process_rule_schema_for_context

_PACKAGE_DIR = (
    Path(__file__).parents[4]
    / "src"
    / "form_schema"
    / "forms"
    / "rr_subaward_budget10_30"
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
            if not key.startswith("x-") and not (root and key in {"$id", "$schema", "title"})
        }
    if isinstance(value, list):
        return [_runtime_schema(child, root=False) for child in value]
    return value


def test_rr_subaward_budget10_30_composes_thirty_ten_period_budget_profiles() -> None:
    assert RRSubawardBudget10_30_v3_0.form_type == FormType.RR_SUBAWARD_BUDGET_10_30
    assert RRSubawardBudget10_30_v3_0.short_form_name == "RR_SubawardBudget10_30_3_0"
    assert RRSubawardBudget10_30_v3_0.json_to_xml_schema is None

    schema = RRSubawardBudget10_30_v3_0.form_json_schema
    subawards = schema["properties"]["budget_attachments"]["properties"]["rr_budget_10_3_0"]
    assert subawards["maxItems"] == 30
    assert subawards["items"]["properties"]["budget_year"]["maxItems"] == 10
    assert _runtime_schema(subawards["items"]) == _runtime_schema(RRBudget10_v3_0.form_json_schema)

    ui_nodes = list(_walk_ui(RRSubawardBudget10_30_v3_0.form_ui_schema))
    assert len([item for item in ui_nodes if item[0] == "field"]) == 157
    assert len([item for item in ui_nodes if item[0] == "array"]) == 6
    assert _count_rules(RRSubawardBudget10_30_v3_0.form_rule_schema, "gg_pre_population") == 30
    assert _count_rules(RRSubawardBudget10_30_v3_0.form_rule_schema, "gg_validation") == 3


def test_subaward_profiles_differ_only_by_embedded_identity_and_period_limit() -> None:
    five_year = _runtime_schema(RRSubawardBudget30_v3_0.form_json_schema)
    ten_year = _runtime_schema(RRSubawardBudget10_30_v3_0.form_json_schema)
    assert isinstance(five_year, dict)
    assert isinstance(ten_year, dict)
    five_properties = five_year["properties"]["budget_attachments"]["properties"]
    five_budget = five_properties.pop("rr_budget_3_0")
    five_budget["items"]["properties"]["budget_year"]["maxItems"] = 10
    five_budget["items"]["title"] = "RR Budget10 3 0"
    five_properties["rr_budget_10_3_0"] = five_budget
    assert five_year == ten_year


def test_unresolved_technical_slots_remain_in_schema_but_are_not_rendered() -> None:
    properties = RRSubawardBudget10_30_v3_0.form_json_schema["properties"]
    technical_slots = {name for name in properties if name.startswith("att_")}
    assert technical_slots == {f"att_{index}" for index in range(1, 31)}
    assert all(properties[name]["type"] == "string" for name in technical_slots)
    rendered_definitions = {
        definition for _, definition in _walk_ui(RRSubawardBudget10_30_v3_0.form_ui_schema)
    }
    assert all(f"/properties/{name}" not in rendered_definitions for name in technical_slots)


def test_each_subaward_executes_cumulative_sums_in_its_own_parent_scope() -> None:
    cumulative_rule = RRSubawardBudget10_30_v3_0.form_rule_schema["budget_attachments"][
        "rr_budget_10_3_0"
    ]["budget_summary"]["cumulative_domestic_travel_costs"]["gg_pre_population"]
    assert cumulative_rule["fields"] == ["@PARENT.budget_year[*].travel.domestic_travel_cost"]

    application_response = {
        "budget_attachments": {
            "rr_budget_10_3_0": [
                {
                    "budget_year": [
                        {"travel": {"domestic_travel_cost": "10.00"}},
                        {"travel": {"domestic_travel_cost": "15.25"}},
                    ],
                    "budget_summary": {},
                },
                {
                    "budget_year": [{"travel": {"domestic_travel_cost": "100.00"}}],
                    "budget_summary": {},
                },
            ]
        }
    }
    application_form = SimpleNamespace(
        application_response=application_response,
        form=RRSubawardBudget10_30_v3_0,
        application_form_id="draft-subaward-budget10-30-test",
        form_id=RRSubawardBudget10_30_v3_0.form_id,
    )
    context = JsonRuleContext(
        application_form,
        JsonRuleConfig(
            do_pre_population=True,
            do_post_population=False,
            do_field_validation=False,
        ),
    )
    process_rule_schema_for_context(context)
    budgets = context.json_data["budget_attachments"]["rr_budget_10_3_0"]
    assert [budget["budget_summary"]["cumulative_domestic_travel_costs"] for budget in budgets] == [
        "25.25",
        "100.00",
    ]


def test_package_pins_sources_and_keeps_behavior_and_wire_gaps_explicit() -> None:
    manifest = json.loads((_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest["artifacts"].items():
        assert hashlib.sha256((_PACKAGE_DIR / name).read_bytes()).hexdigest() == expected_hash

    evidence = manifest["source_evidence"]
    assert evidence["nodes"] == 231
    assert evidence["countable_questions"] == 142
    assert evidence["xsd"]["sha256"] == (
        "0ed112b2e50f0e0c43423f690201b207f5b9c5a85349335260e4fd999f3a611a"
    )
    assert evidence["embedded_budget_xsd"]["sha256"] == (
        "cccce03554424d59b5958e4443a54db12a5a10780fbdc5df2ec25955d443fc9d"
    )
    assert evidence["technical_slot_disposition"] == {
        "count": 30,
        "status": "hidden_unresolved_wire_slots",
        "reason": "ATT names and xs:string types are not attachment semantics",
    }
    assert evidence["sibling_profile_comparison"] == {
        "sibling_form_id": "RRSubawardBudget30",
        "shared_node_count": 231,
        "target_countable_questions": 142,
        "sibling_countable_questions": 187,
        "implementation_structure": "equal_after_wire_identity_and_period_limit",
        "semantic_count_reconciliation": "open",
    }
    assert evidence["behavior_model"]["target_form_dat_parity"] == "not_established"
    assert manifest["review_boundary"]["published_coverage_eligible"] is False
    assert manifest["review_boundary"]["production_ready"] is False
    assert manifest["review_boundary"]["xml_projection"] == "not_available"


@pytest.mark.parametrize(
    "field,value",
    [
        ("subaward_items", 29),
        ("technical_slots", 29),
        ("budget_periods", 5),
        ("embedded_budget_key", "rr_budget_3_0"),
    ],
)
def test_budget_family_builder_rejects_subaward_profile_drift(field: str, value: object) -> None:
    values = {
        "source_form_id": "RRSubawardBudget10_30",
        "form_id": RRSubawardBudget10_30_v3_0.form_id,
        "form_name": RRSubawardBudget10_30_v3_0.form_name,
        "short_form_name": RRSubawardBudget10_30_v3_0.short_form_name,
        "form_version": "3.0",
        "form_type": FormType.RR_SUBAWARD_BUDGET_10_30,
        "form_instruction_id": RRSubawardBudget10_30_v3_0.form_instruction_id,
        "budget_periods": 10,
        "subaward_items": 30,
        "technical_slots": 30,
        "embedded_budget_key": "rr_budget_10_3_0",
        "source_nodes": 231,
        "countable_questions": 142,
        "repeating_groups": 6,
    }
    values[field] = value
    with pytest.raises(BudgetFamilyError):
        build_budget_family_form(_PACKAGE_DIR, BudgetFamilyConfig(**values))
