"""Native, source-pinned composition for the R&R Budget form family."""

from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.constants.lookup_constants import FormType
from src.db.models.competition_models import Form
from src.form_schema.components.schema_field_list import build_schema_field_list
from src.form_schema.shared import COMMON_SHARED_V1


class BudgetFamilyError(ValueError):
    """Raised when a source-pinned budget profile cannot be composed exactly."""


@dataclass(frozen=True)
class BudgetFamilyConfig:
    """Explicit product metadata and source-accounting gates for one budget profile."""

    source_form_id: str
    form_id: uuid.UUID
    form_name: str
    short_form_name: str
    form_version: str
    form_type: FormType
    form_instruction_id: uuid.UUID
    budget_periods: int
    countable_questions: int
    decimal_fields: int = 115
    repeating_groups: int = 5
    source_calculations: int = 56
    executable_sums: int = 30


@dataclass(frozen=True)
class BudgetFamilyBuild:
    """Resolved native form plus source-accounting results."""

    form: Form
    manifest: dict[str, Any]
    compiled_rule_ids: tuple[str, ...]


_DECIMAL_PATTERN = r"^-?(?:\d{1,14}|\d{1,13}[.]\d|\d{1,12}[.]\d{2})$"
_PERIOD_DEFINITION = "/properties/budget_year"
_PERIOD_ATTACHMENTS = frozenset(
    {
        "/properties/budget_year/items/properties/key_persons/properties/attached_key_persons",
        "/properties/budget_year/items/properties/equipment/properties/additional_equipments_attachment",
    }
)


def normalize_source_decimal_fields(schema: dict[str, Any]) -> int:
    """Represent XSD decimal values as strings without floating-point loss."""

    count = 0

    def visit(node: object) -> None:
        nonlocal count
        if isinstance(node, dict):
            if node.get("type") == "number":
                node["type"] = "string"
                node["pattern"] = _DECIMAL_PATTERN
                node["minLength"] = 1
                node["maxLength"] = 16
                count += 1
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    return count


def _source_path_index(schema: dict[str, Any]) -> dict[str, tuple[tuple[str, bool], ...]]:
    result: dict[str, tuple[tuple[str, bool], ...]] = {}

    def visit(node: dict[str, Any], path: tuple[tuple[str, bool], ...]) -> None:
        source_path = node.get("x-source-path")
        if isinstance(source_path, str):
            if source_path in result:
                raise BudgetFamilyError(f"Duplicate source path: {source_path}")
            result[source_path] = path
        if node.get("type") == "object":
            for name, child in node.get("properties", {}).items():
                visit(child, path + ((name, False),))
        elif node.get("type") == "array":
            items = node.get("items")
            if not isinstance(items, dict):
                raise BudgetFamilyError(f"Array has no item schema: {source_path}")
            if not path:
                raise BudgetFamilyError("Root arrays are not supported")
            array_path = path[:-1] + ((path[-1][0], True),)
            visit(items, array_path)

    visit(schema, ())
    return result


def _dotted(path: tuple[tuple[str, bool], ...]) -> str:
    return ".".join(f"{name}[*]" if repeated else name for name, repeated in path)


