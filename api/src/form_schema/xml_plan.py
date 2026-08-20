"""Compile source-pinned grants XML plans into the native XML transform dialect."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

XML_PLAN_CONTRACT = "source-pinned-xml-plan/v1"
RUNTIME_PROFILE_CONTRACT = "simpler-xml-runtime-profile/v1"
REVIEWED_STATUSES = {"accepted", "human_reviewed", "reviewed"}


class XMLPlanError(ValueError):
    """Raised when an XML plan cannot be compiled without inference."""


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise XMLPlanError(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise XMLPlanError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise XMLPlanError(f"{label} must be a non-empty string")
    return value


def _sha256(value: object, label: str) -> str:
    digest = _string(value, label)
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise XMLPlanError(f"{label} must be a lowercase SHA-256 digest")
    return digest


def _qname(value: object, label: str) -> tuple[str, str, str | None]:
    qname = _object(value, label)
    namespace = _string(qname.get("namespace"), f"{label}.namespace")
    local_name = _string(qname.get("local_name"), f"{label}.local_name")
    prefix = qname.get("preferred_prefix")
    if prefix is not None and (not isinstance(prefix, str) or not prefix):
        raise XMLPlanError(f"{label}.preferred_prefix must be a non-empty string")
    return namespace, local_name, prefix


def _pointer(value: object, label: str) -> str:
    pointer = _string(value, label)
    if not pointer.startswith("/") or pointer == "/" or "//" in pointer:
        raise XMLPlanError(f"{label} must be a non-root absolute application pointer")
    return pointer


def _pointer_segments(pointer: str) -> list[str]:
    return [segment.replace("~1", "/").replace("~0", "~") for segment in pointer[1:].split("/")]


def _dotted(pointer: str) -> str:
    segments = _pointer_segments(pointer)
    if any("." in segment for segment in segments):
        raise XMLPlanError(f"application pointer {pointer!r} cannot map safely to a dotted path")
    return ".".join(segments)


def _provenance(value: object, label: str) -> list[dict[str, Any]]:
    items = _array(value, label)
    if not items:
        raise XMLPlanError(f"{label} must contain at least one source reference")
    for index, item in enumerate(items):
        source = _object(item, f"{label}[{index}]")
        _string(source.get("path"), f"{label}[{index}].path")
        _string(source.get("source_ref"), f"{label}[{index}].source_ref")
        _sha256(source.get("sha256"), f"{label}[{index}].sha256")
        _string(source.get("selector"), f"{label}[{index}].selector")
    return items


def _canonical_digest(value: object) -> str:
    content = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
    return hashlib.sha256(content).hexdigest()


def _validate_provenance_sources(value: object, sources: list[dict[str, Any]]) -> None:
    """Tie every provenance reference in the document tree to a verified source."""

    source_keys = {(source["path"], source["source_ref"], source["sha256"]) for source in sources}

    def walk(item: object, label: str) -> None:
        if isinstance(item, dict):
            if "provenance" in item:
                for index, provenance in enumerate(
                    _provenance(item["provenance"], f"{label}.provenance")
                ):
                    key = (
                        provenance["path"],
                        provenance["source_ref"],
                        provenance["sha256"],
                    )
                    if key not in source_keys:
                        raise XMLPlanError(
                            f"{label}.provenance[{index}] does not match a verified source"
                        )
            for key, child in item.items():
                if key != "provenance":
                    walk(child, f"{label}.{key}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{label}[{index}]")

    walk(value, "document")


def _source(value: object, label: str, source_root: Path) -> dict[str, Any]:
    source = _object(value, label)
    _string(source.get("path"), f"{label}.path")
    _string(source.get("source_ref"), f"{label}.source_ref")
    expected_digest = _sha256(source.get("sha256"), f"{label}.sha256")
    _string(source.get("target_namespace"), f"{label}.target_namespace")
    _string(source.get("schema_version"), f"{label}.schema_version")
    _string(source.get("role"), f"{label}.role")
    source_path = (source_root / source["path"]).resolve()
    try:
        source_path.relative_to(source_root)
    except ValueError as exc:
        raise XMLPlanError(f"{label}.path escapes the configured source root") from exc
    if not source_path.is_file():
        raise XMLPlanError(f"{label}.path does not resolve to a source file")
    actual_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if actual_digest != expected_digest:
        raise XMLPlanError(f"{label}.sha256 does not match the pinned source bytes")
    return source


def _review(value: object, label: str) -> dict[str, Any]:
    review = _object(value, label)
    if review.get("status") not in REVIEWED_STATUSES:
        raise XMLPlanError(f"{label}.status is not reviewed")
    _string(review.get("reviewed_by"), f"{label}.reviewed_by")
    _string(review.get("reviewed_at"), f"{label}.reviewed_at")
    _string(review.get("evidence_ref"), f"{label}.evidence_ref")
    return review


def _runtime_bindings(profile: object | None) -> tuple[dict[str, str], list[dict[str, Any]]]:
    if profile is None:
        return {}, []
    value = _object(profile, "runtime profile")
    if value.get("contract") != RUNTIME_PROFILE_CONTRACT:
        raise XMLPlanError(f"runtime profile contract must be {RUNTIME_PROFILE_CONTRACT}")
    _string(value.get("profile_id"), "runtime profile.profile_id")
    expected_digest = _sha256(value.get("profile_sha256"), "runtime profile.profile_sha256")
    digest_input = {key: item for key, item in value.items() if key != "profile_sha256"}
    actual_digest = hashlib.sha256(
        json.dumps(digest_input, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if actual_digest != expected_digest:
        raise XMLPlanError("runtime profile.profile_sha256 does not match its content")
    _review(value.get("review"), "runtime profile.review")

    bindings: dict[str, str] = {}
    for pointer_value, binding_value in _object(
        value.get("bindings"), "runtime profile.bindings"
    ).items():
        pointer = _pointer(pointer_value, "runtime profile binding key")
        binding = _object(binding_value, f"runtime profile binding {pointer}")
        _review(binding.get("review"), f"runtime profile binding {pointer}.review")
        runtime_path = _string(
            binding.get("runtime_path"), f"runtime profile binding {pointer}.runtime_path"
        )
        if "." in runtime_path or "/" in runtime_path:
            raise XMLPlanError(
                f"runtime binding {pointer!r} must currently target one root-level field"
            )
        bindings[pointer] = runtime_path
    return bindings, _array(value.get("legacy_namespaces", []), "runtime profile.legacy_namespaces")


def _namespace_prefix(
    namespace: str, preferred_prefix: str | None, namespaces: dict[str, str]
) -> str:
    if preferred_prefix is not None:
        if namespaces.get(preferred_prefix) != namespace:
            raise XMLPlanError(
                f"preferred prefix {preferred_prefix!r} is not declared for {namespace!r}"
            )
        return preferred_prefix
    matches = [prefix for prefix, uri in namespaces.items() if uri == namespace]
    if len(matches) != 1:
        raise XMLPlanError(f"namespace {namespace!r} does not resolve to exactly one prefix")
    return matches[0]


def _validate_occurs(node: dict[str, Any], label: str) -> None:
    minimum = node.get("min_occurs")
    maximum = node.get("max_occurs")
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
        raise XMLPlanError(f"{label}.min_occurs must be a non-negative integer")
    if maximum != "unbounded" and (
        not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < minimum
    ):
        raise XMLPlanError(f"{label}.max_occurs must be >= min_occurs or unbounded")


def _choice_metadata(value: object, label: str) -> dict[str, Any] | None:
    if value is None:
        return None
    choice = _object(value, label)
    group_id = _string(choice.get("group_id"), f"{label}.group_id")
    minimum = choice.get("min_occurs")
    maximum = choice.get("max_occurs")
    if choice.get("exclusive") is not True:
        raise XMLPlanError(f"choice group {group_id!r} must be exclusive")
    if not isinstance(minimum, int) or minimum not in {0, 1}:
        raise XMLPlanError(f"choice group {group_id!r} min_occurs must be zero or one")
    if maximum != 1:
        raise XMLPlanError(f"choice group {group_id!r} max_occurs must be one")
    return {"group_id": group_id, "min_occurs": minimum, "max_occurs": maximum}


def _children(value: object, label: str) -> list[dict[str, Any]]:
    children = _array(value, label)
    if not all(isinstance(child, dict) for child in children):
        raise XMLPlanError(f"{label} entries must be objects")
    if [child.get("order") for child in children] != list(range(len(children))):
        raise XMLPlanError(f"{label} must be in contiguous XSD order")
    groups: dict[str, dict[str, Any]] = {}
    for index, child in enumerate(children):
        metadata = _choice_metadata(child.get("choice_group"), f"{label}[{index}].choice_group")
        if metadata is None:
            continue
        group_id = metadata["group_id"]
        if group_id in groups and groups[group_id] != metadata:
            raise XMLPlanError(f"choice group {group_id!r} has inconsistent bounds")
        groups[group_id] = metadata
    return children


def _target(
    node: dict[str, Any], namespaces: dict[str, str], label: str
) -> tuple[str, str, dict[str, Any]]:
    namespace, local_name, preferred_prefix = _qname(node.get("qname"), f"{label}.qname")
    prefix = _namespace_prefix(namespace, preferred_prefix, namespaces)
    transform: dict[str, Any] = {
        "target": local_name,
        "namespace_scope": prefix,
    }
    return namespace, local_name, transform


def _runtime_key(pointer: str, target: str, bindings: dict[str, str], *, nested: bool) -> str:
    runtime_path = bindings.get(pointer, _dotted(pointer))
    if pointer not in bindings and _pointer_segments(pointer)[-1] != target:
        raise XMLPlanError(
            f"canonical application pointer {pointer!r} does not match XML target {target!r}"
        )
    if nested:
        if pointer in bindings:
            raise XMLPlanError(
                f"reviewed binding for nested pointer {pointer!r} requires parent composition"
            )
        if runtime_path.rsplit(".", 1)[-1] != target:
            raise XMLPlanError(
                f"application pointer {pointer!r} does not match XML target {target!r}"
            )
        return target
    return runtime_path


def _with_metadata(rule: dict[str, Any], node: dict[str, Any], label: str) -> dict[str, Any]:
    rule["_provenance"] = _provenance(node.get("provenance"), f"{label}.provenance")
    rule["_occurs"] = {
        "min_occurs": node["min_occurs"],
        "max_occurs": node["max_occurs"],
        "kind": node["kind"],
    }
    choice = _choice_metadata(node.get("choice_group"), f"{label}.choice_group")
    if choice is not None:
        rule["_choice_group"] = choice
    return rule


def _attachment(
    node: dict[str, Any], bindings: dict[str, str], ancestors: list[str], label: str
) -> tuple[str, dict[str, Any]]:
    _, target, _ = _qname(node.get("qname"), f"{label}.qname")
    origin = _object(node.get("value_origin"), f"{label}.value_origin")
    if origin.get("kind") != "attachment":
        raise XMLPlanError(f"attachment node {target!r} must have attachment value origin")
    pointer = _pointer(origin.get("pointer"), f"{label}.value_origin.pointer")
    metadata = _object(node.get("attachment"), f"{label}.attachment")
    cardinality = metadata.get("cardinality")
    minimum_files = metadata.get("minimum_files")
    maximum_files = metadata.get("maximum_files")
    if not isinstance(minimum_files, int) or isinstance(minimum_files, bool) or minimum_files < 0:
        raise XMLPlanError(f"{label}.attachment.minimum_files must be non-negative")
    if (
        not isinstance(maximum_files, int)
        or isinstance(maximum_files, bool)
        or maximum_files < minimum_files
    ):
        raise XMLPlanError(f"{label}.attachment.maximum_files must be >= minimum_files")
    _runtime_key(pointer, target, bindings, nested=bool(ancestors))
    source_path = bindings.get(pointer, _dotted(pointer))
    slot = ancestors[0] if ancestors else target
    entry: dict[str, Any]
    if cardinality == "single":
        entry = {
            "file_element": target,
            "source_path": source_path,
            "type": "single_with_wrapper" if ancestors else "single",
            "xml_element": ancestors[-1] if ancestors else target,
            "xml_parent_path": ancestors[:-1] if ancestors else [],
        }
    elif cardinality == "multiple":
        entry = {
            "source_path": source_path,
            "type": "multiple",
            "xml_element": target,
            "xml_parent_path": ancestors,
        }
    else:
        raise XMLPlanError(f"unsupported attachment cardinality {cardinality!r}")
    if cardinality == "single" and maximum_files > 1:
        raise XMLPlanError(f"single attachment node {target!r} cannot allow multiple files")
    entry["minimum_files"] = minimum_files
    entry["maximum_files"] = maximum_files
    entry["_provenance"] = _provenance(node.get("provenance"), f"{label}.provenance")
    entry["_occurs"] = {
        "min_occurs": node["min_occurs"],
        "max_occurs": node["max_occurs"],
        "kind": "attachment",
    }
    choice = _choice_metadata(node.get("choice_group"), f"{label}.choice_group")
    if choice is not None and ancestors:
        entry["_choice_group"] = choice
    return slot, entry


def _node_rule(
    node: dict[str, Any],
    bindings: dict[str, str],
    namespaces: dict[str, str],
    parent_namespace: str,
    ancestors: list[str],
    attachments: dict[str, list[dict[str, Any]]],
    label: str,
    *,
    nested: bool,
    inside_array: bool = False,
) -> tuple[str, dict[str, Any]] | None:
    _validate_occurs(node, label)
    namespace, target, transform = _target(node, namespaces, label)
    origin = _object(node.get("value_origin"), f"{label}.value_origin")
    kind = node.get("kind")
    repeated = node["max_occurs"] == "unbounded" or node["max_occurs"] > 1
    if repeated and kind not in {"array", "attachment"}:
        raise XMLPlanError(f"repeating node {target!r} must use array or attachment kind")
    if kind == "array" and not repeated:
        raise XMLPlanError(f"array node {target!r} must have max_occurs greater than one")

    if kind == "attachment":
        if inside_array:
            raise XMLPlanError(
                f"attachment node {target!r} is nested below an array; "
                "row-qualified attachment bindings are not supported"
            )
        if namespace != parent_namespace:
            raise XMLPlanError(
                f"attachment node {target!r} changes namespace below its parent; "
                "qualified attachment paths are not supported"
            )
        slot, entry = _attachment(node, bindings, ancestors, label)
        attachments.setdefault(slot, []).append(entry)
        return None
    if kind == "simple":
        if origin.get("kind") == "constant":
            if "value" not in origin:
                raise XMLPlanError(f"constant node {target!r} requires a value")
            if origin["value"] is None:
                raise XMLPlanError(f"constant node {target!r} cannot have a null value")
            transform["static_value"] = origin["value"]
            return f"constant_{node['order']}_{target}", _with_metadata(
                {"xml_transform": transform}, node, label
            )
        if origin.get("kind") == "unresolved":
            raise XMLPlanError(f"required runtime value for {target!r} is unresolved")
        if origin.get("kind") != "application_pointer":
            raise XMLPlanError(f"simple node {target!r} requires an application_pointer origin")
        pointer = _pointer(origin.get("pointer"), f"{label}.value_origin.pointer")
        return _runtime_key(pointer, target, bindings, nested=nested), _with_metadata(
            {"xml_transform": transform}, node, label
        )
    if kind not in {"object", "array"}:
        raise XMLPlanError(f"unsupported XML node kind {kind!r}")
    if origin.get("kind") != kind:
        raise XMLPlanError(f"{kind} node {target!r} must have {kind} value origin")
    pointer = _pointer(origin.get("pointer"), f"{label}.value_origin.pointer")
    children = _children(node.get("children", []), f"{label}.children")
    if kind == "object" and not children:
        raise XMLPlanError(f"object node {target!r} must have children")
    child_kinds = {child.get("kind") for child in children}
    if "attachment" in child_kinds and len(child_kinds) > 1:
        raise XMLPlanError(
            f"XML node {target!r} mixes attachment and ordinary children; "
            "in-place attachment merging is not supported"
        )

    directly_bound = [
        child
        for child in children
        if _object(child.get("value_origin"), f"{label}.child.value_origin").get("pointer")
        in bindings
    ]
    if directly_bound:
        if kind != "object" or any(child.get("kind") != "simple" for child in children):
            raise XMLPlanError(
                "flattened runtime profiles support only objects with simple children"
            )
        if any(child.get("choice_group") is not None for child in children):
            raise XMLPlanError("flattened runtime profiles do not support XML choice groups")
        child_pointers = {
            _pointer(
                _object(child.get("value_origin"), f"{label}.child.value_origin").get("pointer"),
                f"{label}.child.value_origin.pointer",
            )
            for child in children
        }
        if not child_pointers.issubset(bindings):
            missing = sorted(child_pointers - bindings.keys())
            raise XMLPlanError(f"flattened runtime profile is missing child bindings: {missing!r}")
        field_mapping: dict[str, str] = {}
        for index, child in enumerate(children):
            child_namespace, child_target, _ = _qname(
                child.get("qname"), f"{label}.children[{index}].qname"
            )
            if child_namespace != namespace:
                raise XMLPlanError(
                    f"flattened runtime profile for {target!r} changes child namespace; "
                    "qualified flattened bindings are not supported"
                )
            child_origin = _object(
                child.get("value_origin"), f"{label}.children[{index}].value_origin"
            )
            child_pointer = _pointer(
                child_origin.get("pointer"), f"{label}.children[{index}].value_origin.pointer"
            )
            field_mapping[child_target] = bindings.get(child_pointer, _dotted(child_pointer))
        transform.update(
            {
                "type": "conditional",
                "conditional_transform": {"type": "compose_object", "field_mapping": field_mapping},
            }
        )
        return f"object_{node['order']}_{target}", _with_metadata(
            {"xml_transform": transform}, node, label
        )

    child_rules: dict[str, Any] = {}
    for index, child in enumerate(children):
        lowered = _node_rule(
            child,
            bindings,
            namespaces,
            namespace,
            [*ancestors, target],
            attachments,
            f"{label}.children[{index}]",
            nested=True,
            inside_array=inside_array or kind == "array",
        )
        if lowered is None:
            continue
        child_key, child_rule = lowered
        if child_key in child_rules:
            raise XMLPlanError(f"duplicate runtime key {child_key!r} in {target!r}")
        child_rules[child_key] = child_rule
    if kind == "array" and not children:
        transform["type"] = "array"
        return _runtime_key(pointer, target, bindings, nested=nested), _with_metadata(
            {"xml_transform": transform}, node, label
        )
    if not child_rules:
        return None
    transform["type"] = "array" if kind == "array" else "nested_object"
    rule: dict[str, Any] = {"xml_transform": transform}
    if kind == "array":
        rule["items"] = child_rules
    else:
        rule.update(child_rules)
    return _runtime_key(pointer, target, bindings, nested=nested), _with_metadata(rule, node, label)


def compile_xml_plan(
    plan: object,
    runtime_profile: object | None = None,
    *,
    source_root: Path,
    source_manifest: object,
) -> dict[str, Any]:
    """Validate and deterministically compile one source-pinned plan."""

    value = _object(plan, "XML plan")
    if value.get("contract") != XML_PLAN_CONTRACT or value.get("format_version") != 1:
        raise XMLPlanError(f"XML plan must declare {XML_PLAN_CONTRACT} format_version 1")
    form = _object(value.get("form"), "form")
    form_id = _string(form.get("form_id"), "form.form_id")
    _string(form.get("form_version"), "form.form_version")

    source_set = _object(value.get("source_set"), "source_set")
    source_root = source_root.resolve()
    root_schema = _source(source_set.get("root_schema"), "source_set.root_schema", source_root)
    if root_schema["role"] != "root":
        raise XMLPlanError("source_set.root_schema.role must be root")
    xsd_url = root_schema["source_ref"]
    dependencies: list[dict[str, Any]] = []
    for index, dependency_value in enumerate(
        _array(source_set.get("dependencies"), "source_set.dependencies")
    ):
        dependencies.append(
            _source(dependency_value, f"source_set.dependencies[{index}]", source_root)
        )
    source_rows = [root_schema, *dependencies]
    graph_sha256 = _sha256(source_set.get("graph_sha256"), "source_set.graph_sha256")
    if _canonical_digest(source_rows) != graph_sha256:
        raise XMLPlanError("source_set.graph_sha256 does not match the verified source graph")
    source_manifest_sha256 = _sha256(
        source_set.get("source_manifest_sha256"), "source_set.source_manifest_sha256"
    )
    if _canonical_digest(source_manifest) != source_manifest_sha256:
        raise XMLPlanError(
            "source_set.source_manifest_sha256 does not match the supplied source manifest"
        )

    bindings, legacy_namespaces = _runtime_bindings(runtime_profile)
    document = _object(value.get("document"), "document")
    _validate_provenance_sources(document, source_rows)
    namespace_items = _array(document.get("namespaces"), "document.namespaces")
    if not namespace_items:
        raise XMLPlanError("document.namespaces must not be empty")
    declared: dict[str, str] = {}
    for index, item_value in enumerate(namespace_items):
        item = _object(item_value, f"document.namespaces[{index}]")
        if item.get("declare_in_output") is not True:
            continue
        prefix = _string(item.get("prefix"), f"document.namespaces[{index}].prefix")
        uri = _string(item.get("uri"), f"document.namespaces[{index}].uri")
        if prefix in declared:
            raise XMLPlanError(f"namespace prefix {prefix!r} is declared more than once")
        declared[prefix] = uri
    for index, item_value in enumerate(legacy_namespaces):
        item = _object(item_value, f"runtime profile.legacy_namespaces[{index}]")
        if item.get("evidence") != "legacy_observed":
            raise XMLPlanError("legacy namespaces require legacy_observed evidence")
        prefix = _string(item.get("prefix"), f"runtime profile.legacy_namespaces[{index}].prefix")
        uri = _string(item.get("uri"), f"runtime profile.legacy_namespaces[{index}].uri")
        if prefix in declared and declared[prefix] != uri:
            raise XMLPlanError(f"legacy namespace prefix {prefix!r} conflicts with XML plan")
        declared[prefix] = uri

    root = _object(document.get("root"), "document.root")
    root_namespace, root_name, preferred_root_prefix = _qname(
        root.get("qname"), "document.root.qname"
    )
    if root_namespace != root_schema["target_namespace"]:
        raise XMLPlanError("document root namespace does not match the pinned root schema")
    namespace_version = re.search(r"-V([0-9]+(?:\.[0-9]+)*)$", root_schema["target_namespace"])
    if namespace_version is None or namespace_version.group(1) != form["form_version"]:
        raise XMLPlanError("form version does not match the pinned root schema identity")
    root_prefix = _namespace_prefix(root_namespace, preferred_root_prefix, declared)
    namespaces = {"default": root_namespace, **declared}

    root_attributes: dict[str, Any] = {}
    for index, item_value in enumerate(
        _array(root.get("attributes", []), "document.root.attributes")
    ):
        item = _object(item_value, f"document.root.attributes[{index}]")
        namespace, local_name, preferred_prefix = _qname(
            item.get("qname"), f"document.root.attributes[{index}].qname"
        )
        prefix = _namespace_prefix(namespace, preferred_prefix, declared)
        origin = _object(
            item.get("value_origin"), f"document.root.attributes[{index}].value_origin"
        )
        if origin.get("kind") != "constant":
            raise XMLPlanError("root attributes currently require constant value origins")
        if "value" not in origin:
            raise XMLPlanError("constant root attributes require a value")
        if origin["value"] is None:
            raise XMLPlanError("constant root attributes cannot have null values")
        _provenance(item.get("provenance"), f"document.root.attributes[{index}].provenance")
        root_attributes[f"{prefix}:{local_name}"] = {
            "kind": "constant",
            "value": origin["value"],
        }

    review_boundary = _object(value.get("review_boundary"), "review_boundary")
    expected_review_keys = {
        "structural_facts",
        "application_pointers",
        "semantic_mappings",
        "published_coverage_eligible",
    }
    if set(review_boundary) != expected_review_keys:
        raise XMLPlanError("review_boundary has missing or unsupported fields")
    if review_boundary.get("structural_facts") != "deterministic_from_pinned_xsd":
        raise XMLPlanError("review_boundary.structural_facts is unsupported")
    if review_boundary.get("application_pointers") != "exact_source_paths_not_semantic_mappings":
        raise XMLPlanError("review_boundary.application_pointers is unsupported")
    if review_boundary.get("semantic_mappings") != []:
        raise XMLPlanError("review_boundary.semantic_mappings must be empty")
    if review_boundary.get("published_coverage_eligible") is not False:
        raise XMLPlanError("source-pinned XML plans cannot claim published coverage")
    result: dict[str, Any] = {
        "_xml_config": {
            "description": f"Generated from source-pinned XML plan for {form_id}",
            "version": "1.0",
            "form_name": form_id,
            "namespaces": namespaces,
            "xsd_url": xsd_url,
            "xml_structure": {
                "root_element": root_name,
                "root_namespace_prefix": root_prefix,
                "root_attributes": root_attributes,
            },
            "null_handling_options": {
                "exclude": "Default - exclude field entirely from XML (recommended)"
            },
            "source_plan": {
                "contract": value["contract"],
                "format_version": value["format_version"],
                "form": deepcopy(form),
                "source_set": deepcopy(source_set),
                "review_boundary": deepcopy(review_boundary),
                "runtime_profile": deepcopy(runtime_profile),
            },
        }
    }

    _provenance(root.get("provenance"), "document.root.provenance")
    attachments: dict[str, list[dict[str, Any]]] = {}
    for index, child in enumerate(_children(root.get("children"), "document.root.children")):
        lowered = _node_rule(
            child,
            bindings,
            namespaces,
            root_namespace,
            [],
            attachments,
            f"document.root.children[{index}]",
            nested=False,
        )
        if lowered is None:
            _, target, _ = _qname(child.get("qname"), f"document.root.children[{index}].qname")
            origin = _object(
                child.get("value_origin"), f"document.root.children[{index}].value_origin"
            )
            pointer = _pointer(
                origin.get("pointer"),
                f"document.root.children[{index}].value_origin.pointer",
            )
            slot_rule = _with_metadata(
                {"xml_transform": {"target": target, "type": "attachment_slot"}},
                child,
                f"document.root.children[{index}]",
            )
            slot_rule["_source_path"] = bindings.get(pointer, _dotted(pointer))
            result[f"attachment_slot_{index}_{target}"] = slot_rule
            continue
        key, rule = lowered
        if key in result:
            raise XMLPlanError(f"duplicate runtime key {key!r}")
        result[key] = rule
    if attachments:
        result["_xml_config"]["attachment_fields"] = {
            slot: {"entries": entries} for slot, entries in attachments.items()
        }
    return result
