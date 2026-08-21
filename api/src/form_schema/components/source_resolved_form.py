"""Fail-closed projection of source-resolved form evidence into native Simpler artifacts."""

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


class SourceResolvedFormError(ValueError):
    """Raised when pinned source evidence cannot be projected exactly."""


@dataclass(frozen=True)
class SourceResolvedFormConfig:
    source_form_id: str
    form_id: uuid.UUID
    form_name: str
    short_form_name: str
    form_version: str
    form_type: FormType
    form_instruction_id: uuid.UUID
    source_nodes: int
    conditions: int
    calculations: int
    attachment_fields: int
    unsupported_scalar_arrays: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceResolvedFormBuild:
    form: Form
    manifest: dict[str, Any]
    condition_rule_ids: tuple[str, ...]
    calculation_rule_ids: tuple[str, ...]
    attachment_paths: tuple[str, ...]
    field_metadata: dict[str, Any]


RuntimePath = tuple[tuple[str, bool], ...]


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SourceResolvedFormError(f"Expected a JSON object: {path.name}")
    return value


def _load_package(
    package_dir: Path, config: SourceResolvedFormConfig
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = _load_json(package_dir / "manifest.json")
    if manifest.get("contract") != "simpler-source-resolved-form-package/v1":
        raise SourceResolvedFormError("Unsupported source-resolved form package")
    if manifest.get("form") != {
        "form_id": config.source_form_id,
        "form_version": config.form_version,
    }:
        raise SourceResolvedFormError("Source-resolved package identity drift")
    boundary = manifest.get("review_boundary", {})
    if boundary.get("published_coverage_eligible") is not False:
        raise SourceResolvedFormError("Draft source evidence cannot be coverage eligible")
    if boundary.get("production_ready") is not False:
        raise SourceResolvedFormError("Draft source evidence cannot claim production readiness")

    artifacts: dict[str, dict[str, Any]] = {}
    for name, expected_hash in manifest.get("artifacts", {}).items():
        artifact_path = package_dir / name
        artifact_bytes = artifact_path.read_bytes()
        if hashlib.sha256(artifact_bytes).hexdigest() != expected_hash:
            raise SourceResolvedFormError(f"Source artifact hash mismatch: {name}")
        artifacts[name] = json.loads(artifact_bytes)
    if set(artifacts) != {"schema.json", "runtime-rules.json", "portable-schema.json"}:
        raise SourceResolvedFormError("Source-resolved package artifact set drift")
    schema = artifacts["schema.json"]
    runtime = artifacts["runtime-rules.json"]
    portable = artifacts["portable-schema.json"]
    if runtime.get("form_id") != config.source_form_id:
        raise SourceResolvedFormError("Runtime-rule identity drift")
    if runtime.get("contract") != "source-bound-runtime-rule-ast/resolved-v1":
        raise SourceResolvedFormError("Unsupported runtime-rule contract")
    if portable.get("form_id") != config.source_form_id:
        raise SourceResolvedFormError("Portable-metadata identity drift")
    if len(portable.get("nodes", [])) != config.source_nodes:
        raise SourceResolvedFormError("Portable-metadata node accounting drift")
    return manifest, schema, runtime, portable


def _source_path(node: dict[str, Any]) -> str | None:
    authoring = node.get("x-authoring")
    if isinstance(authoring, dict) and isinstance(authoring.get("source_path"), str):
        return authoring["source_path"]
    return None


def _source_path_index(schema: dict[str, Any]) -> dict[str, RuntimePath]:
    result: dict[str, RuntimePath] = {}

    def visit(node: dict[str, Any], path: RuntimePath) -> None:
        source_path = _source_path(node)
        if (
            source_path is None
            and node.get("type") == "array"
            and isinstance(node.get("items"), dict)
        ):
            source_path = _source_path(node["items"])
        if source_path is not None:
            previous = result.get(source_path)
            # Scalar array items repeat the container's source identity. The
            # container is the authored question and remains the runtime target.
            if previous is None:
                result[source_path] = path
            elif not (path and path[-1][1] and previous == path[:-1] + ((path[-1][0], False),)):
                raise SourceResolvedFormError(f"Duplicate source path: {source_path}")
        node_type = node.get("type")
        if node_type == "object":
            properties = node.get("properties")
            if not isinstance(properties, dict):
                raise SourceResolvedFormError(f"Object has no properties: {source_path}")
            for name, child in properties.items():
                if not isinstance(child, dict):
                    raise SourceResolvedFormError(f"Invalid schema property: {name}")
                visit(child, path + ((name, False),))
        elif node_type == "array":
            items = node.get("items")
            if not isinstance(items, dict) or not path:
                raise SourceResolvedFormError(f"Array has no item schema: {source_path}")
            visit(items, path[:-1] + ((path[-1][0], True),))

    visit(schema, ())
    return result


def _pointer(path: RuntimePath, *, include_arrays: bool = False) -> str:
    tokens: list[str] = []
    for name, repeated in path:
        tokens.append(name.replace("~", "~0").replace("/", "~1"))
        if repeated and include_arrays:
            tokens.append("items")
    return "/" + "/".join(tokens)


def _schema_pointer(path: RuntimePath) -> str:
    parts: list[str] = []
    for name, repeated in path:
        parts.extend(("properties", name))
        if repeated:
            parts.append("items")
    return "/" + "/".join(parts)


def _data_pointer_template(path: RuntimePath) -> str:
    parts: list[str] = []
    for name, repeated in path:
        parts.append(name.replace("~", "~0").replace("/", "~1"))
        if repeated:
            parts.append("*")
    return "/" + "/".join(parts)


def _schema_at_runtime_path(schema: dict[str, Any], path: RuntimePath) -> dict[str, Any]:
    current = schema
    for name, repeated in path:
        properties = current.get("properties")
        if not isinstance(properties, dict) or not isinstance(properties.get(name), dict):
            raise SourceResolvedFormError(f"Schema path does not resolve: {_pointer(path)}")
        current = properties[name]
        if repeated:
            items = current.get("items")
            if not isinstance(items, dict):
                raise SourceResolvedFormError(f"Array has no item schema: {_pointer(path)}")
            current = items
    return current


def _condition_value(schema: dict[str, Any], dependency: RuntimePath, value: object) -> object:
    """Reconcile workbook labels to the exact XSD enum value without guessing."""

    node = _schema_at_runtime_path(schema, dependency)
    enum = node.get("enum")
    if not isinstance(enum, list) or value in enum:
        return value
    if isinstance(value, str):
        matches = [candidate for candidate in enum if candidate.endswith(f": {value}")]
        if len(matches) == 1:
            return matches[0]
    raise SourceResolvedFormError(
        f"Condition value {value!r} is not an exact or uniquely qualified schema enum"
    )


def _assert_rule_boundary(rule: dict[str, Any]) -> None:
    if (
        rule.get("execution_class") != "executable"
        or rule.get("disposition") != "working"
        or rule.get("unresolved_references") != []
    ):
        raise SourceResolvedFormError(f"Rule is not executable: {rule.get('rule_id')}")
    target = rule.get("target", {})
    if target.get("path_resolved") is not True or target.get("resolution_scope") != "local_form":
        raise SourceResolvedFormError(f"Rule target is not locally resolved: {rule.get('rule_id')}")
    for entry in [*rule.get("dependencies", []), *rule.get("operands", [])]:
        if entry.get("path_resolved") is not True or entry.get("resolution_scope") != "local_form":
            raise SourceResolvedFormError(
                f"Rule input is not locally resolved: {rule.get('rule_id')}"
            )


def _relative_names(path: RuntimePath, prefix: RuntimePath) -> tuple[str, ...]:
    if path[: len(prefix)] != prefix or any(repeated for _, repeated in path[len(prefix) :]):
        raise SourceResolvedFormError("Conditional projection cannot cross an array boundary")
    return tuple(name for name, _ in path[len(prefix) :])


def _common_object_path(paths: list[RuntimePath]) -> RuntimePath:
    if not paths:
        return ()
    length = min(len(path) for path in paths)
    index = 0
    while index < length and len({path[index] for path in paths}) == 1:
        index += 1
    prefix = paths[0][:index]
    if prefix and prefix[-1][1]:
        raise SourceResolvedFormError(
            "Conditional projection inside repeated instances is unsupported"
        )
    return prefix


def _nested_required(names: tuple[str, ...]) -> dict[str, Any]:
    if not names:
        raise SourceResolvedFormError("Required target cannot be an object root")
    if len(names) == 1:
        return {"required": [names[0]]}
    return {
        "properties": {names[0]: _nested_required(names[1:])},
        "required": [names[0]],
    }


def _nested_equals(names: tuple[str, ...], value: object) -> dict[str, Any]:
    if not names:
        raise SourceResolvedFormError("Equals dependency cannot be an object root")
    if len(names) == 1:
        return {"properties": {names[0]: {"const": value}}, "required": [names[0]]}
    return {
        "properties": {names[0]: _nested_equals(names[1:], value)},
        "required": [names[0]],
    }


def _compile_required_condition(
    schema: dict[str, Any], index: dict[str, RuntimePath], rule: dict[str, Any]
) -> None:
    operator = rule.get("operator")
    if operator not in {"equals", "present", "any_present"}:
        raise SourceResolvedFormError(f"Unsupported required operator: {operator}")
    target_source = rule["target"]["path"]
    dependency_sources = [entry["path"] for entry in rule.get("dependencies", [])]
    target = index.get(target_source)
    dependencies = [index.get(source) for source in dependency_sources]
    if target is None or any(path is None for path in dependencies):
        raise SourceResolvedFormError(f"Unknown required-condition path: {rule.get('rule_id')}")
    typed_dependencies = [path for path in dependencies if path is not None]
    if not typed_dependencies:
        raise SourceResolvedFormError(
            f"Required condition has no dependencies: {rule.get('rule_id')}"
        )
    source_value = rule.get("source_value", {})
    if (
        source_value.get("target_path") != target_source
        or source_value.get("dependency_paths") != dependency_sources
        or source_value.get("operator") != operator
        or source_value.get("effect") != "required"
    ):
        raise SourceResolvedFormError(f"Required condition evidence drift: {rule.get('rule_id')}")

    common = _common_object_path([target, *typed_dependencies])
    target_names = _relative_names(target, common)
    dependency_names = [_relative_names(path, common) for path in typed_dependencies]
    if operator == "equals":
        if len(dependency_names) != 1 or source_value.get("value") != rule.get("value"):
            raise SourceResolvedFormError(f"Equals condition evidence drift: {rule.get('rule_id')}")
        runtime_value = _condition_value(schema, typed_dependencies[0], rule["value"])
        predicate = _nested_equals(dependency_names[0], runtime_value)
    elif operator == "present":
        if len(dependency_names) != 1:
            raise SourceResolvedFormError("Present conditions require one dependency")
        predicate = _nested_required(dependency_names[0])
    else:
        predicate = {"anyOf": [_nested_required(names) for names in dependency_names]}
    predicate["$comment"] = f"Source runtime rule {rule['rule_id']}"
    parent = _schema_at_runtime_path(schema, common)
    parent.setdefault("allOf", []).append({"if": predicate, "then": _nested_required(target_names)})


def _compile_calculation(
    schema: dict[str, Any],
    rule_schema: dict[str, Any],
    index: dict[str, RuntimePath],
    rule: dict[str, Any],
) -> None:
    if rule.get("operator") != "sum" or rule.get("instance_scope") != "same_instance":
        raise SourceResolvedFormError(f"Unsupported calculation: {rule.get('rule_id')}")
    target_source = rule["target"]["path"]
    operand_sources = [entry["path"] for entry in rule.get("operands", [])]
    target = index.get(target_source)
    operands = [index.get(source) for source in operand_sources]
    if target is None or any(path is None for path in operands) or not operands:
        raise SourceResolvedFormError(f"Unknown calculation path: {rule.get('rule_id')}")
    source_value = rule.get("source_value", {})
    if (
        source_value.get("target_path") != target_source
        or source_value.get("operand_paths") != operand_sources
        or source_value.get("operator") != "sum"
        or source_value.get("instance_scope") != "same_instance"
    ):
        raise SourceResolvedFormError(f"Calculation evidence drift: {rule.get('rule_id')}")
    parent = target[:-1]
    if any(path is None or path[:-1] != parent for path in operands):
        raise SourceResolvedFormError("Same-instance sum inputs must share the target object")
    for path in [target, *[path for path in operands if path is not None]]:
        node = _schema_at_runtime_path(schema, path)
        if node.get("type") != "number":
            raise SourceResolvedFormError(f"Calculation input is not numeric: {_pointer(path)}")
        minimum = node.pop("minimum", None)
        maximum = node.pop("maximum", None)
        node["type"] = "string"
        node["pattern"] = r"^-?(?:\d+|\d+[.]\d{1,2})$"
        node["x-source-number-bounds"] = {"minimum": minimum, "maximum": maximum}
    _schema_at_runtime_path(schema, target)["readOnly"] = True

    current = rule_schema
    for name, repeated in target[:-1]:
        current = current.setdefault(name, {})
        if repeated:
            current["gg_type"] = "array"
    current[target[-1][0]] = {
        "gg_pre_population": {
            "rule": "sum_monetary",
            "fields": [f"@THIS.{path[-1][0]}" for path in operands if path is not None],
            "order": rule["source_index"] + 1,
        }
    }


def _attachment_schema(node: dict[str, Any]) -> None:
    metadata = {key: value for key, value in node.items() if key.startswith("x-")}
    title = node.get("title")
    node.clear()
    node.update(metadata)
    node["allOf"] = [{"$ref": COMMON_SHARED_V1.field_ref("attachment")}]
    node["format"] = "attachment"
    if title:
        node["title"] = title


def _compile_attachments(schema: dict[str, Any], rule_schema: dict[str, Any]) -> tuple[str, ...]:
    paths: list[str] = []

    def visit(node: dict[str, Any], path: RuntimePath) -> None:
        if node.get("type") == "array":
            items = node.get("items")
            if isinstance(items, dict) and items.get("format") == "attachment":
                metadata = {key: value for key, value in items.items() if key.startswith("x-")}
                items.clear()
                items.update(metadata)
                items.update({"$ref": COMMON_SHARED_V1.field_ref("attachment")})
                paths.append(_pointer(path))
                _set_attachment_rule(rule_schema, path, is_array=True)
                return
            if isinstance(items, dict):
                visit(items, path[:-1] + ((path[-1][0], True),))
            return
        if node.get("format") == "attachment":
            _attachment_schema(node)
            paths.append(_pointer(path))
            _set_attachment_rule(rule_schema, path, is_array=False)
            return
        for name, child in node.get("properties", {}).items():
            if isinstance(child, dict):
                visit(child, path + ((name, False),))

    visit(schema, ())
    return tuple(paths)


def _set_attachment_rule(rule_schema: dict[str, Any], path: RuntimePath, *, is_array: bool) -> None:
    current = rule_schema
    for name, repeated in path[:-1]:
        current = current.setdefault(name, {})
        if repeated:
            current["gg_type"] = "array"
    leaf = path[-1][0]
    if leaf in current:
        raise SourceResolvedFormError(f"Attachment rule collides at {_pointer(path)}")
    current[leaf] = {"gg_validation": {"rule": "attachment"}}
    if is_array:
        current[leaf]["gg_type"] = "array"


def _build_ui(
    schema: dict[str, Any],
    visibility_rules: dict[str, dict[str, Any]],
    unsupported_scalar_arrays: frozenset[str],
) -> list[dict[str, Any]]:
    source_to_node: dict[str, dict[str, Any]] = {}

    def field(node: dict[str, Any], pointer: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": "null" if node.get("readOnly") is True else "field",
            "definition": pointer,
        }
        if node.get("format") == "attachment" or (
            node.get("type") == "array"
            and isinstance(node.get("items"), dict)
            and (node["items"].get("format") == "attachment" or "$ref" in node["items"])
        ):
            result["widget"] = "Attachment"
        source_path = _source_path(node)
        if (
            source_path is None
            and node.get("type") == "array"
            and isinstance(node.get("items"), dict)
        ):
            source_path = _source_path(node["items"])
        if source_path is not None:
            source_to_node[source_path] = result
        return result

    def object_children(
        node: dict[str, Any], pointer: str, *, in_list: bool
    ) -> list[dict[str, Any]]:
        children: list[dict[str, Any]] = []
        for name, child in node.get("properties", {}).items():
            child_pointer = f"{pointer}/properties/{name}"
            child_type = child.get("type")
            if child_type == "object":
                nested = object_children(child, child_pointer, in_list=in_list)
                if in_list:
                    children.extend(nested)
                else:
                    children.append({
                        "type": "section",
                        "name": child_pointer.replace("/properties/", "-").strip("/"),
                        "label": child.get("title") or name,
                        "children": nested,
                    })
            elif child_type == "array" and isinstance(child.get("items"), dict):
                if child["items"].get("type") == "object":
                    definition = build_schema_field_list(
                        child,
                        definition=child_pointer,
                        name=name,
                        label=child.get("title") or name,
                    )
                    list_node = definition.ui_schema
                    source_path = _source_path(child)
                    if source_path is not None:
                        source_to_node[source_path] = list_node
                    for list_child in list_node["children"]:
                        definition_pointer = list_child.get("definition")
                        if isinstance(definition_pointer, str):
                            schema_node = _resolve_schema_pointer(schema, definition_pointer)
                            item_source = _source_path(schema_node)
                            if item_source is not None:
                                source_to_node[item_source] = list_child
                    children.append(list_node)
                else:
                    source_path = _source_path(child) or _source_path(child["items"])
                    result = field(child, child_pointer)
                    if source_path in unsupported_scalar_arrays:
                        result["type"] = "null"
                    children.append(result)
            else:
                children.append(field(child, child_pointer))
        return children

    ui = object_children(schema, "", in_list=False)
    for source_path, conditional in visibility_rules.items():
        target = source_to_node.get(source_path)
        if target is None:
            raise SourceResolvedFormError(f"Visibility target is not rendered: {source_path}")
        if "conditional" in target and target["conditional"] != conditional:
            raise SourceResolvedFormError(f"Conflicting visibility rules: {source_path}")
        target["conditional"] = conditional
    return ui


def _resolve_schema_pointer(schema: dict[str, Any], pointer: str) -> dict[str, Any]:
    current: Any = schema
    for token in pointer.removeprefix("/").split("/"):
        if not isinstance(current, dict) or token not in current:
            raise SourceResolvedFormError(f"UI pointer does not resolve: {pointer}")
        current = current[token]
    if not isinstance(current, dict):
        raise SourceResolvedFormError(f"UI pointer is not an object: {pointer}")
    return current


def _build_field_metadata(
    portable: dict[str, Any],
    runtime: dict[str, Any],
    source_index: dict[str, RuntimePath],
    attachment_paths: tuple[str, ...],
) -> dict[str, Any]:
    """Preserve analysis metadata and keep applicant-question counts honest."""

    calculation_targets = {
        rule["target"]["path"]
        for rule in runtime["rules"]
        if rule.get("mechanism") == "calculation"
    }
    attachment_runtime_paths = set(attachment_paths)
    rule_links: dict[str, list[dict[str, str]]] = {}
    for rule in runtime["rules"]:
        rule_id = rule["rule_id"]
        for role, entries in (
            ("target", [rule["target"]]),
            ("dependency", rule.get("dependencies", [])),
            ("operand", rule.get("operands", [])),
        ):
            for entry in entries:
                rule_links.setdefault(entry["path"], []).append({
                    "rule_id": rule_id,
                    "mechanism": rule["mechanism"],
                    "role": role,
                })

    records: list[dict[str, Any]] = []
    counts: dict[str, int] = {
        "applicant_question": 0,
        "calculated_output": 0,
        "technical_field": 0,
        "static_content": 0,
        "attachment": 0,
    }
    for node in portable["nodes"]:
        source_path = node["path"]
        runtime_path = source_index.get(source_path)
        runtime_pointer = _pointer(runtime_path) if runtime_path is not None else None
        if source_path in calculation_targets:
            classification = "calculated_output"
        elif runtime_pointer in attachment_runtime_paths:
            classification = "attachment"
        elif node["record_kind"] == "question" and node.get("countable") is True:
            classification = "applicant_question"
        elif node["record_kind"] == "static_content":
            classification = "static_content"
        else:
            classification = "technical_field"
        counts[classification] += 1

        authoring = node.get("authoring", {})
        semantic_candidates = authoring.get("semantic_candidates", [])
        canonical_semantic_id = semantic_candidates[0] if len(semantic_candidates) == 1 else None
        constraints = node.get("constraints", {})
        declared_type = constraints.get("declared_type")
        source_version = node.get("source_version")
        records.append({
            "stable_record_id": node["node_id"],
            "source_path": source_path,
            "runtime_schema_pointer": (
                _schema_pointer(runtime_path) if runtime_path is not None else None
            ),
            "runtime_data_pointer_template": (
                _data_pointer_template(runtime_path) if runtime_path is not None else None
            ),
            "classification": classification,
            "counts_as_applicant_question": classification == "applicant_question",
            "canonical_semantic_question_id": canonical_semantic_id,
            "semantic_mapping_status": (
                authoring.get("review_statuses", [None])[0]
                if canonical_semantic_id is not None
                else "unmapped"
            ),
            "semantic_candidates": semantic_candidates,
            "xml": {
                "path": source_path,
                "type": declared_type or node.get("data_type"),
                "type_source": ("xsd_declared_type" if declared_type else "normalized_source_type"),
                "xsd_url": node.get("source_ref"),
                "version": source_version,
                "sha256": (
                    source_version.removeprefix("sha256:")
                    if isinstance(source_version, str)
                    else None
                ),
            },
            "component_module_ids": authoring.get("modules", []),
            "roles": authoring.get("roles", []),
            "dimensions": authoring.get("dimensions", []),
            "cardinality": node.get("cardinality"),
            "source_behavior_ids": node.get("behavior_keys", []),
            "runtime_behavior_links": rule_links.get(source_path, []),
            "review_statuses": authoring.get("review_statuses", []),
            "published_coverage_eligible": authoring.get("published_coverage_eligible", False),
        })
    if counts["calculated_output"] != len(calculation_targets):
        raise SourceResolvedFormError("Calculated-output metadata accounting drift")
    return {
        "contract": "simpler-form-field-metadata/v1",
        "form_id": portable["form_id"],
        "source_form_version": portable["form_version"],
        "counts": {**counts, "total_records": len(records)},
        "records": records,
        "review_boundary": deepcopy(portable["review_boundary"]),
    }


def build_source_resolved_form(
    package_dir: Path, config: SourceResolvedFormConfig
) -> SourceResolvedFormBuild:
    """Compile a pinned, coverage-ineligible source package to native Simpler artifacts."""

    manifest, packaged_schema, runtime, portable = _load_package(package_dir, config)
    accounting = runtime.get("accounting", {})
    if accounting.get("normalized_records") != config.conditions + config.calculations:
        raise SourceResolvedFormError("Runtime-rule accounting drift")
    if (
        accounting.get("blocked_records") != 0
        or accounting.get("working_rules_needing_path_resolution") != 0
    ):
        raise SourceResolvedFormError("Runtime-rule package is not fully resolved")
    if manifest.get("source_evidence", {}).get("nodes") != config.source_nodes:
        raise SourceResolvedFormError("Source-node accounting drift")

    schema = deepcopy(packaged_schema)
    index = _source_path_index(schema)
    rule_schema: dict[str, Any] = {}
    visibility_rules: dict[str, dict[str, Any]] = {}
    condition_ids: list[str] = []
    calculation_ids: list[str] = []

    for rule in runtime.get("rules", []):
        _assert_rule_boundary(rule)
        mechanism = rule.get("mechanism")
        if mechanism == "calculation":
            _compile_calculation(schema, rule_schema, index, rule)
            calculation_ids.append(rule["rule_id"])
        elif mechanism == "condition":
            effect = rule.get("effect")
            if effect == "required":
                _compile_required_condition(schema, index, rule)
            elif effect == "visible":
                operator = rule.get("operator")
                dependencies = rule.get("dependencies", [])
                source_value = rule.get("source_value", {})
                if len(dependencies) != 1 or operator not in {"equals", "present"}:
                    raise SourceResolvedFormError(
                        f"Unsupported visibility rule: {rule.get('rule_id')}"
                    )
                dependency = dependencies[0]["path"]
                dependency_path = index.get(dependency)
                if dependency_path is None:
                    raise SourceResolvedFormError(f"Unknown visibility dependency: {dependency}")
                if (
                    source_value.get("target_path") != rule["target"]["path"]
                    or source_value.get("dependency_paths") != [dependency]
                    or source_value.get("operator") != operator
                    or source_value.get("effect") != "visible"
                ):
                    raise SourceResolvedFormError(
                        f"Visibility evidence drift: {rule.get('rule_id')}"
                    )
                predicate: dict[str, Any] = {
                    "op": operator,
                    "ref": {"scope": "root", "pointer": _pointer(dependency_path)},
                }
                if operator == "equals":
                    if source_value.get("value") != rule.get("value"):
                        raise SourceResolvedFormError(
                            f"Visibility value drift: {rule.get('rule_id')}"
                        )
                    predicate["value"] = _condition_value(schema, dependency_path, rule["value"])
                conditional = {
                    "when": predicate,
                    "then": {"visible": True},
                    "otherwise": {"visible": False},
                }
                target_source = rule["target"]["path"]
                existing = visibility_rules.get(target_source)
                if existing is not None and existing != conditional:
                    raise SourceResolvedFormError(f"Conflicting visibility rules: {target_source}")
                visibility_rules[target_source] = conditional
            else:
                raise SourceResolvedFormError(f"Unsupported condition effect: {effect}")
            condition_ids.append(rule["rule_id"])
        else:
            raise SourceResolvedFormError(f"Unsupported runtime mechanism: {mechanism}")

    if len(condition_ids) != config.conditions or len(calculation_ids) != config.calculations:
        raise SourceResolvedFormError("Compiled runtime-rule count drift")
    attachment_paths = _compile_attachments(schema, rule_schema)
    if len(attachment_paths) != config.attachment_fields:
        raise SourceResolvedFormError("Attachment accounting drift")
    ui_schema = _build_ui(
        schema,
        visibility_rules,
        frozenset(config.unsupported_scalar_arrays),
    )
    field_metadata = _build_field_metadata(portable, runtime, index, attachment_paths)
    schema["x-simpler-field-metadata"] = field_metadata

    form = Form(
        form_id=config.form_id,
        legacy_form_id=None,
        form_name=config.form_name,
        short_form_name=config.short_form_name,
        form_version=config.form_version,
        agency_code="HHS",
        form_json_schema=schema,
        form_ui_schema=ui_schema,
        form_rule_schema=rule_schema,
        json_to_xml_schema=None,
        form_type=config.form_type,
        form_instruction_id=config.form_instruction_id,
        is_deprecated=False,
    )
    return SourceResolvedFormBuild(
        form=form,
        manifest=deepcopy(manifest),
        condition_rule_ids=tuple(condition_ids),
        calculation_rule_ids=tuple(calculation_ids),
        attachment_paths=attachment_paths,
        field_metadata=deepcopy(field_metadata),
    )
