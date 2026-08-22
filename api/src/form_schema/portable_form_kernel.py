"""Dependency-neutral validation and analysis for portable form declarations."""

from __future__ import annotations

import dataclasses
import hashlib
import itertools
import json
import re
import uuid
from pathlib import Path
from typing import Any

import jsonref
import jsonschema

CONTRACT = "portable-grants-form-bundle/v1"
MAPPING_STATES = {
    "agent_proposed",
    "agent_reviewed",
    "human_reviewed",
    "accepted",
    "rejected",
    "superseded",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")


class PortableFormKernelError(ValueError):
    """Raised when portable declarations are incomplete or inconsistent."""


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PortableFormKernelError(f"{label} must be an object with string keys")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PortableFormKernelError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PortableFormKernelError(f"{label} must be a non-empty string")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise PortableFormKernelError(
            f"{label} has invalid keys; "
            f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )


def _safe_path(root: Path, raw: object, label: str) -> Path:
    relative = Path(_string(raw, label))
    if relative.is_absolute() or ".." in relative.parts:
        raise PortableFormKernelError(f"{label} must remain inside the portable bundle")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise PortableFormKernelError(f"{label} does not identify a bundle file: {relative}")
    return path


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortableFormKernelError(f"could not read {label}: {path}") from exc


def _read_hashed_json(root: Path, descriptor: object, label: str) -> tuple[Path, object]:
    value = _object(descriptor, label)
    _exact_keys(value, {"path", "sha256"}, label)
    path = _safe_path(root, value["path"], f"{label}.path")
    expected = _string(value["sha256"], f"{label}.sha256")
    if not _SHA256.fullmatch(expected):
        raise PortableFormKernelError(f"{label}.sha256 must be a lowercase SHA-256 digest")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise PortableFormKernelError(
            f"{label}.sha256 does not match {value['path']}: expected {expected}, got {actual}"
        )
    return path, _read_json(path, label)


def _resolve_pointer(document: object, pointer: str, label: str) -> object:
    if not pointer.startswith("/"):
        raise PortableFormKernelError(f"{label} must be an absolute JSON pointer")
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise PortableFormKernelError(f"{label} does not resolve: {pointer}")
        current = current[token]
    return current


def _escape_pointer(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _question_references(
    value: object,
    question_schema_ids: set[str],
    pointer: str = "",
) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str) and reference in question_schema_ids:
            references.append((f"{pointer}/$ref", reference))
        for key, child in value.items():
            if key != "$ref":
                references.extend(
                    _question_references(
                        child,
                        question_schema_ids,
                        f"{pointer}/{_escape_pointer(key)}",
                    )
                )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            references.extend(
                _question_references(child, question_schema_ids, f"{pointer}/{index}")
            )
    return references


def _references(value: object) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str):
            references.append(reference)
        for key, child in value.items():
            if key != "$ref":
                references.extend(_references(child))
    elif isinstance(value, list):
        for child in value:
            references.extend(_references(child))
    return references


def _validate_source_evidence(value: object, label: str) -> None:
    source = _object(value, label)
    _exact_keys(
        source,
        {
            "kind",
            "repository",
            "revision",
            "path",
            "sha256",
            "source_version",
        },
        label,
    )
    if source["kind"] not in {
        "authoritative_source",
        "implementation_oracle",
        "agent_derivation",
    }:
        raise PortableFormKernelError(f"{label}.kind is unknown")
    _string(source["repository"], f"{label}.repository")
    revision = _string(source["revision"], f"{label}.revision")
    if not _REVISION.fullmatch(revision):
        raise PortableFormKernelError(f"{label}.revision must be a full lowercase git SHA")
    path = Path(_string(source["path"], f"{label}.path"))
    if path.is_absolute() or ".." in path.parts:
        raise PortableFormKernelError(f"{label}.path must be repository-relative")
    digest = _string(source["sha256"], f"{label}.sha256")
    if not _SHA256.fullmatch(digest):
        raise PortableFormKernelError(f"{label}.sha256 must be a lowercase SHA-256 digest")
    _string(source["source_version"], f"{label}.source_version")


