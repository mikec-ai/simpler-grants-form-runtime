#!/usr/bin/env python3
"""Build the declarative R&R Budget profiles from pinned implementation oracles.

The emitted JSON is the runtime input. This builder performs deterministic migration and
verification only; no budget-specific code is imported by the Simpler runtime adapter.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, TypedDict

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "form-specs"
ORACLES = SPECS / "oracles" / "budget"
QUESTION_DIR = SPECS / "schemas" / "questions" / "budget"

DECIMAL_PATTERN = r"^-?(?:\d{1,14}|\d{1,13}[.]\d|\d{1,12}[.]\d{2})$"
IMPLEMENTATION_REVISION = "51f76027d560353531db161040431d3138c71ca3"
CROSSWALK_REVISION = "dfe9e47ffd6a25c967b8ed38703480ccdc15a8ef"
VERSION = "0.1.0"
HELP = """build-portable-budget-pilot
description: Regenerate the two declarative R&R Budget profiles from pinned evidence.
usage: python scripts/build_portable_budget_pilot.py [--help | --version]

flags:
  --help       Show this reference and exit.
  --version    Show the builder version and exit.
"""

SHARED_QUESTION_IDENTITIES = {
    "OrganizationName": (
        "question:organization:legal-name",
        "urn:grants-form-kernel:questions:organization:legal-name:v1",
    ),
    "BudgetYear.KeyPersons.KeyPerson.Name.FirstName": (
        "question:person:name:first",
        "urn:grants-form-kernel:questions:person-name-first:v1",
    ),
    "BudgetYear.KeyPersons.KeyPerson.Name.MiddleName": (
        "question:person:name:middle",
        "urn:grants-form-kernel:questions:person-name-middle:v1",
    ),
    "BudgetYear.KeyPersons.KeyPerson.Name.LastName": (
        "question:person:name:last",
        "urn:grants-form-kernel:questions:person-name-last:v1",
    ),
}

SHARED_SEMANTIC_IDENTITIES = {
    "BudgetYear.KeyPersons.KeyPerson.Name.PrefixName": "question:person:name:prefix",
    "BudgetYear.KeyPersons.KeyPerson.Name.SuffixName": "question:person:name:suffix",
}


class ProfileConfig(TypedDict):
    candidate: str
    runtime: str
    schema: str
    mappings: str
    form_id: str
    legacy_form_id: int | None
    form_name: str
    short_form_name: str
    form_type: str
    instruction_id: str
    periods: int
    source_prefix: str
    xsd_source: str
    source_evidence: list[str]


PROFILES: dict[str, ProfileConfig] = {
    "RRBudget": {
        "candidate": "rr-budget-v3.candidate.json",
        "runtime": "rr-budget-v3.runtime-rules.json",
        "schema": "schemas/forms/rr-budget-v3.schema.json",
        "mappings": "mappings/rr-budget-v3.mappings.json",
        "form_id": "cfa593f7-e5ef-4ba8-82b2-c732ec65e461",
        "legacy_form_id": None,
        "form_name": "[Draft] Research & Related Budget",
        "short_form_name": "RR_Budget_3_0",
        "form_type": "RRBudget",
        "instruction_id": "6c604b81-8582-4d39-b899-f3e15bbcd3ef",
        "periods": 5,
        "source_prefix": "RR_Budget_3_0",
        "xsd_source": "budget-source-rr-xsd",
        "source_evidence": ["budget-source-rr-xsd", "budget-source-rr-dat"],
    },
    "RRBudget10": {
        "candidate": "rr-budget10-v3.candidate.json",
        "runtime": "rr-budget10-v3.runtime-rules.json",
        "schema": "schemas/forms/rr-budget10-v3.schema.json",
        "mappings": "mappings/rr-budget10-v3.mappings.json",
        "form_id": "2ae77c1c-58f7-41e7-9fb0-7a0823621758",
        "legacy_form_id": None,
        "form_name": "[Draft] Research & Related Budget 10YR",
        "short_form_name": "RR_Budget10_3_0",
        "form_type": "RRBudget10",
        "instruction_id": "6436c11c-0756-4806-885f-819d21ffe914",
        "periods": 10,
        "source_prefix": "RR_Budget10_3_0",
        "xsd_source": "budget-source-rr10-xsd",
        "source_evidence": [
            "budget-source-rr10-xsd",
            "budget-source-rr-dat",
        ],
    },
}


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(path: str) -> dict[str, str]:
    return {"path": path, "sha256": digest(SPECS / path)}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalized_source_path(source_path: str, prefix: str) -> str:
    expected = f"{prefix}."
    if not source_path.startswith(expected):
        raise ValueError(f"source path does not start with {prefix}: {source_path}")
    return source_path[len(expected) :]


def iter_leaf_nodes(
    node: dict[str, Any],
    *,
    pointer: str = "",
    required: bool = True,
    repeat_pointers: tuple[str, ...] = (),
) -> list[tuple[str, dict[str, Any], bool, tuple[str, ...]]]:
    result: list[tuple[str, dict[str, Any], bool, tuple[str, ...]]] = []
    node_type = node.get("type")
    if "x-question-key" in node:
        return [(pointer, node, required, repeat_pointers)]
    if node_type == "object":
        required_names = set(node.get("required", []))
        for name, child in node.get("properties", {}).items():
            result.extend(
                iter_leaf_nodes(
                    child,
                    pointer=f"{pointer}/properties/{name}",
                    required=name in required_names,
                    repeat_pointers=repeat_pointers,
                )
            )
    elif node_type == "array":
        repeat_pointer = pointer
        result.extend(
            iter_leaf_nodes(
                node["items"],
                pointer=f"{pointer}/items",
                required=required,
                repeat_pointers=repeat_pointers + (repeat_pointer,),
            )
        )
    return result


def portable_leaf(
    node: dict[str, Any], schema_id: str, question_id: str
) -> dict[str, Any]:
    result = {
        key: copy.deepcopy(value)
        for key, value in node.items()
        if not key.startswith("x-") and key != "readOnly"
    }
    if result.get("type") == "number":
        result["type"] = "string"
        result["pattern"] = DECIMAL_PATTERN
        result["minLength"] = 1
        result["maxLength"] = 16
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_id,
        **result,
        "x-question-id": question_id,
    }


def question_identity(node: dict[str, Any], prefix: str) -> tuple[str, str, str | None]:
    source_path = normalized_source_path(node["x-source-path"], prefix)
    if source_path in SHARED_QUESTION_IDENTITIES:
        question_id, schema_id = SHARED_QUESTION_IDENTITIES[source_path]
        return question_id, schema_id, None
    question_id = SHARED_SEMANTIC_IDENTITIES.get(
        source_path, f"question:budget:{slug(source_path)}"
    )
    schema_id = f"urn:grants-form-kernel:questions:budget:{slug(source_path)}:v1"
    filename = f"{slug(source_path)}.schema.json"
    return question_id, schema_id, filename


def replace_input_leaves(
    node: dict[str, Any],
    *,
    prefix: str,
    questions: dict[str, tuple[str, str | None, dict[str, Any]]],
) -> None:
    if "x-question-key" in node:
        if node.get("x-interaction") != "input":
            if node.get("type") == "number":
                node["type"] = "string"
                node["pattern"] = DECIMAL_PATTERN
                node["minLength"] = 1
                node["maxLength"] = 16
            return
        question_id, schema_id, filename = question_identity(node, prefix)
        portable = portable_leaf(node, schema_id, question_id)
        existing = questions.get(question_id)
        comparable = {key: value for key, value in portable.items() if key != "$id"}
        if existing is not None:
            existing_comparable = {
                key: value for key, value in existing[2].items() if key != "$id"
            }
            if comparable != existing_comparable:
                raise ValueError(
                    f"question constraint drift across profiles: {question_id}"
                )
        else:
            questions[question_id] = (schema_id, filename, portable)
        occurrence = {
            key: copy.deepcopy(value)
            for key, value in node.items()
            if key.startswith("x-") or key in {"title", "description"}
        }
        node.clear()
        node.update({"allOf": [{"$ref": schema_id}], **occurrence})
        return
    if node.get("type") == "object":
        for child in node.get("properties", {}).values():
            replace_input_leaves(child, prefix=prefix, questions=questions)
    elif node.get("type") == "array":
        replace_input_leaves(node["items"], prefix=prefix, questions=questions)


def role_for(source_path: str) -> str:
    if ".KeyPersons.KeyPerson." in source_path:
        return "key_person"
    if (
        ".OtherPersonnel.ProjectRole" in source_path
        or ".OtherPersonnel.NumberPersonnel" in source_path
    ):
        return "other_personnel_category"
    if source_path.endswith(".OrganizationName") or source_path.endswith(".SAMUEI"):
        return "applicant_organization"
    return "applicant_budget"


def bindings_for(
    schema: dict[str, Any], prefix: str, form_key: str
) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for pointer, node, required, repeats in iter_leaf_nodes(schema):
        if node.get("x-interaction") != "input":
            continue
        question_id, schema_id, _filename = question_identity(node, prefix)
        normalized = normalized_source_path(node["x-source-path"], prefix)
        bindings.append(
            {
                "binding_id": f"binding:{slug(form_key)}:{slug(normalized)}",
                "question_id": question_id,
                "schema_id": schema_id,
                "form_pointer": pointer,
                "role": role_for(node["x-source-path"]),
                "cardinality": {"min": 1 if required else 0, "max": 1},
                "context": {
                    "scope": "budget",
                    "repetition": "nested" if repeats else "single",
                    "repeat_pointer": repeats[-1] if repeats else None,
                    "repeat_ancestors": list(repeats),
                },
                "mapping_refs": {},
                "mapping_status": "agent_proposed",
            }
        )
    return bindings


def ui_elements(
    node: dict[str, Any], base: str = "#/properties"
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if node.get("type") != "object":
        raise ValueError("UI object expected")
    for name, child in node.get("properties", {}).items():
        scope = f"{base}/{name}"
        if child.get("type") == "array":
            result.append(
                {
                    "type": "Control",
                    "scope": scope,
                    "label": child.get("title", name.replace("_", " ").title()),
                    "options": {
                        "itemLabel": child.get("title", name.replace("_", " ").title()),
                        "detail": {
                            "type": "VerticalLayout",
                            "elements": ui_elements(child["items"]),
                        },
                    },
                }
            )
        elif child.get("type") == "object":
            result.append(
                {
                    "type": "Group",
                    "label": child.get("title", name.replace("_", " ").title()),
                    "elements": ui_elements(child, base=scope + "/properties"),
                }
            )
        else:
            options = {"simpler": {"type": "null"}} if child.get("readOnly") else None
            control: dict[str, Any] = {"type": "Control", "scope": scope}
            if options:
                control["options"] = options
            result.append(control)
    return result


def source_path_index(
    schema: dict[str, Any],
) -> dict[str, tuple[tuple[str, bool], ...]]:
    result: dict[str, tuple[tuple[str, bool], ...]] = {}

    def visit(node: dict[str, Any], path: tuple[tuple[str, bool], ...]) -> None:
        source_path = node.get("x-source-path")
        if isinstance(source_path, str):
            result[source_path] = path
        if node.get("type") == "object":
            for name, child in node.get("properties", {}).items():
                visit(child, path + ((name, False),))
        elif node.get("type") == "array":
            visit(node["items"], path[:-1] + ((path[-1][0], True),))

    visit(schema, ())
    return result


def dotted(path: tuple[tuple[str, bool], ...]) -> str:
    return ".".join(f"{name}[*]" if repeated else name for name, repeated in path)


def compile_rules(schema: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
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
            elif rule["instance_scope"] == "all_budget_periods":
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
    if compiled != 30:
        raise ValueError(f"expected 30 executable sums, got {compiled}")
    return result


def main() -> None:
    manifest_path = SPECS / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"].update(
        {
            "budget-source-rr-xsd": {
                "kind": "authoritative_source",
                "repository": "https://github.com/mikec-ai/grants-question-crosswalk.git",
                "revision": CROSSWALK_REVISION,
                "path": "work/grantsgov-xsds/RR_Budget_3_0-V3.0.xsd",
                "sha256": "d474010f85819549990de65fc51292bed08ba98ac0895d0dde9513fbe855cdbc",
                "source_version": "R&R Budget 3.0",
            },
            "budget-source-rr10-xsd": {
                "kind": "authoritative_source",
                "repository": "https://github.com/mikec-ai/grants-question-crosswalk.git",
                "revision": CROSSWALK_REVISION,
                "path": "work/grantsgov-xsds/RR_Budget10_3_0-V3.0.xsd",
                "sha256": "cccce03554424d59b5958e4443a54db12a5a10780fbdc5df2ec25955d443fc9d",
                "source_version": "R&R Budget 10 3.0",
            },
            "budget-source-rr-dat": {
                "kind": "authoritative_source",
                "repository": "https://github.com/mikec-ai/grants-question-crosswalk.git",
                "revision": CROSSWALK_REVISION,
                "path": "work/form-metadata/RR_Budget_3_0-V3.0_F770.xls",
                "sha256": "c85158ce7ddcc756d6e8a55a050e00b4a95cdfc8d9a2d91b7bd94c7f8bdb1035",
                "source_version": "R&R Budget 3.0 F770 DAT",
            },
        }
    )
    questions: dict[str, tuple[str, str | None, dict[str, Any]]] = {}
    generated_forms: list[dict[str, Any]] = []
    shared_ui: dict[str, Any] | None = None
    shared_rules: dict[str, Any] | None = None
    profile_summary: list[dict[str, Any]] = []

    for form_key, profile in PROFILES.items():
        candidate = json.loads(
            (ORACLES / profile["candidate"]).read_text(encoding="utf-8")
        )
        runtime = json.loads((ORACLES / profile["runtime"]).read_text(encoding="utf-8"))
        source_schema = candidate["artifacts"]["json_schema"]
        leaves = iter_leaf_nodes(source_schema)
        if len(leaves) != 157:
            raise ValueError(f"{form_key} expected 157 structural leaves")
        inputs = [row for row in leaves if row[1].get("x-interaction") == "input"]
        computed = [row for row in leaves if row[1].get("x-interaction") == "computed"]
        if (len(inputs), len(computed)) != (101, 56):
            raise ValueError(f"{form_key} input/output accounting drift")

        bindings = bindings_for(source_schema, profile["source_prefix"], form_key)
        schema = copy.deepcopy(source_schema)
        schema["$id"] = f"urn:grants-form-kernel:forms:{slug(form_key)}:v3"
        schema["title"] = profile["form_name"]
        schema["x-portable-template"] = "profile:rr-budget-family:v1"
        schema["x-portable-profile"] = {
            "form_key": form_key,
            "budget_periods": profile["periods"],
        }
        replace_input_leaves(
            schema, prefix=profile["source_prefix"], questions=questions
        )
        if schema["properties"]["budget_year"]["maxItems"] != profile["periods"]:
            raise ValueError(f"{form_key} budget period drift")
        write_json(SPECS / profile["schema"], schema)

        profile_ui = {
            "type": "VerticalLayout",
            "elements": [
                {
                    "type": "Group",
                    "label": "Budget",
                    "elements": ui_elements(source_schema),
                }
            ],
        }
        if shared_ui is None:
            shared_ui = profile_ui
        elif profile_ui != shared_ui:
            raise ValueError("budget profiles require different UI declarations")

        rules = compile_rules(source_schema, runtime)
        if shared_rules is None:
            shared_rules = rules
        elif rules != shared_rules:
            raise ValueError("budget profiles require different executable rule graphs")

        mappings: dict[str, Any] = {
            "targets": {"common_grants": {"from": {}, "to": {}}}
        }
        write_json(SPECS / profile["mappings"], mappings)
        generated_forms.append(
            {
                "form_key": form_key,
                "schema_id": schema["$id"],
                "metadata": {
                    "form_id": profile["form_id"],
                    "legacy_form_id": profile["legacy_form_id"],
                    "form_name": profile["form_name"],
                    "short_form_name": profile["short_form_name"],
                    "form_version": "3.0",
                    "agency_code": "GRANTS_GOV",
                    "omb_number": "4040-0001",
                    "form_type": profile["form_type"],
                    "sgg_version": "1.0",
                    "is_deprecated": False,
                    "form_instruction_id": profile["instruction_id"],
                },
                "ui": {"path": "ui/rr-budget-family.ui.json", "sha256": "pending"},
                "mappings": artifact(profile["mappings"]),
                "rules": {
                    "path": "rules/rr-budget-family.rules.json",
                    "sha256": "pending",
                },
                "question_bindings": bindings,
                "source_evidence": [
                    manifest["sources"][key] for key in profile["source_evidence"]
                ],
                "supplemental_evidence": [
                    artifact(f"oracles/budget/{profile['candidate']}"),
                    artifact(f"oracles/budget/{profile['runtime']}"),
                    {
                        "path": "evidence/rr-budget-family-profile.json",
                        "sha256": "pending",
                    },
                ],
                "review_boundary": {
                    "semantic_mappings": "agent_proposed",
                    "published_coverage_eligible": False,
                    "production_ready": False,
                },
            }
        )
        profile_summary.append(
            {
                "form_key": form_key,
                "structural_leaves": len(leaves),
                "applicant_inputs": len(inputs),
                "computed_outputs": len(computed),
                "budget_periods": profile["periods"],
                "question_bindings": len(bindings),
                "executable_calculations": 30,
                "blocked_calculations": 26,
            }
        )

    assert shared_ui is not None
    assert shared_rules is not None
    write_json(SPECS / "ui" / "rr-budget-family.ui.json", shared_ui)
    write_json(SPECS / "rules" / "rr-budget-family.rules.json", shared_rules)

    question_descriptors: list[dict[str, Any]] = []
    exact_shared_ids = {
        schema_id for _, schema_id in SHARED_QUESTION_IDENTITIES.values()
    }
    for descriptor in manifest["schemas"]:
        if descriptor["id"] in exact_shared_ids:
            for source_ref in ("budget-source-rr-xsd", "budget-source-rr10-xsd"):
                if source_ref not in descriptor["source_evidence"]:
                    descriptor["source_evidence"].append(source_ref)

    for question_id, (schema_id, filename, document) in sorted(questions.items()):
        if filename is None:
            existing = next(
                item for item in manifest["schemas"] if item["id"] == schema_id
            )
            existing_document = json.loads(
                (SPECS / existing["artifact"]["path"]).read_text(encoding="utf-8")
            )
            ignored = {"$id", "title", "description", "x-review-status"}
            expected = {k: v for k, v in document.items() if k not in ignored}
            actual = {k: v for k, v in existing_document.items() if k not in ignored}
            if expected != actual:
                raise ValueError(f"shared question constraint drift: {question_id}")
            continue
        path = QUESTION_DIR / filename
        write_json(path, document)
        question_descriptors.append(
            {
                "kind": "question",
                "id": schema_id,
                "question_id": question_id,
                "artifact": artifact(str(path.relative_to(SPECS))),
                "source_evidence": ["budget-source-rr-xsd", "budget-source-rr10-xsd"],
            }
        )

    evidence = {
        "contract": "portable-budget-family-profile-evidence/v1",
        "implementation_oracle_revision": IMPLEMENTATION_REVISION,
        "template": {
            "profile_id": "profile:rr-budget-family:v1",
            "shared_question_count": len(questions),
            "shared_ui": True,
            "shared_executable_rule_graph": True,
            "only_runtime_parameter": "budget_year.maxItems",
        },
        "profiles": profile_summary,
        "source_question_count_discrepancy": {
            "previous_semantic_counts": {"RRBudget": 97, "RRBudget10": 107},
            "structural_applicant_input_count_each": 101,
            "resolution": "portable declarations classify identical input structure consistently; semantic acceptance remains agent_proposed",
        },
        "behavior_boundary": {
            "source_calculations_each": 56,
            "executable_exact_sums_each": 30,
            "blocked_each": 26,
            "rr_budget10_target_dat_parity": "not_established_in_pinned_evidence",
        },
        "runtime_boundaries": {
            "attachment_fields": (
                "portable scalar declarations only; attachment upload/runtime parity "
                "is not established"
            ),
            "nested_repeating_ui": (
                "generic structural projection; exact native custom-widget parity is not claimed"
            ),
        },
        "xml_projection": "not_available_in_pinned_implementation_oracle",
        "accepted_mappings": 0,
        "published_coverage_eligible": False,
    }
    write_json(SPECS / "evidence" / "rr-budget-family-profile.json", evidence)

    # Refresh descriptors now that shared artifacts and evidence exist.
    for form in generated_forms:
        form["ui"] = artifact("ui/rr-budget-family.ui.json")
        form["rules"] = artifact("rules/rr-budget-family.rules.json")
        form["supplemental_evidence"][-1] = artifact(
            "evidence/rr-budget-family-profile.json"
        )

    budget_schema_ids = {item["id"] for item in question_descriptors} | {
        form["schema_id"] for form in generated_forms
    }
    obsolete_shared_paths = {
        QUESTION_DIR / "organizationname.schema.json",
        QUESTION_DIR / "budgetyear-keypersons-keyperson-name-firstname.schema.json",
        QUESTION_DIR / "budgetyear-keypersons-keyperson-name-middlename.schema.json",
        QUESTION_DIR / "budgetyear-keypersons-keyperson-name-lastname.schema.json",
    }
    obsolete_shared_ids = {
        "urn:grants-form-kernel:questions:budget:organizationname:v1",
        "urn:grants-form-kernel:questions:budget:budgetyear-keypersons-keyperson-name-firstname:v1",
        "urn:grants-form-kernel:questions:budget:budgetyear-keypersons-keyperson-name-middlename:v1",
        "urn:grants-form-kernel:questions:budget:budgetyear-keypersons-keyperson-name-lastname:v1",
    }
    budget_schema_ids.update(obsolete_shared_ids)
    for path in obsolete_shared_paths:
        path.unlink(missing_ok=True)
    manifest["schemas"] = [
        item for item in manifest["schemas"] if item["id"] not in budget_schema_ids
    ]
    manifest["schemas"].extend(question_descriptors)
    for form in generated_forms:
        manifest["schemas"].append(
            {
                "kind": "form",
                "id": form["schema_id"],
                "question_id": None,
                "artifact": artifact(PROFILES[form["form_key"]]["schema"]),
                "source_evidence": [],
            }
        )
    manifest["forms"] = [
        item for item in manifest["forms"] if item["form_key"] not in PROFILES
    ] + generated_forms
    manifest["bundle"]["version"] = "0.6.0"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def cli(argv: list[str]) -> int:
    if argv in (["--version"], ["-v"], ["-V"]):
        sys.stdout.write(f"{VERSION}\n")
        return 0
    if argv == ["--help"]:
        sys.stdout.write(HELP)
        return 0
    if argv:
        sys.stdout.write(
            "error:\n"
            "  code: usage\n"
            f"  message: unknown argument: {argv[0]}\n"
            "help:\n"
            "  command: python scripts/build_portable_budget_pilot.py --help\n"
        )
        return 2
    try:
        main()
    except (KeyError, OSError, TypeError, ValueError) as exc:
        sys.stdout.write(
            "error:\n"
            "  code: build_failed\n"
            f"  message: {exc}\n"
            "help:\n"
            "  action: restore the pinned artifact or update its declared profile evidence\n"
        )
        return 1
    sys.stdout.write(
        "build:\n  status: generated\n  forms: 2\n  shared_questions: 101\n  executable_rules: 30\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
