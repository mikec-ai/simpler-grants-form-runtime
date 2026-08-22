#!/usr/bin/env python3
"""Build declarative subaward and multi-project budget compositions."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from collections.abc import Iterator
from typing import Any

from build_portable_budget_pilot import (
    DECIMAL_PATTERN,
    artifact,
    portable_leaf,
    ui_elements,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "form-specs"
ORACLES = SPECS / "oracles" / "budget"
CROSSWALK_REVISION = "dfe9e47ffd6a25c967b8ed38703480ccdc15a8ef"
VERSION = "0.1.0"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def pointer_tokens(pointer: str) -> list[str]:
    if not pointer.startswith("/root") and not pointer.startswith("/properties"):
        raise ValueError(f"unsupported pointer: {pointer}")
    return [
        token.replace("~1", "/").replace("~0", "~") for token in pointer.split("/")[1:]
    ]


def at_pointer(document: dict[str, Any], pointer: str) -> Any:
    value: Any = document
    for token in pointer_tokens(pointer):
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def replace_pointer(document: dict[str, Any], pointer: str, value: Any) -> None:
    tokens = pointer_tokens(pointer)
    parent: Any = document
    for token in tokens[:-1]:
        parent = parent[int(token)] if isinstance(parent, list) else parent[token]
    if isinstance(parent, list):
        parent[int(tokens[-1])] = value
    else:
        parent[tokens[-1]] = value


def occurrences(node: Any, pointer: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    if not isinstance(node, dict):
        return
    if "x-source-path" in node and node.get("type") not in {"object", "array"}:
        yield pointer, node
    for name, child in node.get("properties", {}).items():
        yield from occurrences(child, f"{pointer}/properties/{name}")
    if isinstance(node.get("items"), dict):
        yield from occurrences(node["items"], f"{pointer}/items")


def occurrence_overlay(node: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in node.items()
        if key.startswith("x-") or key in {"title", "description"}
    }


def source_core(node: dict[str, Any]) -> dict[str, Any]:
    ignored = {"title", "description", "readOnly"}
    return {
        key: value
        for key, value in node.items()
        if key not in ignored and not key.startswith("x-")
    }


def portable_constraint_core(node: dict[str, Any]) -> dict[str, Any]:
    ignored = {"$id", "title", "description", "x-question-id", "x-review-status"}
    return {key: value for key, value in node.items() if key not in ignored}


def normalize_computed(node: Any) -> None:
    if not isinstance(node, dict):
        return
    if "x-source-path" in node and node.get("type") == "number":
        node["type"] = "string"
        node["pattern"] = DECIMAL_PATTERN
        node["minLength"] = 1
        node["maxLength"] = 16
    for child in node.get("properties", {}).values():
        normalize_computed(child)
    if isinstance(node.get("items"), dict):
        normalize_computed(node["items"])


def source_path_index(
    schema: dict[str, Any],
) -> dict[str, tuple[tuple[str, bool], ...]]:
    result: dict[str, tuple[tuple[str, bool], ...]] = {}

    def visit(node: dict[str, Any], path: tuple[tuple[str, bool], ...]) -> None:
        if isinstance(node.get("x-source-path"), str):
            result[node["x-source-path"]] = path
        if node.get("type") == "object":
            for name, child in node.get("properties", {}).items():
                visit(child, path + ((name, False),))
        elif node.get("type") == "array":
            visit(node["items"], path[:-1] + ((path[-1][0], True),))

    visit(schema, ())
    return result


def dotted(path: tuple[tuple[str, bool], ...]) -> str:
    return ".".join(f"{name}[*]" if repeated else name for name, repeated in path)


def compile_calculations(
    schema: dict[str, Any], runtime: dict[str, Any], *, expected: int
) -> dict[str, Any]:
    index = source_path_index(schema)
    result: dict[str, Any] = {}
    compiled = 0
    for rule in runtime["rules"]:
        if (
            rule.get("mechanism") != "calculation"
            or rule.get("execution_class") != "executable"
        ):
            continue
        if rule.get("disposition") != "working" or rule.get("operator") != "sum":
            raise ValueError(f"unsupported executable rule: {rule.get('rule_id')}")
        target_source = rule["target"]["path"]
        target_path = index[target_source]
        target_parent_source = target_source.rsplit(".", 1)[0]
        target_parent_path = target_path[:-1]
        fields: list[str] = []
        for operand in rule["operands"]:
            operand_source = operand["path"]
            operand_path = index[operand_source]
            if rule["instance_scope"] == "same_instance":
                if not operand_source.startswith(target_parent_source + "."):
                    raise ValueError("same-instance operand escapes target")
                fields.append(
                    "@THIS." + dotted(operand_path[len(target_parent_path) :])
                )
            elif rule["instance_scope"] in {
                "all_budget_periods",
                "all_collection_instances",
            }:
                fields.append(dotted(operand_path))
            else:
                raise ValueError(f"unsupported rule scope: {rule['instance_scope']}")
        current = result
        for name, repeated in target_path[:-1]:
            current = current.setdefault(name, {})
            if repeated:
                current["gg_type"] = "array"
        current[target_path[-1][0]] = {
            "gg_pre_population": {
                "rule": "sum_monetary",
                "fields": fields,
                "order": rule["source_index"] + 1,
            }
        }
        compiled += 1
    if compiled != expected:
        raise ValueError(f"expected {expected} executable sums, got {compiled}")
    return result


def form_descriptor(
    *,
    form_key: str,
    schema_id: str,
    metadata: dict[str, Any],
    ui_path: str,
    rules_path: str,
    mappings_path: str,
    bindings: list[dict[str, Any]],
    source_evidence: list[dict[str, Any]],
    supplemental_paths: list[str],
) -> dict[str, Any]:
    return {
        "form_key": form_key,
        "schema_id": schema_id,
        "metadata": metadata,
        "ui": artifact(ui_path),
        "mappings": artifact(mappings_path),
        "rules": artifact(rules_path),
        "question_bindings": bindings,
        "source_evidence": source_evidence,
        "supplemental_evidence": [artifact(path) for path in supplemental_paths],
        "review_boundary": {
            "semantic_mappings": "agent_proposed",
            "published_coverage_eligible": False,
            "production_ready": False,
        },
    }


def main() -> None:
    manifest_path = SPECS / "manifest.json"
    manifest = read_json(manifest_path)
    base_form = next(
        form for form in manifest["forms"] if form["form_key"] == "RRBudget"
    )
    base_schema = read_json(SPECS / "schemas/forms/rr-budget-v3.schema.json")
    base_raw = read_json(ORACLES / "rr-budget-v3.candidate.json")["artifacts"][
        "json_schema"
    ]
    base_bindings = {
        binding["form_pointer"]: binding for binding in base_form["question_bindings"]
    }
    base_raw_nodes = dict(occurrences(base_raw))

    manifest["sources"].update(
        {
            "subaward-source-ledger": {
                "kind": "authoritative_source",
                "repository": "https://github.com/mikec-ai/grants-question-crosswalk.git",
                "revision": CROSSWALK_REVISION,
                "path": "artifacts/proof/grantsgov-RRSubawardBudget30.jsonl",
                "sha256": "4aeab4e8d6dc1161ce2cfae3ffb36b9f5aca53472d9fcfbcdacaf881724a8890",
                "source_version": "RR Subaward Budget 30 3.0; XSD sha256:d5d534326e8f7e4416baf98c95c1f9234c0a23628259ee2d7e3199181a24e08a",
            },
            "mp-budget-source-xsd": {
                "kind": "authoritative_source",
                "repository": "https://github.com/mikec-ai/grants-question-crosswalk.git",
                "revision": CROSSWALK_REVISION,
                "path": "harness/portfolio-ingestion/cache/RR_MP_Budget_3_0-V3.0_F788/RR_MP_Budget_3_0-V3.0.xsd",
                "sha256": "8ee3867971d4030582ff4c4cd906cd1a086c2d2491fb6f05b33cdd07ae435846",
                "source_version": "R&R Multi-Project Budget 3.0",
            },
            "mp-budget-source-dat": {
                "kind": "authoritative_source",
                "repository": "https://github.com/mikec-ai/grants-question-crosswalk.git",
                "revision": CROSSWALK_REVISION,
                "path": "harness/portfolio-ingestion/cache/RR_MP_Budget_3_0-V3.0_F788/RR_MP_Budget_3_0-V3.0_F788.xls",
                "sha256": "1b306bea720d7c470b20b2fb6920c76687479dc1ed468caf6d165c02465d6827",
                "source_version": "R&R Multi-Project Budget 3.0 F788 DAT",
            },
        }
    )

    # Subaward Budget 30: exact base budget payload plus a bounded outer shell.
    sub_candidate = read_json(ORACLES / "rr-subaward-budget30-v3.candidate.json")
    sub_runtime = read_json(ORACLES / "rr-subaward-budget30-v3.runtime-rules.json")
    sub_schema = copy.deepcopy(sub_candidate["artifacts"]["json_schema"])
    sub_schema.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "urn:grants-form-kernel:forms:rr-subaward-budget30:v1",
            "x-portable-form-bundle": "portable-grants-form-bundle/v1",
        }
    )
    nested_prefix = "/properties/budget_attachments/properties/rr_budget_3_0/items"
    nested_source = at_pointer(sub_schema, nested_prefix)
    nested = copy.deepcopy(base_schema)
    for key in (
        "$schema",
        "$id",
        "x-form-id",
        "x-portable-form-bundle",
        "x-portable-profile",
    ):
        nested.pop(key, None)
    for pointer, raw_node in occurrences(nested_source):
        destination = at_pointer(nested, pointer)
        for key, value in occurrence_overlay(raw_node).items():
            destination[key] = value
    replace_pointer(sub_schema, nested_prefix, nested)
    compile_calculations(sub_schema, sub_runtime, expected=30)

    sub_bindings: list[dict[str, Any]] = []
    for pointer, binding in base_bindings.items():
        cloned = copy.deepcopy(binding)
        cloned["binding_id"] = (
            f"binding:rr-subaward-budget30:{binding['binding_id'].split(':')[-1]}"
        )
        cloned["form_pointer"] = nested_prefix + pointer
        cloned["role"] = f"subaward_{binding['role']}"
        cloned["context"] = {
            **binding["context"],
            "outer_repeat_pointer": nested_prefix.rsplit("/items", 1)[0],
            "outer_repeat_max": 30,
            "scope": "subaward_budget",
        }
        cloned["analysis_classification"] = "semantic_question"
        sub_bindings.append(cloned)

    mechanism_id = "capture:attachment:subaward-budget-file"
    mechanism_schema_id = "urn:grants-form-kernel:questions:subaward-budget-file:v1"
    mechanism_path = "schemas/questions/attachments/subaward-budget-file.schema.json"
    mechanism_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": mechanism_schema_id,
        "title": "Subaward budget file",
        "type": "string",
        "x-question-id": mechanism_id,
        "x-analysis-classification": "content_capture_mechanism",
    }
    write_json(SPECS / mechanism_path, mechanism_schema)
    for ordinal in range(1, 31):
        pointer = f"/properties/att_{ordinal}"
        source = at_pointer(sub_schema, pointer)
        replace_pointer(
            sub_schema,
            pointer,
            {"allOf": [{"$ref": mechanism_schema_id}], **occurrence_overlay(source)},
        )
        sub_bindings.append(
            {
                "binding_id": f"binding:rr-subaward-budget30:attachment-{ordinal}",
                "question_id": mechanism_id,
                "schema_id": mechanism_schema_id,
                "form_pointer": pointer,
                "role": "subaward_budget_attachment",
                "cardinality": {"min": 0, "max": 1},
                "context": {"scope": "subaward_collection", "ordinal": ordinal},
                "mapping_refs": {},
                "mapping_status": "agent_proposed",
                "analysis_classification": "content_capture_mechanism",
            }
        )

    sub_schema_path = "schemas/forms/rr-subaward-budget30-v3.schema.json"
    sub_ui_path = "ui/rr-subaward-budget30.ui.json"
    sub_rules_path = "rules/rr-subaward-budget30.rules.json"
    sub_mapping_path = "mappings/rr-subaward-budget30.mappings.json"
    write_json(SPECS / sub_schema_path, sub_schema)
    write_json(
        SPECS / sub_ui_path,
        {"type": "VerticalLayout", "elements": ui_elements(sub_schema)},
    )
    base_rules = read_json(SPECS / "rules/rr-budget-family.rules.json")
    write_json(
        SPECS / sub_rules_path,
        {"budget_attachments": {"rr_budget_3_0": {"gg_type": "array", **base_rules}}},
    )
    write_json(
        SPECS / sub_mapping_path, {"targets": {"common_grants": {"from": {}, "to": {}}}}
    )

    # Multi-project budget: proposed semantic reuse with exact validation variants.
    mp_candidate = read_json(ORACLES / "rr-mp-budget-v3.candidate.json")
    mp_runtime = read_json(ORACLES / "rr-mp-budget-v3.runtime-rules.json")
    mp_schema = copy.deepcopy(mp_candidate["artifacts"]["json_schema"])
    mp_schema.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "urn:grants-form-kernel:forms:rr-mp-budget:v1",
            "x-portable-form-bundle": "portable-grants-form-bundle/v1",
        }
    )
    mp_bindings: list[dict[str, Any]] = []
    variant_descriptors: list[dict[str, Any]] = []
    stale_variant_descriptors = [
        descriptor
        for descriptor in manifest["schemas"]
        if descriptor["artifact"]["path"].startswith("schemas/questions/budget/rr-mp/")
    ]
    for descriptor in stale_variant_descriptors:
        (SPECS / descriptor["artifact"]["path"]).unlink(missing_ok=True)
    stale_variant_ids = {descriptor["id"] for descriptor in stale_variant_descriptors}
    manifest["schemas"] = [
        descriptor
        for descriptor in manifest["schemas"]
        if descriptor["id"] not in stale_variant_ids
    ]
    catalog_by_question: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for descriptor in manifest["schemas"]:
        if descriptor["kind"] != "question":
            continue
        catalog_by_question.setdefault(descriptor["question_id"], []).append(
            (
                descriptor["id"],
                read_json(SPECS / descriptor["artifact"]["path"]),
            )
        )
    exact_reuse = 0
    variants = 0
    for pointer, binding in base_bindings.items():
        raw_base = base_raw_nodes[pointer]
        raw_mp = at_pointer(mp_schema, pointer)
        if source_core(raw_base) == source_core(raw_mp):
            schema_id = binding["schema_id"]
            exact_reuse += 1
        else:
            proposed = portable_leaf(
                raw_mp,
                "urn:comparison-only",
                binding["question_id"],
            )
            reusable = next(
                (
                    candidate_schema_id
                    for candidate_schema_id, candidate in catalog_by_question.get(
                        binding["question_id"], []
                    )
                    if portable_constraint_core(candidate)
                    == portable_constraint_core(proposed)
                ),
                None,
            )
            if reusable is not None:
                schema_id = reusable
            else:
                schema_id = f"{binding['schema_id'].removesuffix(':v1')}:rr-mp:v1"
                suffix = hashlib.sha256(pointer.encode()).hexdigest()[:10]
                filename = (
                    "schemas/questions/budget/rr-mp/"
                    f"{pointer.split('/')[-1]}-{suffix}.schema.json"
                )
                document = portable_leaf(raw_mp, schema_id, binding["question_id"])
                write_json(SPECS / filename, document)
                variant_descriptors.append(
                    {
                        "kind": "question",
                        "id": schema_id,
                        "question_id": binding["question_id"],
                        "artifact": artifact(filename),
                        "source_evidence": ["mp-budget-source-xsd"],
                    }
                )
            variants += 1
        replace_pointer(
            mp_schema,
            pointer,
            {"allOf": [{"$ref": schema_id}], **occurrence_overlay(raw_mp)},
        )
        cloned = copy.deepcopy(binding)
        cloned["binding_id"] = (
            f"binding:rr-mp-budget:{binding['binding_id'].split(':')[-1]}"
        )
        cloned["schema_id"] = schema_id
        cloned["role"] = f"multi_project_{binding['role']}"
        cloned["context"] = {**binding["context"], "scope": "multi_project_budget"}
        cloned["analysis_classification"] = "semantic_question"
        mp_bindings.append(cloned)
    if (exact_reuse, variants) != (87, 14):
        raise ValueError(
            f"unexpected multi-project reuse partition: {(exact_reuse, variants)}"
        )
    normalize_computed(mp_schema)

    mp_schema_path = "schemas/forms/rr-mp-budget-v3.schema.json"
    mp_ui_path = "ui/rr-mp-budget.ui.json"
    mp_rules_path = "rules/rr-mp-budget.rules.json"
    mp_mapping_path = "mappings/rr-mp-budget.mappings.json"
    write_json(SPECS / mp_schema_path, mp_schema)
    write_json(
        SPECS / mp_ui_path,
        {"type": "VerticalLayout", "elements": ui_elements(mp_schema)},
    )
    write_json(
        SPECS / mp_rules_path, compile_calculations(mp_schema, mp_runtime, expected=10)
    )
    write_json(
        SPECS / mp_mapping_path, {"targets": {"common_grants": {"from": {}, "to": {}}}}
    )

    evidence = {
        "contract": "portable-budget-composition-evidence/v1",
        "forms": {
            "RRSubawardBudget30": {
                "source_structural_records": 231,
                "semantic_question_occurrences": 101,
                "content_capture_mechanisms": 30,
                "computed_outputs": 56,
                "exact_budget_payload_reuse": True,
                "outer_budget_instances_max": 30,
                "calculations_projected": 30,
                "conditions_source_bound_not_projected": 20,
            },
            "RRMPBudget": {
                "source_structural_records": 199,
                "semantic_question_occurrences": 101,
                "exact_schema_reuse": 87,
                "validation_profile_variants": 14,
                "validation_variants_reusing_existing_catalog_schemas": 2,
                "new_validation_variant_schemas": 12,
                "computed_outputs": 56,
                "calculations_projected": 10,
                "calculations_preserved_not_projected": 46,
                "conditions_source_bound_not_projected": 55,
            },
        },
        "semantic_identity_status": "agent_proposed",
        "accepted_mappings": 0,
        "published_coverage_eligible": False,
        "xml_projection": "not_available_in_pinned_implementation_oracles",
    }
    evidence_path = "evidence/rr-budget-composition-wave.json"
    write_json(SPECS / evidence_path, evidence)

    # Add source provenance to every reused budget question declaration.
    budget_schema_ids = {binding["schema_id"] for binding in base_bindings.values()}
    for descriptor in manifest["schemas"]:
        if descriptor["id"] in budget_schema_ids:
            for source_ref in ("subaward-source-ledger", "mp-budget-source-xsd"):
                if source_ref not in descriptor["source_evidence"]:
                    descriptor["source_evidence"].append(source_ref)

    new_schema_ids = {
        mechanism_schema_id,
        *[item["id"] for item in variant_descriptors],
    }
    new_schema_ids.update({sub_schema["$id"], mp_schema["$id"]})
    manifest["schemas"] = [
        item for item in manifest["schemas"] if item["id"] not in new_schema_ids
    ]
    manifest["schemas"].append(
        {
            "kind": "question",
            "id": mechanism_schema_id,
            "question_id": mechanism_id,
            "artifact": artifact(mechanism_path),
            "source_evidence": ["subaward-source-ledger"],
        }
    )
    manifest["schemas"].extend(variant_descriptors)
    for schema, path in ((sub_schema, sub_schema_path), (mp_schema, mp_schema_path)):
        manifest["schemas"].append(
            {
                "kind": "form",
                "id": schema["$id"],
                "question_id": None,
                "artifact": artifact(path),
                "source_evidence": [],
            }
        )

    forms = [
        form_descriptor(
            form_key="RRSubawardBudget30",
            schema_id=sub_schema["$id"],
            metadata={
                "form_id": "33ce5425-e8f1-422e-8fe0-e2337adbd56f",
                "legacy_form_id": None,
                "form_name": "[Draft] R&R Subaward Budget Attachment(s) Form 30",
                "short_form_name": "RR_SubawardBudget30_3_0",
                "form_version": "3.0",
                "agency_code": "GRANTS_GOV",
                "omb_number": "4040-0001",
                "form_type": "RRSubawardBudget30",
                "sgg_version": "1.0",
                "is_deprecated": False,
                "form_instruction_id": "1bc60459-7d72-4964-9816-e965b2ba4aec",
            },
            ui_path=sub_ui_path,
            rules_path=sub_rules_path,
            mappings_path=sub_mapping_path,
            bindings=sub_bindings,
            source_evidence=[
                manifest["sources"]["subaward-source-ledger"],
                manifest["sources"]["budget-source-rr-dat"],
            ],
            supplemental_paths=[
                "oracles/budget/rr-subaward-budget30-v3.candidate.json",
                "oracles/budget/rr-subaward-budget30-v3.runtime-rules.json",
                evidence_path,
            ],
        ),
        form_descriptor(
            form_key="RRMPBudget",
            schema_id=mp_schema["$id"],
            metadata={
                "form_id": "955001b0-bade-4ed2-80f1-88630dd8d170",
                "legacy_form_id": None,
                "form_name": "[Draft] Research & Related Multi-Project Budget Form",
                "short_form_name": "RR_MP_Budget_3_0",
                "form_version": "3.0",
                "agency_code": "GRANTS_GOV",
                "omb_number": "4040-0001",
                "form_type": "RRMPBudget",
                "sgg_version": "1.0",
                "is_deprecated": False,
                "form_instruction_id": "f1bfa235-b36e-4b00-bc8b-ea9bb0a970e4",
            },
            ui_path=mp_ui_path,
            rules_path=mp_rules_path,
            mappings_path=mp_mapping_path,
            bindings=mp_bindings,
            source_evidence=[
                manifest["sources"]["mp-budget-source-xsd"],
                manifest["sources"]["mp-budget-source-dat"],
            ],
            supplemental_paths=[
                "oracles/budget/rr-mp-budget-v3.candidate.json",
                "oracles/budget/rr-mp-budget-v3.runtime-rules.json",
                evidence_path,
            ],
        ),
    ]
    manifest["forms"] = [
        form
        for form in manifest["forms"]
        if form["form_key"] not in {item["form_key"] for item in forms}
    ] + forms
    manifest["bundle"]["version"] = "0.7.0"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def cli(argv: list[str]) -> int:
    if argv in (["--version"], ["-v"], ["-V"]):
        sys.stdout.write(f"{VERSION}\n")
        return 0
    if argv == ["--help"]:
        sys.stdout.write(
            "usage: python scripts/build_portable_budget_composition.py [--help | --version]\n"
        )
        return 0
    if argv:
        sys.stdout.write(
            "error:\n"
            "  code: usage\n"
            f"  message: unknown argument: {argv[0]}\n"
            "help:\n"
            "  command: python scripts/build_portable_budget_composition.py --help\n"
        )
        return 2
    try:
        main()
    except (KeyError, OSError, TypeError, ValueError) as exc:
        sys.stdout.write(f"error:\n  code: build_failed\n  message: {exc}\n")
        return 1
    sys.stdout.write(
        "build:\n"
        "  status: generated\n"
        "  forms: 2\n"
        "  semantic_questions_each: 101\n"
        "  subaward_mechanisms: 30\n"
        "  multi_project_schema_variants: 14\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
