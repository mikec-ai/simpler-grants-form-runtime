import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from src.constants.lookup_constants import FormType
from src.db.models.competition_models import ApplicationForm
from src.form_schema.components.source_resolved_form import (
    SourceResolvedFormConfig,
    SourceResolvedFormError,
    build_source_resolved_form,
)
from src.form_schema.forms.phs_fellowship_supplemental import (
    PHSFellowshipSupplemental_v8_0,
    _form_json,
)
from src.form_schema.rule_processing.json_rule_context import JsonRuleConfig, JsonRuleContext
from src.form_schema.rule_processing.json_rule_processor import process_rule_schema_for_context

_PACKAGE_DIR = (
    Path(__file__).parents[4]
    / "src"
    / "form_schema"
    / "forms"
    / "phs_fellowship_supplemental"
    / "1"
    / "0"
    / "draft_package"
)


def _walk_ui(nodes: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for node in nodes:
        yield node
        if node["type"] in {"section", "fieldList"}:
            yield from _walk_ui(node["children"])


def _ui_by_definition() -> dict[str, dict[str, Any]]:
    return {
        node["definition"]: node
        for node in _walk_ui(PHSFellowshipSupplemental_v8_0.form_ui_schema)
        if isinstance(node.get("definition"), str)
    }


def _config(**overrides: object) -> SourceResolvedFormConfig:
    values: dict[str, object] = {
        "source_form_id": "PHSFellowshipSupplemental",
        "form_id": PHSFellowshipSupplemental_v8_0.form_id,
        "form_name": PHSFellowshipSupplemental_v8_0.form_name,
        "short_form_name": PHSFellowshipSupplemental_v8_0.short_form_name,
        "form_version": "8.0",
        "form_type": FormType.PHS_FELLOWSHIP_SUPPLEMENTAL,
        "form_instruction_id": PHSFellowshipSupplemental_v8_0.form_instruction_id,
        "source_nodes": 165,
        "conditions": 43,
        "calculations": 2,
        "attachment_fields": 17,
        "unsupported_scalar_arrays": (
            "PHS_Fellowship_Supplemental_8_0.AdditionalInformation.StemCells.CellLines",
        ),
    }
    values.update(overrides)
    return SourceResolvedFormConfig(**values)


def test_phs_fellowship_is_a_complete_source_accounted_canary() -> None:
    form = PHSFellowshipSupplemental_v8_0
    assert form.form_type == FormType.PHS_FELLOWSHIP_SUPPLEMENTAL
    assert form.form_version == "8.0"
    assert form.short_form_name == "PHS_Fellowship_Supplemental_8_0"
    assert form.form_name.startswith("[Draft]")
    assert form.json_to_xml_schema is None
    assert len(_form_json._BUILD.condition_rule_ids) == 43
    assert len(_form_json._BUILD.calculation_rule_ids) == 2
    assert len(_form_json._BUILD.attachment_paths) == 17

    ui_nodes = list(_walk_ui(form.form_ui_schema))
    definitions = [node["definition"] for node in ui_nodes if "definition" in node]
    assert len(definitions) == len(set(definitions))
    assert len([node for node in ui_nodes if "conditional" in node]) == 28


def test_source_visibility_rules_are_native_conditional_ui() -> None:
    fields = _ui_by_definition()
    euthanasia = fields["/properties/OtherResearchTrainingPlan/properties/AreAnimalsEuthanized"]
    assert euthanasia["conditional"] == {
        "when": {
            "op": "equals",
            "ref": {
                "scope": "root",
                "pointer": "/OtherResearchTrainingPlan/VertebrateAnimalsUsed",
            },
            "value": "Y: Yes",
        },
        "then": {"visible": True},
        "otherwise": {"visible": False},
    }
    support_level = fields[
        "/properties/AdditionalInformation/properties/CurrentPriorNRSASupport/items/properties/Level"
    ]
    assert support_level["conditional"]["when"]["ref"] == {
        "scope": "root",
        "pointer": "/AdditionalInformation/CurrentPriorNRSASupportIndicator",
    }
    cell_lines = fields[
        "/properties/AdditionalInformation/properties/StemCells/properties/CellLines"
    ]
    assert cell_lines["type"] == "null"
    assert "conditional" in cell_lines


def test_source_requiredness_is_live_json_schema() -> None:
    validator = Draft202012Validator(PHSFellowshipSupplemental_v8_0.form_json_schema)
    animal_errors = list(
        validator.iter_errors({"OtherResearchTrainingPlan": {"VertebrateAnimalsUsed": "Y: Yes"}})
    )
    assert any("AreAnimalsEuthanized" in error.message for error in animal_errors)
    inactive_errors = list(
        validator.iter_errors({"OtherResearchTrainingPlan": {"VertebrateAnimalsUsed": "N: No"}})
    )
    assert not any("AreAnimalsEuthanized" in error.message for error in inactive_errors)
    salary_errors = list(
        validator.iter_errors({"Budget": {"InstitutionalBaseSalary": {"Amount": "100.00"}}})
    )
    messages = [error.message for error in salary_errors]
    assert any("AcademicPeriod" in message for message in messages)
    assert any("NumberOfMonths" in message for message in messages)


def test_exact_tuition_and_childcare_sums_execute() -> None:
    application_response = {
        "Budget": {
            "TuitionRequestedYear1": "100.00",
            "TuitionRequestedYear2": "25.50",
            "TuitionRequestedYear3": "0.50",
            "ChildcareRequestedYear1": "10.00",
            "ChildcareRequestedYear2": "2.25",
        }
    }
    application_form = SimpleNamespace(
        application_response=application_response,
        form=PHSFellowshipSupplemental_v8_0,
        application_form_id="draft-phs-fellowship-test",
        form_id=PHSFellowshipSupplemental_v8_0.form_id,
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
    assert context.json_data["Budget"]["TuitionRequestedTotal"] == "126.00"
    assert context.json_data["Budget"]["ChildcareRequestedTotal"] == "12.25"


def test_all_attachment_questions_use_native_attachment_contracts() -> None:
    form = PHSFellowshipSupplemental_v8_0
    appendix_items = form.form_json_schema["properties"]["Appendix"]["items"]
    assert appendix_items.get("$ref", "").endswith("#/attachment") or (
        appendix_items.get("type") == "string" and appendix_items.get("format") == "uuid"
    )
    fields = _ui_by_definition()
    assert fields["/properties/Appendix"]["widget"] == "Attachment"
    assert (
        fields[
            "/properties/AdditionalInformation/properties/ConcurrentSupportDescription/properties/attFile"
        ]["widget"]
        == "Attachment"
    )


def test_machine_readable_metadata_preserves_analysis_without_counting_outputs() -> None:
    metadata = PHSFellowshipSupplemental_v8_0.form_json_schema["x-simpler-field-metadata"]
    assert metadata["contract"] == "simpler-form-field-metadata/v1"
    assert metadata["counts"] == {
        "applicant_question": 47,
        "calculated_output": 2,
        "technical_field": 99,
        "static_content": 0,
        "attachment": 17,
        "total_records": 165,
    }
    tuition_total = next(
        record
        for record in metadata["records"]
        if record["runtime_data_pointer_template"] == "/Budget/TuitionRequestedTotal"
    )
    assert tuition_total["classification"] == "calculated_output"
    assert tuition_total["counts_as_applicant_question"] is False
    assert tuition_total["canonical_semantic_question_id"] == (
        "concept:fellowship-budget:tuition-requested-total"
    )
    assert tuition_total["semantic_mapping_status"] == "agent_proposed"
    assert tuition_total["xml"] == {
        "path": "PHS_Fellowship_Supplemental_8_0.Budget.TuitionRequestedTotal",
        "type": "globLib:BudgetTotalAmountDataType",
        "type_source": "xsd_declared_type",
        "xsd_url": "https://apply07.grants.gov/apply/forms/schemas/PHS_Fellowship_Supplemental_8_0-V8.0.xsd",
        "version": "sha256:85f8e33df4641c56f3b6b96108690f89d214de8b5c864b1d6bd1e6bf8c7cc7bc",
        "sha256": "85f8e33df4641c56f3b6b96108690f89d214de8b5c864b1d6bd1e6bf8c7cc7bc",
    }
    assert tuition_total["component_module_ids"] == ["semantic-domain-fellowship-budget"]
    assert tuition_total["runtime_behavior_links"] == [
        {
            "rule_id": "runtime-rule:sha256:e962c5b093f43d8b34840d119020855e4f1fec4671a5d71e22378228180d5a51",
            "mechanism": "calculation",
            "role": "target",
        }
    ]


def test_package_hashes_and_open_gates_are_explicit() -> None:
    manifest = json.loads((_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest["artifacts"].items():
        assert hashlib.sha256((_PACKAGE_DIR / name).read_bytes()).hexdigest() == expected_hash
    assert manifest["source_evidence"] == {
        "nodes": 165,
        "behavior_records": 120,
        "resolved_runtime_rules": 45,
        "conditions": 43,
        "calculations": 2,
        "attachments": 17,
        "form_xsd": {
            "source_ref": "https://apply07.grants.gov/apply/forms/schemas/PHS_Fellowship_Supplemental_8_0-V8.0.xsd",
            "sha256": "85f8e33df4641c56f3b6b96108690f89d214de8b5c864b1d6bd1e6bf8c7cc7bc",
        },
        "behavior_workbook": {
            "source_ref": "https://apply07.grants.gov/apply/forms/sample/PHS_Fellowship_Supplemental_8_0-V8.0_F836.xls",
            "sha256": "fe9c42a0ec7008f6d9076e250bb37243629a71403331b69afcbf1069929f8beb",
        },
    }
    assert manifest["review_boundary"]["published_coverage_eligible"] is False
    assert manifest["review_boundary"]["production_ready"] is False
    assert manifest["open_gates"]["scalar_string_arrays"] == [
        "PHS_Fellowship_Supplemental_8_0.AdditionalInformation.StemCells.CellLines"
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_nodes", 164),
        ("conditions", 42),
        ("calculations", 1),
        ("attachment_fields", 16),
    ],
)
def test_builder_fails_closed_on_source_accounting_drift(field: str, value: int) -> None:
    with pytest.raises(SourceResolvedFormError):
        build_source_resolved_form(_PACKAGE_DIR, _config(**{field: value}))