def _validate_cardinality(value: object, label: str) -> None:
    cardinality = _object(value, label)
    _exact_keys(cardinality, {"min", "max"}, label)
    minimum = cardinality["min"]
    maximum = cardinality["max"]
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
        raise PortableFormKernelError(f"{label}.min must be a nonnegative integer")
    if maximum is not None and (
        not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < minimum
    ):
        raise PortableFormKernelError(f"{label}.max must be null or an integer >= min")


@dataclasses.dataclass(frozen=True)
class PortableFormDeclaration:
    definition: dict[str, Any]
    schema: dict[str, Any]
    ui: dict[str, Any]
    mappings: dict[str, Any]
    rules: dict[str, Any] | None


@dataclasses.dataclass(frozen=True)
class PortableFormKernel:
    """Verified declarations usable without importing Simpler application code."""

    root: Path
    manifest: dict[str, Any]
    schemas_by_id: dict[str, dict[str, Any]]
    forms_by_key: dict[str, PortableFormDeclaration]
    compatibility_records: tuple[dict[str, Any], ...]
    dependency_paths: tuple[Path, ...]
    bundle_digest: str

    def resolved_schema(self, form_key: str) -> dict[str, Any]:
        if form_key not in self.forms_by_key:
            raise PortableFormKernelError(f"unknown portable form_key: {form_key}")

        def loader(uri: str, **_kwargs: object) -> object:
            if uri not in self.schemas_by_id:
                raise PortableFormKernelError(f"schema reference is not in the bundle: {uri}")
            return self.schemas_by_id[uri]

        try:
            resolved = jsonref.replace_refs(
                self.forms_by_key[form_key].schema,
                loader=loader,
                lazy_load=False,
                proxies=False,
                jsonschema=True,
            )
        except (jsonref.JsonRefError, ValueError) as exc:
            raise PortableFormKernelError("could not resolve the form schema graph") from exc
        return _object(resolved, "resolved_schema")

    def analysis_projection(self) -> dict[str, Any]:
        associations: list[dict[str, Any]] = []
        form_questions: dict[str, set[str]] = {}
        accepted_mappings = 0
        for form_key, portable in sorted(self.forms_by_key.items()):
            question_ids: set[str] = set()
            targets = portable.mappings["targets"]
            for binding in portable.definition["question_bindings"]:
                question_id = binding["question_id"]
                question_ids.add(question_id)
                if binding["mapping_status"] == "accepted":
                    accepted_mappings += 1
                xml_ref = binding["mapping_refs"].get("grants_gov_xml")
                xml = (
                    targets["grants_gov_xml"]["bindings"][xml_ref] if xml_ref is not None else None
                )
                associations.append(
                    {
                        "binding_id": binding["binding_id"],
                        "form_key": form_key,
                        "question_id": question_id,
                        "role": binding["role"],
                        "form_pointer": binding["form_pointer"],
                        "cardinality": binding["cardinality"],
                        "context": binding["context"],
                        "mapping_status": binding["mapping_status"],
                        "xml_path": xml["path"] if xml is not None else None,
                        "type_source": xml["type_source"] if xml is not None else None,
                        "type": xml["type"] if xml is not None else None,
                        "xsd_source": xml["xsd_source"] if xml is not None else None,
                    }
                )
            form_questions[form_key] = question_ids

        question_counts: dict[str, int] = {}
        for question_ids in form_questions.values():
            for question_id in question_ids:
                question_counts[question_id] = question_counts.get(question_id, 0) + 1

        pairwise: list[dict[str, Any]] = []
        for form_a, form_b in itertools.combinations(sorted(form_questions), 2):
            questions_a = form_questions[form_a]
            questions_b = form_questions[form_b]
            common = questions_a & questions_b
            union = questions_a | questions_b
            pairwise.append(
                {
                    "form_a": form_a,
                    "form_b": form_b,
                    "questions_in_common": len(common),
                    "unique_questions": len(union),
                    "similarity": len(common) / len(union) if union else 0.0,
                    "form_a_coverage": len(common) / len(questions_a) if questions_a else 0.0,
                    "form_b_coverage": len(common) / len(questions_b) if questions_b else 0.0,
                }
            )

        return {
            "contract": "portable-grants-form-analysis/v1",
            "bundle_digest": self.bundle_digest,
            "summary": {
                "forms": len(form_questions),
                "unique_questions": len(question_counts),
                "associations": len(associations),
                "accepted_mappings": accepted_mappings,
            },
            "questions": [
                {"question_id": question_id, "form_count": count}
                for question_id, count in sorted(question_counts.items())
            ],
            "form_question_associations": associations,
            "pairwise_form_overlap": pairwise,
        }