def compile_source_resolved_sum_rules(
    schema: dict[str, Any], runtime_ast: dict[str, Any], *, expected_count: int = 30
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Compile only exact, source-resolved sums into Simpler's native dialect."""

    if runtime_ast.get("contract") != "source-bound-runtime-rule-ast/resolved-v1":
        raise BudgetFamilyError("Unsupported budget runtime-rule contract")
    index = _source_path_index(schema)
    rule_schema: dict[str, Any] = {}
    compiled_ids: list[str] = []

    for rule in runtime_ast.get("rules", []):
        if rule.get("mechanism") != "calculation" or rule.get("execution_class") != "executable":
            continue
        if (
            rule.get("disposition") != "working"
            or rule.get("operator") != "sum"
            or rule.get("unresolved_references") != []
        ):
            raise BudgetFamilyError(f"Unsupported executable rule: {rule.get('rule_id')}")

        target_source = rule["target"]["path"]
        target_path = index.get(target_source)
        if target_path is None:
            raise BudgetFamilyError(f"Unknown calculation target: {target_source}")
        target_parent_source = target_source.rsplit(".", 1)[0]
        target_parent_path = target_path[:-1]
        fields: list[str] = []
        for operand in rule["operands"]:
            operand_source = operand["path"]
            operand_path = index.get(operand_source)
            if operand_path is None:
                raise BudgetFamilyError(f"Unknown calculation operand: {operand_source}")
            if rule.get("instance_scope") == "same_instance":
                if not operand_source.startswith(f"{target_parent_source}."):
                    raise BudgetFamilyError(
                        f"Same-instance operand escapes target parent: {operand_source}"
                    )
                if operand_path[: len(target_parent_path)] != target_parent_path:
                    raise BudgetFamilyError(f"Runtime path drift: {operand_source}")
                relative = operand_path[len(target_parent_path) :]
                fields.append(f"@THIS.{_dotted(relative)}")
            elif rule.get("instance_scope") == "all_budget_periods":
                fields.append(_dotted(operand_path))
            else:
                raise BudgetFamilyError(
                    f"Unsupported calculation scope: {rule.get('instance_scope')}"
                )

        current = rule_schema
        for name, repeated in target_path[:-1]:
            current = current.setdefault(name, {})
            if repeated:
                current["gg_type"] = "array"
        leaf = target_path[-1]
        if leaf[1] or leaf[0] in current:
            raise BudgetFamilyError(f"Duplicate or array calculation target: {target_source}")
        current[leaf[0]] = {
            "gg_pre_population": {
                "rule": "sum_monetary",
                "fields": fields,
                "order": rule["source_index"] + 1,
            }
        }
        compiled_ids.append(rule["rule_id"])

    if len(compiled_ids) != expected_count:
        raise BudgetFamilyError(
            f"Expected {expected_count} executable sums, got {len(compiled_ids)}"
        )
    return rule_schema, tuple(compiled_ids)


def _resolve_pointer(schema: dict[str, Any], pointer: str) -> dict[str, Any]:
    current: Any = schema
    for token in pointer.removeprefix("/").split("/"):
        if not isinstance(current, dict) or token not in current:
            raise BudgetFamilyError(f"Budget schema pointer does not resolve: {pointer}")
        current = current[token]
    if not isinstance(current, dict):
        raise BudgetFamilyError(f"Budget schema pointer is not an object: {pointer}")
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


def _load_package(
    package_dir: Path, config: BudgetFamilyConfig
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("contract") != "simpler-budget-family-draft-package/v1":
        raise BudgetFamilyError("Unsupported budget-family draft package")
    form_identity = manifest.get("form", {})
    if form_identity.get("form_id") != config.source_form_id:
        raise BudgetFamilyError("Budget-family package identity drift")
    if form_identity.get("form_version") != config.form_version:
        raise BudgetFamilyError("Budget-family package version drift")
    boundary = manifest.get("review_boundary", {})
    if boundary.get("published_coverage_eligible") is not False:
        raise BudgetFamilyError("Budget-family draft cannot be coverage eligible")
    if boundary.get("production_ready") is not False:
        raise BudgetFamilyError("Budget-family draft cannot claim production readiness")

    artifacts: dict[str, dict[str, Any]] = {}
    for name, expected_hash in manifest["artifacts"].items():
        artifact_bytes = (package_dir / name).read_bytes()
        if hashlib.sha256(artifact_bytes).hexdigest() != expected_hash:
            raise BudgetFamilyError(f"Budget-family artifact hash mismatch: {name}")
        artifacts[name] = json.loads(artifact_bytes)
    candidate = artifacts["candidate.json"]
    runtime_rules = artifacts["runtime-rules.json"]
    if candidate.get("metadata", {}).get("form_id") != config.source_form_id:
        raise BudgetFamilyError("Budget-family candidate identity drift")
    if runtime_rules.get("form_id") != config.source_form_id:
        raise BudgetFamilyError("Budget-family runtime identity drift")
    source_versions = candidate.get("provenance", {}).get("source_versions")
    expected_source_version = manifest.get("source_evidence", {}).get("contract_source_version")
    if source_versions != [expected_source_version]:
        raise BudgetFamilyError("Budget-family source-version drift")
    return manifest, candidate, runtime_rules


def build_budget_family_form(package_dir: Path, config: BudgetFamilyConfig) -> BudgetFamilyBuild:
    """Resolve one budget-family profile into Simpler's native form contract."""

    manifest, candidate, runtime_rules = _load_package(package_dir, config)
    evidence = manifest.get("source_evidence", {})
    expected_evidence = {
        "countable_questions": config.countable_questions,
        "decimal_fields": config.decimal_fields,
        "repeating_groups": config.repeating_groups,
        "source_calculations": config.source_calculations,
        "executable_source_resolved_sums": config.executable_sums,
        "blocked_calculations": config.source_calculations - config.executable_sums,
    }
    for key, value in expected_evidence.items():
        if evidence.get(key) != value:
            raise BudgetFamilyError(f"Budget-family source accounting drift: {key}")

    schema = deepcopy(candidate["artifacts"]["json_schema"])
    if normalize_source_decimal_fields(schema) != config.decimal_fields:
        raise BudgetFamilyError("Budget-family decimal-field count drift")
    period_schema = schema.get("properties", {}).get("budget_year", {})
    if period_schema.get("maxItems") != config.budget_periods:
        raise BudgetFamilyError("Budget-family period parameter drift")

    rule_schema, compiled_rule_ids = compile_source_resolved_sum_rules(
        schema, runtime_rules, expected_count=config.executable_sums
    )
    period = build_schema_field_list(
        period_schema,
        definition=_PERIOD_DEFINITION,
        name="budget_year",
        label="Budget Period",
        attachment_definitions=_PERIOD_ATTACHMENTS,
    )

    ui_schema = deepcopy(candidate["artifacts"]["ui_schema"])
    ui_schema[1]["children"] = [period.ui_schema]
    for section in (ui_schema[0], ui_schema[2]):
        for field in section["children"]:
            node = _resolve_pointer(schema, field["definition"])
            if node.get("readOnly") is True:
                field["type"] = "null"
            if field["definition"] == "/properties/budget_justification_attachment":
                field["widget"] = "Attachment"

    for pointer in ("/properties/budget_justification_attachment", *_PERIOD_ATTACHMENTS):
        _attachment_schema(schema, pointer)

    budget_year_rules = rule_schema.setdefault("budget_year", {})
    budget_year_rules["gg_type"] = "array"
    budget_year_rules.setdefault("key_persons", {})["attached_key_persons"] = {
        "gg_validation": {"rule": "attachment"}
    }
    budget_year_rules.setdefault("equipment", {})["additional_equipments_attachment"] = {
        "gg_validation": {"rule": "attachment"}
    }
    rule_schema["budget_justification_attachment"] = {"gg_validation": {"rule": "attachment"}}

    form = Form(
        form_id=config.form_id,
        legacy_form_id=None,
        form_name=config.form_name,
        short_form_name=config.short_form_name,
        form_version=config.form_version,
        agency_code="GRANTS_GOV",
        form_json_schema=schema,
        form_ui_schema=ui_schema,
        form_rule_schema=rule_schema,
        json_to_xml_schema=None,
        form_type=config.form_type,
        form_instruction_id=config.form_instruction_id,
        is_deprecated=False,
    )
    return BudgetFamilyBuild(
        form=form,
        manifest=deepcopy(manifest),
        compiled_rule_ids=compiled_rule_ids,
    )
