"""Lossless source-record metadata for implementation-derived form analysis."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any


class FieldMetadataError(ValueError):
    """Raised when source records cannot be bound exactly to a runtime schema."""


RuntimePath = tuple[tuple[str, bool], ...]
_ATT_SLOT = re.compile(r"ATT\d+$")


def _schema_pointer(path: RuntimePath) -> str:
    parts: list[str] = []
    for name, repeated in path:
        parts.extend(("properties", name))
        if repeated:
            parts.append("items")
    return "/" + "/".join(parts)


def _data_pointer(path: RuntimePath) -> str:
    parts: list[str] = []
    for name, repeated in path:
        parts.append(name.replace("~", "~0").replace("/", "~1"))
        if repeated:
            parts.append("*")
    return "/" + "/".join(parts)


def _schema_source_index(
    schema: dict[str, Any],
) -> dict[str, tuple[str, str, dict[str, Any]]]:
    result: dict[str, tuple[str, str, dict[str, Any]]] = {}

    def visit(node: dict[str, Any], path: RuntimePath) -> None:
        authoring = node.get("x-authoring")
        authoring_path = authoring.get("source_path") if isinstance(authoring, dict) else None
        source_path = node.get("x-source-path") or authoring_path
        if isinstance(source_path, str) and source_path:
            if source_path in result:
                raise FieldMetadataError(f"duplicate runtime source path: {source_path}")
            result[source_path] = (_schema_pointer(path), _data_pointer(path), node)
        if node.get("type") == "object" or isinstance(node.get("properties"), dict):
            for name, child in node.get("properties", {}).items():
                if isinstance(child, dict):
                    visit(child, path + ((name, False),))
        if node.get("type") == "array" or isinstance(node.get("items"), dict):
            items = node.get("items")
            if isinstance(items, dict) and path:
                visit(items, path[:-1] + ((path[-1][0], True),))

    visit(schema, ())
    return result


def explicit_property_bindings(
    authoring: Mapping[str, Any],
) -> dict[str, tuple[str, str]]:
    """Translate source-authored root-property declarations into runtime pointers."""

    bindings: dict[str, tuple[str, str]] = {}
    properties = authoring.get("json_properties")
    if not isinstance(properties, list):
        raise FieldMetadataError("source-authored json_properties are missing")
    for declaration in properties:
        if not isinstance(declaration, dict):
            raise FieldMetadataError("source-authored property declaration is invalid")
        name = declaration.get("name")
        source_paths = declaration.get("source_paths")
        if not isinstance(name, str) or not name or not isinstance(source_paths, list):
            raise FieldMetadataError("source-authored property binding is incomplete")
        escaped = name.replace("~", "~0").replace("/", "~1")
        pointer = (f"/properties/{escaped}", f"/{escaped}")
        for source_path in source_paths:
            if not isinstance(source_path, str) or not source_path:
                raise FieldMetadataError("source-authored source path is invalid")
            if source_path in bindings and bindings[source_path] != pointer:
                raise FieldMetadataError(f"conflicting source-authored binding: {source_path}")
            bindings[source_path] = pointer
    return bindings


def _resolve_pointer(schema: dict[str, Any], pointer: str) -> dict[str, Any]:
    if pointer in {"", "/"}:
        return schema
    current: Any = schema
    for raw in pointer.removeprefix("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise FieldMetadataError(f"runtime schema pointer does not resolve: {pointer}")
        current = current[token]
    if not isinstance(current, dict):
        raise FieldMetadataError(f"runtime schema pointer is not an object: {pointer}")
    return current


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if isinstance(item, str) and item})


def _source_digest(record: Mapping[str, Any], source_ref: str) -> str | None:
    for entry in _strings(record.get("provenance")):
        digest, separator, reference = entry.partition(" ")
        if separator and reference == source_ref and digest.startswith("sha256:"):
            return digest.removeprefix("sha256:")
    source_version = record.get("source_version")
    if isinstance(source_version, str) and source_version.startswith("sha256:"):
        return source_version.removeprefix("sha256:")
    source = record.get("source")
    if isinstance(source, dict):
        for entry in _strings(source.get("provenance")):
            digest, separator, reference = entry.partition(" ")
            if separator and reference == source_ref and digest.startswith("sha256:"):
                return digest.removeprefix("sha256:")
    return None


def _runtime_links(rules: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, str]]]:
    links: dict[str, list[dict[str, str]]] = defaultdict(list)
    for rule in rules:
        rule_id = rule.get("rule_id")
        mechanism = rule.get("mechanism")
        if not isinstance(rule_id, str) or not isinstance(mechanism, str):
            continue
        candidates = [("target", [rule.get("target")])]
        candidates.extend((role, rule.get(role, [])) for role in ("dependencies", "operands"))
        for role, entries in candidates:
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                    continue
                links[entry["path"]].append({
                    "rule_id": rule_id,
                    "mechanism": mechanism,
                    "role": role,
                })
    return links


def _semantic_mapping(
    record: Mapping[str, Any], candidate: Mapping[str, Any] | None
) -> tuple[list[str], str]:
    if candidate is not None:
        key = candidate.get("question_candidate_key")
        status = candidate.get("review_status")
        return ([key] if isinstance(key, str) and key else []), (
            status if isinstance(status, str) and status else "unreviewed"
        )
    mapping = record.get("semantic_mapping")
    if isinstance(mapping, dict):
        concept = mapping.get("concept_id")
        status = mapping.get("status")
        return ([concept] if isinstance(concept, str) and concept else []), (
            status if isinstance(status, str) and status else "unreviewed"
        )
    return [], "unmapped"


def _record_kind(record: Mapping[str, Any]) -> str:
    value = record.get("record_kind") or record.get("kind")
    return value if isinstance(value, str) else ""


def _record_path(record: Mapping[str, Any]) -> str:
    path = record.get("path")
    if not isinstance(path, str) or not path:
        raise FieldMetadataError("source record path is missing")
    return path


def _record_id(record: Mapping[str, Any]) -> str:
    value = record.get("question_key") or record.get("node_id")
    if not isinstance(value, str) or not value:
        raise FieldMetadataError("source record stable ID is missing")
    return value


def _binding_for_path(
    source_path: str,
    runtime_index: Mapping[str, tuple[str, str, dict[str, Any]]],
    explicit: Mapping[str, tuple[str, str]],
) -> tuple[str, str, dict[str, Any]]:
    if source_path in explicit:
        schema_pointer, data_pointer = explicit[source_path]
        return schema_pointer, data_pointer, {}
    if source_path in runtime_index:
        return runtime_index[source_path]

    parent = source_path
    while "." in parent:
        parent = parent.rsplit(".", 1)[0]
        if parent in explicit:
            schema_pointer, data_pointer = explicit[parent]
            return schema_pointer, data_pointer, {}
        if parent in runtime_index:
            return runtime_index[parent]

    descendants: set[tuple[str, str]] = set()
    prefix = f"{source_path}."
    for path, (schema_pointer, data_pointer, _) in runtime_index.items():
        if path.startswith(prefix):
            descendants.add((schema_pointer, data_pointer))
    for path, pointer in explicit.items():
        if path.startswith(prefix):
            descendants.add(pointer)
    if len(descendants) == 1:
        schema_pointer, data_pointer = descendants.pop()
        return schema_pointer, data_pointer, {}
    return "/", "/", {}


def build_field_metadata(
    schema: dict[str, Any],
    *,
    form_id: str,
    form_version: str,
    source_records: list[dict[str, Any]],
    question_candidates: list[dict[str, Any]] | None = None,
    component_assignments: list[dict[str, Any]] | None = None,
    runtime_rules: list[dict[str, Any]] | None = None,
    explicit_bindings: Mapping[str, tuple[str, str]] | None = None,
    review_boundary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one complete metadata record for every pinned source record."""

    runtime_index = _schema_source_index(schema)
    explicit = dict(explicit_bindings or {})
    candidates: dict[str, dict[str, Any]] = {}
    for candidate in question_candidates or []:
        path = candidate.get("source_path")
        if not isinstance(path, str) or path in candidates:
            raise FieldMetadataError(f"invalid or duplicate question candidate: {path}")
        candidates[path] = candidate
    assignments: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for assignment in component_assignments or []:
        path = assignment.get("source_path")
        if not isinstance(path, str):
            raise FieldMetadataError("component assignment source path is missing")
        assignments[path].append(assignment)
    links = _runtime_links(runtime_rules or [])
    calculation_paths = {
        rule["target"]["path"]
        for rule in runtime_rules or []
        if rule.get("mechanism") == "calculation"
        and isinstance(rule.get("target"), dict)
        and isinstance(rule["target"].get("path"), str)
    }

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    counts = {
        "applicant_question": 0,
        "calculated_output": 0,
        "technical_field": 0,
        "static_content": 0,
        "attachment": 0,
    }
    for source in source_records:
        source_path = _record_path(source)
        stable_id = _record_id(source)
        if stable_id in seen_ids or source_path in seen_paths:
            raise FieldMetadataError(f"duplicate source record: {source_path}")
        seen_ids.add(stable_id)
        seen_paths.add(source_path)

        schema_pointer, data_pointer, indexed_node = _binding_for_path(
            source_path, runtime_index, explicit
        )
        schema_node = _resolve_pointer(schema, schema_pointer)
        if indexed_node and indexed_node is not schema_node:
            raise FieldMetadataError(f"runtime source index drift: {source_path}")
        kind = _record_kind(source)
        data_type = source.get("data_type")
        interaction = source.get("authoring_interaction") or source.get("interaction")
        authoring = schema_node.get("x-authoring")
        authoring_modules = (
            _strings(authoring.get("modules")) if isinstance(authoring, dict) else []
        )
        leaf = source_path.rsplit(".", 1)[-1]
        if (
            source_path in calculation_paths
            or interaction in {"computed", "calculated"}
            or schema_node.get("x-interaction") == "computed"
            or "budget-calculation" in authoring_modules
        ):
            classification = "calculated_output"
        elif data_type == "AttachedFileDataType":
            classification = "attachment"
        elif kind == "static_content":
            classification = "static_content"
        elif kind in {"technical_field", "technical", "container"} or _ATT_SLOT.fullmatch(leaf):
            classification = "technical_field"
        elif kind == "question":
            classification = "applicant_question"
        else:
            classification = "technical_field"
        counts[classification] += 1

        semantic_candidates, mapping_status = _semantic_mapping(source, candidates.get(source_path))
        modules: set[str] = set()
        roles: set[str] = set()
        for assignment in assignments.get(source_path, []):
            modules.update(_strings(assignment.get("module_ids")))
            component = assignment.get("component_id")
            if isinstance(component, str) and component:
                modules.add(component)
            role = assignment.get("role")
            if isinstance(role, str) and role:
                roles.add(role)
        behavior_ids = {
            behavior["behavior_key"]
            for behavior in source.get("behaviors", [])
            if isinstance(behavior, dict) and isinstance(behavior.get("behavior_key"), str)
        }
        constraints = source.get("constraints")
        if not isinstance(constraints, dict):
            constraints = {}
        declared_type = constraints.get("declared_type")
        source_info = source.get("source")
        source_ref = source.get("source_ref")
        source_version = source.get("source_version")
        if isinstance(source_info, dict):
            source_ref = source_ref or source_info.get("ref")
            source_version = source_version or source_info.get("version")
        source_ref = source_ref if isinstance(source_ref, str) else ""
        source_version = source_version if isinstance(source_version, str) else ""
        cardinality = source.get("cardinality")
        if not isinstance(cardinality, dict):
            cardinality = {
                "minimum": source.get("min_occurs"),
                "maximum": source.get("max_occurs"),
            }
        records.append({
            "stable_record_id": stable_id,
            "source_path": source_path,
            "runtime_schema_pointer": schema_pointer,
            "runtime_data_pointer_template": data_pointer,
            "classification": classification,
            "classification_basis": "source_record_kind_and_runtime_behavior",
            "source_countable": source.get("source_countable", source.get("countable")),
            "counts_as_applicant_question": classification == "applicant_question",
            "canonical_semantic_question_id": (
                semantic_candidates[0] if len(semantic_candidates) == 1 else None
            ),
            "semantic_mapping_status": mapping_status,
            "semantic_candidates": semantic_candidates,
            "xml": {
                "path": source_path,
                "type": declared_type or data_type,
                "type_source": (
                    "xsd_declared_type"
                    if isinstance(declared_type, str)
                    else "normalized_source_type"
                ),
                "xsd_url": source_ref,
                "version": source_version,
                "sha256": _source_digest(source, source_ref),
            },
            "component_module_ids": sorted(modules),
            "roles": sorted(roles),
            "dimensions": _strings(source.get("dimensions")),
            "cardinality": cardinality,
            "source_behavior_ids": sorted(behavior_ids),
            "runtime_behavior_links": links.get(source_path, []),
            "review_statuses": [mapping_status],
            "published_coverage_eligible": False,
        })

    dangling_candidates = sorted(set(candidates) - seen_paths)
    dangling_assignments = sorted(set(assignments) - seen_paths)
    if dangling_candidates:
        raise FieldMetadataError(
            f"question candidate source path is not present: {dangling_candidates[0]}"
        )
    if dangling_assignments:
        raise FieldMetadataError(
            f"component assignment source path is not present: {dangling_assignments[0]}"
        )

    return {
        "contract": "simpler-form-field-metadata/v1",
        "form_id": form_id,
        "source_form_version": form_version,
        "counts": {**counts, "total_records": len(records)},
        "records": records,
        "review_boundary": dict(review_boundary or {}),
    }


def attach_field_metadata(schema: dict[str, Any], metadata: dict[str, Any]) -> None:
    """Attach a validated, independently generated envelope to a native schema."""

    if "x-simpler-field-metadata" in schema:
        raise FieldMetadataError("runtime schema already contains field metadata")
    if metadata.get("contract") != "simpler-form-field-metadata/v1":
        raise FieldMetadataError("unsupported field metadata contract")
    records = metadata.get("records")
    if not isinstance(records, list) or metadata.get("counts", {}).get("total_records") != len(
        records
    ):
        raise FieldMetadataError("field metadata accounting drift")
    for record in records:
        if not isinstance(record, dict):
            raise FieldMetadataError("field metadata record is invalid")
        _resolve_pointer(schema, record.get("runtime_schema_pointer", ""))
    schema["x-simpler-field-metadata"] = metadata