def load_portable_form_kernel(root: Path) -> PortableFormKernel:
    """Verify a self-contained portable bundle without a Simpler checkout."""

    root = root.resolve()
    manifest_path = _safe_path(root, "manifest.json", "manifest")
    manifest = _object(_read_json(manifest_path, "manifest"), "manifest")
    _exact_keys(
        manifest,
        {"contract", "bundle", "schemas", "compatibility", "forms"},
        "manifest",
    )
    if manifest["contract"] != CONTRACT:
        raise PortableFormKernelError(f"manifest.contract must equal {CONTRACT}")
    bundle = _object(manifest["bundle"], "bundle")
    _exact_keys(bundle, {"name", "version"}, "bundle")
    _string(bundle["name"], "bundle.name")
    _string(bundle["version"], "bundle.version")

    dependencies: set[Path] = {manifest_path}
    schemas_by_id: dict[str, dict[str, Any]] = {}
    schema_kinds: dict[str, str] = {}
    question_ids: dict[str, str] = {}
    for index, raw_schema in enumerate(_array(manifest["schemas"], "schemas")):
        label = f"schemas[{index}]"
        descriptor = _object(raw_schema, label)
        _exact_keys(descriptor, {"kind", "id", "question_id", "artifact"}, label)
        kind = _string(descriptor["kind"], f"{label}.kind")
        if kind not in {"question", "form"}:
            raise PortableFormKernelError(f"{label}.kind is unknown")
        schema_id = _string(descriptor["id"], f"{label}.id")
        if schema_id in schemas_by_id:
            raise PortableFormKernelError(f"duplicate schema id: {schema_id}")
        path, raw_document = _read_hashed_json(root, descriptor["artifact"], f"{label}.artifact")
        dependencies.add(path)
        document = _object(raw_document, f"{label}.document")
        if document.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise PortableFormKernelError(f"{label} must declare JSON Schema Draft 2020-12")
        if document.get("$id") != schema_id:
            raise PortableFormKernelError(f"{label}.id does not match the schema $id")
        try:
            jsonschema.Draft202012Validator.check_schema(document)
        except jsonschema.SchemaError as exc:
            raise PortableFormKernelError(f"{label} is not valid JSON Schema") from exc
        question_id = descriptor["question_id"]
        if kind == "question":
            question_id = _string(question_id, f"{label}.question_id")
            if document.get("x-question-id") != question_id:
                raise PortableFormKernelError(
                    f"{label}.question_id does not match schema x-question-id"
                )
            if question_id in question_ids:
                raise PortableFormKernelError(f"duplicate question id: {question_id}")
            question_ids[question_id] = schema_id
        elif question_id is not None:
            raise PortableFormKernelError(f"{label}.question_id must be null for form schemas")
        schemas_by_id[schema_id] = document
        schema_kinds[schema_id] = kind

    compatibility_path, compatibility_raw = _read_hashed_json(
        root, manifest["compatibility"], "compatibility"
    )
    dependencies.add(compatibility_path)
    compatibility = _object(compatibility_raw, "compatibility.document")
    _exact_keys(compatibility, {"contract", "records"}, "compatibility.document")
    if compatibility["contract"] != "portable-schema-compatibility/v1":
        raise PortableFormKernelError(
            "compatibility.contract must equal portable-schema-compatibility/v1"
        )
    compatibility_records: list[dict[str, Any]] = []
    seen_compatibility: set[tuple[str, str]] = set()
    for index, raw_record in enumerate(_array(compatibility["records"], "compatibility.records")):
        record_label = f"compatibility.records[{index}]"
        record = _object(raw_record, record_label)
        _exact_keys(
            record,
            {
                "portable_schema_id",
                "existing_schema_ref",
                "relation",
                "mapping_status",
                "comparison",
                "evidence",
            },
            record_label,
        )
        portable_schema_id = _string(
            record["portable_schema_id"], f"{record_label}.portable_schema_id"
        )
        if portable_schema_id not in schemas_by_id:
            raise PortableFormKernelError(
                f"{record_label}.portable_schema_id is not a bundled schema"
            )
        existing_schema_ref = _string(
            record["existing_schema_ref"], f"{record_label}.existing_schema_ref"
        )
        identity = (portable_schema_id, existing_schema_ref)
        if identity in seen_compatibility:
            raise PortableFormKernelError(f"duplicate compatibility record: {identity}")
        seen_compatibility.add(identity)
        if record["relation"] not in {
            "candidate_alias",
            "compatible_subset",
            "compatible_superset",
            "intentional_divergence",
            "supersedes",
        }:
            raise PortableFormKernelError(f"{record_label}.relation is unknown")
        if record["mapping_status"] not in MAPPING_STATES:
            raise PortableFormKernelError(f"{record_label}.mapping_status is unknown")
        _object(record["comparison"], f"{record_label}.comparison")
        _validate_source_evidence(record["evidence"], f"{record_label}.evidence")
        compatibility_records.append(record)

    forms_by_key: dict[str, PortableFormDeclaration] = {}
    question_schema_ids = set(question_ids.values())
    for schema_id, document in schemas_by_id.items():
        for reference in _references(document):
            if reference not in schemas_by_id:
                raise PortableFormKernelError(
                    f"schema {schema_id} contains an unbundled schema reference: {reference}"
                )
    for index, raw_form in enumerate(_array(manifest["forms"], "forms")):
        label = f"forms[{index}]"
        definition = _object(raw_form, label)
        required_definition_keys = {
            "form_key",
            "schema_id",
            "metadata",
            "ui",
            "mappings",
            "question_bindings",
            "source_evidence",
            "supplemental_evidence",
            "review_boundary",
        }
        definition_keys = set(definition)
        missing_definition_keys = required_definition_keys - definition_keys
        unknown_definition_keys = definition_keys - required_definition_keys - {"rules"}
        if missing_definition_keys or unknown_definition_keys:
            raise PortableFormKernelError(
                f"{label} has invalid keys; missing={sorted(missing_definition_keys)}, "
                f"unknown={sorted(unknown_definition_keys)}"
            )
        form_key = _string(definition["form_key"], f"{label}.form_key")
        if form_key in forms_by_key:
            raise PortableFormKernelError(f"duplicate form_key: {form_key}")
        schema_id = _string(definition["schema_id"], f"{label}.schema_id")
        if schema_kinds.get(schema_id) != "form":
            raise PortableFormKernelError(f"{label}.schema_id is not a bundled form schema")

        metadata = _object(definition["metadata"], f"{label}.metadata")
        required_metadata_keys = {
            "form_id",
            "legacy_form_id",
            "form_name",
            "short_form_name",
            "form_version",
            "agency_code",
            "omb_number",
            "form_type",
            "sgg_version",
            "is_deprecated",
        }
        metadata_keys = set(metadata)
        missing_metadata_keys = required_metadata_keys - metadata_keys
        unknown_metadata_keys = metadata_keys - required_metadata_keys - {"form_instruction_id"}
        if missing_metadata_keys or unknown_metadata_keys:
            raise PortableFormKernelError(
                f"{label}.metadata has invalid keys; missing={sorted(missing_metadata_keys)}, "
                f"unknown={sorted(unknown_metadata_keys)}"
            )
        try:
            uuid.UUID(_string(metadata["form_id"], f"{label}.metadata.form_id"))
        except ValueError as exc:
            raise PortableFormKernelError(f"{label}.metadata.form_id must be a UUID") from exc
        for key in ("form_name", "short_form_name", "form_version", "agency_code", "sgg_version"):
            _string(metadata[key], f"{label}.metadata.{key}")
        if not isinstance(metadata["is_deprecated"], bool):
            raise PortableFormKernelError(f"{label}.metadata.is_deprecated must be boolean")
        instruction_id = metadata.get("form_instruction_id")
        if instruction_id is not None:
            try:
                uuid.UUID(_string(instruction_id, f"{label}.metadata.form_instruction_id"))
            except ValueError as exc:
                raise PortableFormKernelError(
                    f"{label}.metadata.form_instruction_id must be a UUID or null"
                ) from exc

        ui_path, ui_raw = _read_hashed_json(root, definition["ui"], f"{label}.ui")
        mapping_path, mappings_raw = _read_hashed_json(
            root, definition["mappings"], f"{label}.mappings"
        )
        dependencies.update({ui_path, mapping_path})
        rules = None
        if "rules" in definition:
            rules_path, rules_raw = _read_hashed_json(root, definition["rules"], f"{label}.rules")
            dependencies.add(rules_path)
            rules = _object(rules_raw, f"{label}.rules.document")
        for evidence_index, raw_evidence in enumerate(
            _array(definition["supplemental_evidence"], f"{label}.supplemental_evidence")
        ):
            evidence_path, _evidence_document = _read_hashed_json(
                root,
                raw_evidence,
                f"{label}.supplemental_evidence[{evidence_index}]",
            )
            dependencies.add(evidence_path)
        ui = _object(ui_raw, f"{label}.ui.document")
        mappings = _object(mappings_raw, f"{label}.mappings.document")
        _exact_keys(mappings, {"targets"}, f"{label}.mappings.document")
        targets = _object(mappings["targets"], f"{label}.mappings.targets")
        for target_name, raw_target in targets.items():
            target = _object(raw_target, f"{label}.mappings.targets.{target_name}")
            if target_name == "common_grants":
                _exact_keys(target, {"from", "to"}, f"{label}.mappings.targets.{target_name}")
                _object(target["from"], f"{label}.mappings.targets.{target_name}.from")
                _object(target["to"], f"{label}.mappings.targets.{target_name}.to")
            elif target_name == "grants_gov_xml":
                target_keys = set(target)
                if target_keys not in ({"bindings"}, {"bindings", "runtime_transform"}):
                    raise PortableFormKernelError(
                        f"{label}.mappings.targets.{target_name} has invalid keys; "
                        "expected bindings with optional runtime_transform"
                    )
                bindings = _object(
                    target["bindings"], f"{label}.mappings.targets.{target_name}.bindings"
                )
                for binding_id, raw_xml in bindings.items():
                    xml = _object(raw_xml, f"{label}.mappings.xml.{binding_id}")
                    _exact_keys(
                        xml,
                        {"path", "type_source", "type", "xsd_source"},
                        f"{label}.mappings.xml.{binding_id}",
                    )
                    for key in ("path", "type_source", "type", "xsd_source"):
                        _string(xml[key], f"{label}.mappings.xml.{binding_id}.{key}")
                if "runtime_transform" in target:
                    _object(
                        target["runtime_transform"],
                        f"{label}.mappings.targets.{target_name}.runtime_transform",
                    )
            else:
                raise PortableFormKernelError(f"{label} has unknown mapping target: {target_name}")

        schema = schemas_by_id[schema_id]
        all_references = dict(_question_references(schema, question_schema_ids))
        covered_references: set[str] = set()
        seen_binding_ids: set[str] = set()
        seen_form_pointers: set[str] = set()
        for binding_index, raw_binding in enumerate(
            _array(definition["question_bindings"], f"{label}.question_bindings")
        ):
            binding_label = f"{label}.question_bindings[{binding_index}]"
            binding = _object(raw_binding, binding_label)
            _exact_keys(
                binding,
                {
                    "binding_id",
                    "question_id",
                    "schema_id",
                    "form_pointer",
                    "role",
                    "cardinality",
                    "context",
                    "mapping_refs",
                    "mapping_status",
                },
                binding_label,
            )
            binding_id = _string(binding["binding_id"], f"{binding_label}.binding_id")
            if binding_id in seen_binding_ids:
                raise PortableFormKernelError(f"duplicate binding_id: {binding_id}")
            seen_binding_ids.add(binding_id)
            question_id = _string(binding["question_id"], f"{binding_label}.question_id")
            question_schema_id = _string(binding["schema_id"], f"{binding_label}.schema_id")
            if question_ids.get(question_id) != question_schema_id:
                raise PortableFormKernelError(
                    f"{binding_label} does not identify a bundled question schema"
                )
            pointer = _string(binding["form_pointer"], f"{binding_label}.form_pointer")
            if pointer in seen_form_pointers:
                raise PortableFormKernelError(f"duplicate form pointer: {pointer}")
            seen_form_pointers.add(pointer)
            _resolve_pointer(schema, pointer, f"{binding_label}.form_pointer")
            matching_references = {
                ref_pointer
                for ref_pointer, ref_schema_id in all_references.items()
                if ref_schema_id == question_schema_id
                and (ref_pointer == f"{pointer}/$ref" or ref_pointer.startswith(f"{pointer}/"))
            }
            if len(matching_references) != 1:
                raise PortableFormKernelError(
                    f"{binding_label} must cover exactly one question $ref occurrence"
                )
            reference_pointer = next(iter(matching_references))
            if reference_pointer in covered_references:
                raise PortableFormKernelError(
                    f"question $ref occurrence is bound more than once: {reference_pointer}"
                )
            covered_references.add(reference_pointer)
            _string(binding["role"], f"{binding_label}.role")
            _validate_cardinality(binding["cardinality"], f"{binding_label}.cardinality")
            _object(binding["context"], f"{binding_label}.context")
            mapping_refs = _object(binding["mapping_refs"], f"{binding_label}.mapping_refs")
            for mapping_target, mapping_ref in mapping_refs.items():
                if mapping_target not in targets:
                    raise PortableFormKernelError(
                        f"{binding_label}.mapping_refs names absent target: {mapping_target}"
                    )
                mapping_ref = _string(mapping_ref, f"{binding_label}.mapping_refs.{mapping_target}")
                if (
                    mapping_target == "grants_gov_xml"
                    and mapping_ref not in targets[mapping_target]["bindings"]
                ):
                    raise PortableFormKernelError(
                        f"{binding_label}.mapping_refs.{mapping_target} does not resolve"
                    )
            if binding["mapping_status"] not in MAPPING_STATES:
                raise PortableFormKernelError(f"{binding_label}.mapping_status is unknown")

        if covered_references != set(all_references):
            missing = sorted(set(all_references) - covered_references)
            raise PortableFormKernelError(
                f"{label} has unbound question $ref occurrences: {missing}"
            )

        review = _object(definition["review_boundary"], f"{label}.review_boundary")
        _exact_keys(
            review,
            {"semantic_mappings", "published_coverage_eligible", "production_ready"},
            f"{label}.review_boundary",
        )
        if review["semantic_mappings"] not in MAPPING_STATES:
            raise PortableFormKernelError(f"{label} semantic mapping state is unknown")
        if not isinstance(review["published_coverage_eligible"], bool):
            raise PortableFormKernelError(
                f"{label}.review_boundary.published_coverage_eligible must be boolean"
            )
        if not isinstance(review["production_ready"], bool):
            raise PortableFormKernelError(
                f"{label}.review_boundary.production_ready must be boolean"
            )
        if review["published_coverage_eligible"] and any(
            binding["mapping_status"] != "accepted" for binding in definition["question_bindings"]
        ):
            raise PortableFormKernelError(
                f"{label} cannot publish coverage with unaccepted occurrence mappings"
            )

        sources = _array(definition["source_evidence"], f"{label}.source_evidence")
        if not sources:
            raise PortableFormKernelError(f"{label}.source_evidence cannot be empty")
        for source_index, source in enumerate(sources):
            _validate_source_evidence(source, f"{label}.source_evidence[{source_index}]")

        forms_by_key[form_key] = PortableFormDeclaration(
            definition=definition,
            schema=schema,
            ui=ui,
            mappings=mappings,
            rules=rules,
        )

    bundle_digest = hashlib.sha256(canonical_json(manifest).encode("utf-8")).hexdigest()
    return PortableFormKernel(
        root=root,
        manifest=manifest,
        schemas_by_id=schemas_by_id,
        forms_by_key=forms_by_key,
        compatibility_records=tuple(compatibility_records),
        dependency_paths=tuple(sorted(dependencies)),
        bundle_digest=bundle_digest,
    )
