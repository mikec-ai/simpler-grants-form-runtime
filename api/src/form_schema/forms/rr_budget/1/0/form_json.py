import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from src.constants.lookup_constants import FormType
from src.db.models.competition_models import Form
from src.form_schema.components.schema_field_list import build_schema_field_list
from src.form_schema.forms.rr_budget.behaviors import (
    compile_source_resolved_sum_rules,
    normalize_source_decimal_fields,
)
from src.form_schema.forms.rr_budget.config import FORM_ID, SHORT_FORM_NAME
from src.form_schema.shared import COMMON_SHARED_V1

_PACKAGE_DIR = Path(__file__).with_name("draft_package")


def _load_package() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = json.loads((_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("contract") != "simpler-rr-budget-draft-package/v1":
        raise ValueError("Unsupported R&R Budget draft package")
    boundary = manifest.get("review_boundary", {})
    if boundary.get("published_coverage_eligible") is not False:
        raise ValueError("The R&R Budget draft cannot be coverage eligible")
    if boundary.get("production_ready") is not False:
        raise ValueError("The R&R Budget draft cannot claim production readiness")

    artifacts: dict[str, dict[str, Any]] = {}
    for name, expected_hash in manifest["artifacts"].items():
        artifact_bytes = (_PACKAGE_DIR / name).read_bytes()
        if hashlib.sha256(artifact_bytes).hexdigest() != expected_hash:
            raise ValueError(f"R&R Budget artifact hash mismatch: {name}")
        artifacts[name] = json.loads(artifact_bytes)
    return manifest, artifacts["candidate.json"], artifacts["runtime-rules.json"]


def _resolve_pointer(schema: dict[str, Any], pointer: str) -> dict[str, Any]:
    current: Any = schema
    for token in pointer.removeprefix("/").split("/"):
        if not isinstance(current, dict) or token not in current:
            raise ValueError(f"R&R Budget schema pointer does not resolve: {pointer}")
        current = current[token]
    if not isinstance(current, dict):
        raise ValueError(f"R&R Budget schema pointer is not an object: {pointer}")
    return current


def _attachment_schema(schema: dict[str, Any], pointer: str) -> None:
    node = _resolve_pointer(schema, pointer)
    source_metadata = {key: value for key, value in node.items() if key.startswith("x-")}
    title = node.get("title")
    node.clear()
    node.update(source_metadata)
    node["allOf"] = [{"$ref": COMMON_SHARED_V1.field_ref("attachment")}]
    if title:
        node["title"] = title


_MANIFEST, _CANDIDATE, _RUNTIME_RULES = _load_package()
FORM_JSON_SCHEMA = _CANDIDATE["artifacts"]["json_schema"]
if normalize_source_decimal_fields(FORM_JSON_SCHEMA) != 115:
    raise ValueError("R&R Budget decimal-field count drift")

FORM_RULE_SCHEMA, _COMPILED_RULE_IDS = compile_source_resolved_sum_rules(
    FORM_JSON_SCHEMA, _RUNTIME_RULES
)
if len(_COMPILED_RULE_IDS) != _MANIFEST["source_evidence"]["executable_source_resolved_sums"]:
    raise ValueError("R&R Budget compiled calculation count drift")

_PERIOD_DEFINITION = "/properties/budget_year"
_PERIOD_ATTACHMENTS = frozenset(
    {
        "/properties/budget_year/items/properties/key_persons/properties/attached_key_persons",
        "/properties/budget_year/items/properties/equipment/properties/additional_equipments_attachment",
    }
)
_period = build_schema_field_list(
    FORM_JSON_SCHEMA["properties"]["budget_year"],
    definition=_PERIOD_DEFINITION,
    name="budget_year",
    label="Budget Period",
    attachment_definitions=_PERIOD_ATTACHMENTS,
)

FORM_UI_SCHEMA = _CANDIDATE["artifacts"]["ui_schema"]
FORM_UI_SCHEMA[1]["children"] = [_period.ui_schema]
for section in (FORM_UI_SCHEMA[0], FORM_UI_SCHEMA[2]):
    for field in section["children"]:
        node = _resolve_pointer(FORM_JSON_SCHEMA, field["definition"])
        if node.get("readOnly") is True:
            field["type"] = "null"
        if field["definition"] == "/properties/budget_justification_attachment":
            field["widget"] = "Attachment"

for pointer in (
    "/properties/budget_justification_attachment",
    *_PERIOD_ATTACHMENTS,
):
    _attachment_schema(FORM_JSON_SCHEMA, pointer)

_budget_year_rules = FORM_RULE_SCHEMA.setdefault("budget_year", {})
_budget_year_rules["gg_type"] = "array"
_budget_year_rules.setdefault("key_persons", {})["attached_key_persons"] = {
    "gg_validation": {"rule": "attachment"}
}
_budget_year_rules.setdefault("equipment", {})["additional_equipments_attachment"] = {
    "gg_validation": {"rule": "attachment"}
}
FORM_RULE_SCHEMA["budget_justification_attachment"] = {"gg_validation": {"rule": "attachment"}}

FORM_XML_TRANSFORM_RULES = None

RRBudget_v3_0 = Form(
    form_id=FORM_ID,
    legacy_form_id=None,
    form_name="[Draft] Research & Related Budget",
    short_form_name=SHORT_FORM_NAME,
    form_version="3.0",
    agency_code="GRANTS_GOV",
    form_json_schema=FORM_JSON_SCHEMA,
    form_ui_schema=FORM_UI_SCHEMA,
    form_rule_schema=FORM_RULE_SCHEMA,
    json_to_xml_schema=FORM_XML_TRANSFORM_RULES,
    form_type=FormType.RR_BUDGET,
    form_instruction_id=uuid.UUID("6c604b81-8582-4d39-b899-f3e15bbcd3ef"),
    is_deprecated=False,
)

del _CANDIDATE, _RUNTIME_RULES, _MANIFEST, _period, _budget_year_rules
