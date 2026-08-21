import hashlib
import json
from pathlib import Path

import pytest

from src.constants.lookup_constants import FormType
from src.form_schema.components.budget_family import (
    BudgetFamilyConfig,
    BudgetFamilyError,
    build_budget_family_form,
)
from src.form_schema.forms.rr_budget10 import RRBudget10_v3_0
from src.form_schema.forms.rr_mp_subaward_budget import RRMPSubawardBudget_v3_0

_PACKAGE_DIR = (
    Path(__file__).parents[4]
    / "src"
    / "form_schema"
    / "forms"
    / "rr_mp_subaward_budget"
    / "1"
    / "0"
    / "draft_package"
)


def _walk_ui(nodes: list[dict]):
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


def test_rr_mp_subaward_budget_composes_thirty_ten_period_profiles() -> None:
    assert RRMPSubawardBudget_v3_0.form_type == FormType.RR_MP_SUBAWARD_BUDGET
    assert RRMPSubawardBudget_v3_0.short_form_name == "RR_MP_SubawardBudget_3_0"
    assert RRMPSubawardBudget_v3_0.json_to_xml_schema is None

    schema = RRMPSubawardBudget_v3_0.form_json_schema
    subawards = schema["properties"]["budget_attachments"]["properties"]["rr_mp_budget_3_0"]
    assert subawards["maxItems"] == 30
    assert subawards["items"]["properties"]["budget_year"]["maxItems"] == 10

    ui_nodes = list(_walk_ui(RRMPSubawardBudget_v3_0.form_ui_schema))
    assert len([item for kind, item in ui_nodes if kind == "field"]) == 157
    assert len([item for kind, item in ui_nodes if kind == "array"]) == 6
    assert len([item for kind, item in ui_nodes if kind == "field" and item.get("widget")]) == 3
    assert _count_rules(RRMPSubawardBudget_v3_0.form_rule_schema, "gg_validation") == 3


def test_multi_project_cardinality_differences_are_preserved_not_normalized() -> None:
    multi_project = RRMPSubawardBudget_v3_0.form_json_schema["properties"]["budget_attachments"][
        "properties"
    ]["rr_mp_budget_3_0"]["items"]["properties"]["budget_year"]["items"]
    standard = RRBudget10_v3_0.form_json_schema["properties"]["budget_year"]["items"]

    assert multi_project["properties"]["key_persons"]["properties"]["key_person"]["maxItems"] == 100
    assert standard["properties"]["key_persons"]["properties"]["key_person"]["maxItems"] == 8
    assert (
        multi_project["properties"]["equipment"]["properties"]["equipment_list"]["maxItems"] == 100
    )
    assert standard["properties"]["equipment"]["properties"]["equipment_list"]["maxItems"] == 10


def test_missing_target_behavior_evidence_fails_closed_instead_of_inheriting_rules() -> None:
    assert _count_rules(RRMPSubawardBudget_v3_0.form_rule_schema, "gg_pre_population") == 0
    manifest = json.loads((_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_evidence"]["behavior_model"] == {
        "status": "insufficient_to_inherit_sibling_runtime_behavior",
        "source_behavior_records": 7,
        "calculation_records_observed": 0,
        "condition_records_observed": 0,
        "target_form_behavior_parity": "not_established",
    }
    assert manifest["review_boundary"]["calculation_projection"] == ("none_without_target_evidence")
    assert manifest["review_boundary"]["sibling_calculation_inheritance"] == (
        "explicitly_forbidden"
    )


def test_unresolved_technical_slots_remain_in_schema_but_are_not_rendered() -> None:
    properties = RRMPSubawardBudget_v3_0.form_json_schema["properties"]
    technical_slots = {name for name in properties if name.startswith("att_")}
    assert technical_slots == {f"att_{index}" for index in range(1, 31)}
    rendered_definitions = {
        item["definition"]
        for kind, item in _walk_ui(RRMPSubawardBudget_v3_0.form_ui_schema)
        if kind == "field"
    }
    assert all(f"/properties/{name}" not in rendered_definitions for name in technical_slots)


def test_package_pins_multi_project_sources_and_review_boundary() -> None:
    manifest = json.loads((_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest["artifacts"].items():
        assert hashlib.sha256((_PACKAGE_DIR / name).read_bytes()).hexdigest() == expected_hash
    evidence = manifest["source_evidence"]
    assert evidence["nodes"] == 231
    assert evidence["countable_questions"] == 187
    assert evidence["xsd"]["sha256"] == (
        "20dce5b3498c809727892ee6cb837db223d687564c5829d94fe481367b7815c4"
    )
    assert evidence["embedded_budget_xsd"]["sha256"] == (
        "8ee3867971d4030582ff4c4cd906cd1a086c2d2491fb6f05b33cdd07ae435846"
    )
    assert manifest["review_boundary"]["published_coverage_eligible"] is False
    assert manifest["review_boundary"]["production_ready"] is False
    assert manifest["review_boundary"]["xml_projection"] == "not_available"


@pytest.mark.parametrize(
    "field,value",
    [
        ("subaward_items", 29),
        ("budget_periods", 5),
        ("embedded_budget_key", "rr_budget_10_3_0"),
        ("source_calculations", 56),
        ("executable_sums", 30),
    ],
)
def test_budget_family_builder_rejects_multi_project_profile_drift(
    field: str, value: object
) -> None:
    values = {
        "source_form_id": "RRMPSubawardBudget",
        "form_id": RRMPSubawardBudget_v3_0.form_id,
        "form_name": RRMPSubawardBudget_v3_0.form_name,
        "short_form_name": RRMPSubawardBudget_v3_0.short_form_name,
        "form_version": "3.0",
        "form_type": FormType.RR_MP_SUBAWARD_BUDGET,
        "form_instruction_id": RRMPSubawardBudget_v3_0.form_instruction_id,
        "budget_periods": 10,
        "subaward_items": 30,
        "technical_slots": 30,
        "embedded_budget_key": "rr_mp_budget_3_0",
        "source_nodes": 231,
        "countable_questions": 187,
        "repeating_groups": 6,
        "source_calculations": 0,
        "executable_sums": 0,
    }
    values[field] = value
    with pytest.raises(BudgetFamilyError):
        build_budget_family_form(_PACKAGE_DIR, BudgetFamilyConfig(**values))
