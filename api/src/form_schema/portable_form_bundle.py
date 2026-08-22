"""Load portable referenced form declarations into the native Simpler runtime."""

from __future__ import annotations

import dataclasses
import copy
import hashlib
import itertools
import json
import re
import uuid
from pathlib import Path
from typing import Any

import jsonref
import jsonschema

from src.constants.lookup_constants import FormType
from src.db.models.competition_models import Form

CONTRACT = "portable-grants-form-bundle/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PortableFormBundleError(ValueError):
    """Raised when portable form declarations are incomplete or inconsistent."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PortableFormBundleError(f"{label} must be an object with string keys")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PortableFormBundleError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PortableFormBundleError(f"{label} must be a non-empty string")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise PortableFormBundleError(
            f"{label} has invalid keys; "
            f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )


def _safe_path(root: Path, raw: object, label: str) -> Path:
    relative = Path(_string(raw, label))
    if relative.is_absolute() or ".." in relative.parts:
        raise PortableFormBundleError(f"{label} must remain inside the portable bundle")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise PortableFormBundleError(f"{label} does not identify a bundle file: {relative}")
    return path


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortableFormBundleError(f"could not read {label}: {path}") from exc


def _read_hashed_json(root: Path, descriptor: object, label: str) -> tuple[Path, object]:
    value = _object(descriptor, label)
    _exact_keys(value, {"path", "sha256"}, label)
    path = _safe_path(root, value["path"], f"{label}.path")
    expected = _string(value["sha256"], f"{label}.sha256")
    if not _SHA256.fullmatch(expected):
        raise PortableFormBundleError(f"{label}.sha256 must be a lowercase SHA-256 digest")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise PortableFormBundleError(
            f"{label}.sha256 does not match {value['path']}: expected {expected}, got {actual}"
        )
    return path, _read_json(path, label)


def _resolve_pointer(document: object, pointer: str, label: str) -> object:
    if not pointer.startswith("/"):
        raise PortableFormBundleError(f"{label} must be an absolute JSON pointer")
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise PortableFormBundleError(f"{label} does not resolve: {pointer}")
        current = current[token]
    return current


def _contains_question_id(value: object, question_id: str) -> bool:
    if isinstance(value, dict):
        if value.get("x-question-id") == question_id:
            return True
        return any(_contains_question_id(child, question_id) for child in value.values())
    if isinstance(value, list):
        return any(_contains_question_id(child, question_id) for child in value)
    return False


def _ui_name(label: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return name or "section"


def _adapt_ui_node(node: object, label: str) -> list[dict[str, Any]]:
    value = _object(node, label)
    node_type = _string(value.get("type"), f"{label}.type")
    if node_type == "Control":
        allowed = {"type", "scope", "label", "description", "options"}
        unknown = set(value) - allowed
        if unknown:
            raise PortableFormBundleError(f"{label} has unknown Control keys: {sorted(unknown)}")
        scope = _string(value.get("scope"), f"{label}.scope")
        if not scope.startswith("#/"):
            raise PortableFormBundleError(f"{label}.scope must begin with #/")
        result: dict[str, Any] = {"type": "field", "definition": scope[1:]}
        for key in ("label", "description"):
            if key in value:
                result[key] = _string(value[key], f"{label}.{key}")
        if "options" in value:
            result["options"] = _object(value["options"], f"{label}.options")
        return [result]

    if node_type not in {"VerticalLayout", "Group"}:
        raise PortableFormBundleError(f"{label}.type is unsupported: {node_type}")
    allowed = {"type", "label", "elements"}
    unknown = set(value) - allowed
    if unknown:
        raise PortableFormBundleError(f"{label} has unknown layout keys: {sorted(unknown)}")
    elements = _array(value.get("elements"), f"{label}.elements")
    children = list(
        itertools.chain.from_iterable(
            _adapt_ui_node(child, f"{label}.elements[{index}]")
            for index, child in enumerate(elements)
        )
    )
    section_label = _string(value.get("label", "Form"), f"{label}.label")
    return [
        {
            "type": "section",
            "label": section_label,
            "name": _ui_name(section_label),
            "children": children,
        }
    ]


@dataclasses.dataclass(frozen=True)
class _PortableForm:
    definition: dict[str, Any]
    schema: dict[str, Any]
    ui: dict[str, Any]
    mappings: dict[str, Any]


@dataclasses.dataclass(frozen=True)
class PortableFormBundle:
    """Verified portable declarations with a generic native-Simpler adapter."""

    root: Path
    manifest: dict[str, Any]
    schemas_by_id: dict[str, dict[str, Any]]
    forms_by_key: dict[str, _PortableForm]
    dependency_paths: tuple[Path, ...]
    bundle_digest: str

    def _resolved_schema(self, form: _PortableForm) -> dict[str, Any]:
        def loader(uri: str, **_kwargs: object) -> object:
            if uri not in self.schemas_by_id:
                raise PortableFormBundleError(f"schema reference is not in the bundle: {uri}")
            return self.schemas_by_id[uri]

        try:
            resolved = jsonref.replace_refs(
                form.schema,
                loader=loader,
                lazy_load=False,
                proxies=False,
                jsonschema=True,
            )
        except (jsonref.JsonRefError, ValueError) as exc:
            raise PortableFormBundleError("could not resolve the form schema graph") from exc
        return _object(resolved, "resolved_schema")

    def to_form(self, form_key: str) -> Form:
        """Resolve one portable form into an independently allocated native Form."""

        if form_key not in self.forms_by_key:
            raise PortableFormBundleError(f"unknown portable form_key: {form_key}")
        portable = self.forms_by_key[form_key]
        definition = portable.definition
        metadata = definition["metadata"]
        schema = self._resolved_schema(portable)
        mappings = copy.deepcopy(portable.mappings)
        schema["x-mapping-from-cg"] = mappings["common_grants"]["from"]
        schema["x-mapping-to-cg"] = mappings["common_grants"]["to"]
        schema["x-portable-form-bundle"] = {
            "contract": CONTRACT,
            "bundle_digest": self.bundle_digest,
            "form_key": form_key,
            "question_bindings": copy.deepcopy(definition["question_bindings"]),
            "review_boundary": copy.deepcopy(definition["review_boundary"]),
        }

        form_type_value = metadata["form_type"]
        return Form(
            form_id=uuid.UUID(metadata["form_id"]),
            legacy_form_id=metadata["legacy_form_id"],
            form_name=metadata["form_name"],
            short_form_name=metadata["short_form_name"],
            form_version=metadata["form_version"],
            agency_code=metadata["agency_code"],
            omb_number=metadata["omb_number"],
            form_json_schema=schema,
            # The current runtime stores a list-shaped UI schema despite the Form annotation.
            form_ui_schema=_adapt_ui_node(portable.ui, f"forms.{form_key}.ui"),  # type: ignore[arg-type]
            form_rule_schema=None,
            json_to_xml_schema=None,
            form_instruction_id=None,
            form_type=FormType(form_type_value) if form_type_value is not None else None,
            sgg_version=metadata["sgg_version"],
            is_deprecated=metadata["is_deprecated"],
        )

    def analysis_projection(self) -> dict[str, Any]:
        """Derive question frequency, association, and pairwise overlap records."""

        associations: list[dict[str, Any]] = []
        form_questions: dict[str, set[str]] = {}
        for form_key, portable in sorted(self.forms_by_key.items()):
            question_ids: set[str] = set()
            xml_fields = portable.mappings["xml_fields"]
            for binding in portable.definition["question_bindings"]:
                question_id = binding["question_id"]
                question_ids.add(question_id)
                xml = xml_fields[question_id]
                associations.append({
                    "form_key": form_key,
                    "question_id": question_id,
                    "role": binding["role"],
                    "form_pointer": binding["form_pointer"],
                    "mapping_status": binding["mapping_status"],
                    "xml_path": xml["path"],
                    "type_source": xml["type_source"],
                    "type": xml["type"],
                    "xsd_source": xml["xsd_source"],
                })
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
            pairwise.append({
                "form_a": form_a,
                "form_b": form_b,
                "questions_in_common": len(common),
                "unique_questions": len(union),
                "similarity": len(common) / len(union) if union else 0.0,
                "form_a_coverage": len(common) / len(questions_a) if questions_a else 0.0,
                "form_b_coverage": len(common) / len(questions_b) if questions_b else 0.0,
            })

        return {
            "contract": "portable-grants-form-analysis/v1",
            "bundle_digest": self.bundle_digest,
            "summary": {
                "forms": len(form_questions),
                "unique_questions": len(question_counts),
                "associations": len(associations),
                "accepted_mappings": 0,
            },
            "questions": [
                {"question_id": question_id, "form_count": count}
                for question_id, count in sorted(question_counts.items())
            ],
            "form_question_associations": associations,
            "pairwise_form_overlap": pairwise,
        }


def load_portable_form_bundle(root: Path, repository_root: Path) -> PortableFormBundle:
    """Verify one portable bundle without network or Simpler-specific authoring imports."""

    root = root.resolve()
    repository_root = repository_root.resolve()
    manifest_path = _safe_path(root, "manifest.json", "manifest")
    manifest = _object(_read_json(manifest_path, "manifest"), "manifest")
    _exact_keys(manifest, {"contract", "bundle", "schemas", "forms"}, "manifest")
    if manifest["contract"] != CONTRACT:
        raise PortableFormBundleError(f"manifest.contract must equal {CONTRACT}")
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
            raise PortableFormBundleError(f"{label}.kind is unknown")
        schema_id = _string(descriptor["id"], f"{label}.id")
        if schema_id in schemas_by_id:
            raise PortableFormBundleError(f"duplicate schema id: {schema_id}")
        path, raw_document = _read_hashed_json(root, descriptor["artifact"], f"{label}.artifact")
        dependencies.add(path)
        document = _object(raw_document, f"{label}.document")
        if document.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise PortableFormBundleError(f"{label} must declare JSON Schema Draft 2020-12")
        if document.get("$id") != schema_id:
            raise PortableFormBundleError(f"{label}.id does not match the schema $id")
        try:
            jsonschema.Draft202012Validator.check_schema(document)
        except jsonschema.SchemaError as exc:
            raise PortableFormBundleError(f"{label} is not valid JSON Schema") from exc
        question_id = descriptor["question_id"]
        if kind == "question":
            question_id = _string(question_id, f"{label}.question_id")
            if document.get("x-question-id") != question_id:
                raise PortableFormBundleError(
                    f"{label}.question_id does not match schema x-question-id"
                )
            if question_id in question_ids:
                raise PortableFormBundleError(f"duplicate question id: {question_id}")
            question_ids[question_id] = schema_id
        elif question_id is not None:
            raise PortableFormBundleError(f"{label}.question_id must be null for form schemas")
        schemas_by_id[schema_id] = document
        schema_kinds[schema_id] = kind

    forms_by_key: dict[str, _PortableForm] = {}
    for index, raw_form in enumerate(_array(manifest["forms"], "forms")):
        label = f"forms[{index}]"
        definition = _object(raw_form, label)
        _exact_keys(
            definition,
            {
                "form_key",
                "schema_id",
                "metadata",
                "ui",
                "mappings",
                "question_bindings",
                "source_evidence",
                "review_boundary",
            },
            label,
        )
        form_key = _string(definition["form_key"], f"{label}.form_key")
        if form_key in forms_by_key:
            raise PortableFormBundleError(f"duplicate form_key: {form_key}")
        schema_id = _string(definition["schema_id"], f"{label}.schema_id")
        if schema_kinds.get(schema_id) != "form":
            raise PortableFormBundleError(f"{label}.schema_id is not a bundled form schema")

        metadata = _object(definition["metadata"], f"{label}.metadata")
        _exact_keys(
            metadata,
            {
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
            },
            f"{label}.metadata",
        )
        try:
            uuid.UUID(_string(metadata["form_id"], f"{label}.metadata.form_id"))
        except ValueError as exc:
            raise PortableFormBundleError(f"{label}.metadata.form_id must be a UUID") from exc
        for key in ("form_name", "short_form_name", "form_version", "agency_code", "sgg_version"):
            _string(metadata[key], f"{label}.metadata.{key}")
        if not isinstance(metadata["is_deprecated"], bool):
            raise PortableFormBundleError(f"{label}.metadata.is_deprecated must be boolean")

        ui_path, ui_raw = _read_hashed_json(root, definition["ui"], f"{label}.ui")
        mapping_path, mappings_raw = _read_hashed_json(
            root, definition["mappings"], f"{label}.mappings"
        )
        dependencies.update({ui_path, mapping_path})
        ui = _object(ui_raw, f"{label}.ui.document")
        mappings = _object(mappings_raw, f"{label}.mappings.document")
        _exact_keys(mappings, {"common_grants", "xml_fields"}, f"{label}.mappings.document")
        common_grants = _object(mappings["common_grants"], f"{label}.mappings.common_grants")
        _exact_keys(common_grants, {"from", "to"}, f"{label}.mappings.common_grants")
        _object(common_grants["from"], f"{label}.mappings.common_grants.from")
        _object(common_grants["to"], f"{label}.mappings.common_grants.to")
        xml_fields = _object(mappings["xml_fields"], f"{label}.mappings.xml_fields")

        schema = schemas_by_id[schema_id]
        seen_pointers: set[str] = set()
        for binding_index, raw_binding in enumerate(
            _array(definition["question_bindings"], f"{label}.question_bindings")
        ):
            binding_label = f"{label}.question_bindings[{binding_index}]"
            binding = _object(raw_binding, binding_label)
            _exact_keys(
                binding,
                {"question_id", "schema_id", "form_pointer", "role", "mapping_status"},
                binding_label,
            )
            question_id = _string(binding["question_id"], f"{binding_label}.question_id")
            question_schema_id = _string(binding["schema_id"], f"{binding_label}.schema_id")
            if question_ids.get(question_id) != question_schema_id:
                raise PortableFormBundleError(
                    f"{binding_label} does not identify a bundled question schema"
                )
            pointer = _string(binding["form_pointer"], f"{binding_label}.form_pointer")
            if pointer in seen_pointers:
                raise PortableFormBundleError(f"duplicate form pointer: {pointer}")
            seen_pointers.add(pointer)
            target = _resolve_pointer(schema, pointer, f"{binding_label}.form_pointer")
            try:
                resolved_target = jsonref.replace_refs(
                    target,
                    loader=lambda uri, **_kwargs: schemas_by_id[uri],
                    lazy_load=False,
                    proxies=False,
                    jsonschema=True,
                )
            except (jsonref.JsonRefError, KeyError) as exc:
                raise PortableFormBundleError(
                    f"{binding_label} contains an unbundled schema reference"
                ) from exc
            if not _contains_question_id(resolved_target, question_id):
                raise PortableFormBundleError(
                    f"{binding_label} target does not compose the declared question"
                )
            _string(binding["role"], f"{binding_label}.role")
            if binding["mapping_status"] != "agent_proposed":
                raise PortableFormBundleError(
                    f"{binding_label}.mapping_status must remain agent_proposed in the canary"
                )
            xml = _object(xml_fields.get(question_id), f"{binding_label}.xml")
            _exact_keys(xml, {"path", "type_source", "type", "xsd_source"}, f"{binding_label}.xml")
            for key in ("path", "type_source", "type", "xsd_source"):
                _string(xml[key], f"{binding_label}.xml.{key}")

        review = _object(definition["review_boundary"], f"{label}.review_boundary")
        _exact_keys(
            review,
            {"semantic_mappings", "published_coverage_eligible", "production_ready"},
            f"{label}.review_boundary",
        )
        if review["semantic_mappings"] != "agent_proposed":
            raise PortableFormBundleError(f"{label} semantic mappings must remain agent_proposed")
        if review["published_coverage_eligible"] is not False:
            raise PortableFormBundleError(f"{label} cannot publish unreviewed coverage")
        if review["production_ready"] is not False:
            raise PortableFormBundleError(f"{label} canary cannot be production ready")

        for source_index, raw_source in enumerate(
            _array(definition["source_evidence"], f"{label}.source_evidence")
        ):
            source_label = f"{label}.source_evidence[{source_index}]"
            source = _object(raw_source, source_label)
            _exact_keys(source, {"path", "sha256", "source_version"}, source_label)
            source_path = Path(_string(source["path"], f"{source_label}.path"))
            if source_path.is_absolute() or ".." in source_path.parts:
                raise PortableFormBundleError(f"{source_label}.path must be repository-relative")
            evidence_path = (repository_root / source_path).resolve()
            if not evidence_path.is_relative_to(repository_root) or not evidence_path.is_file():
                raise PortableFormBundleError(f"{source_label}.path is missing")
            expected = _string(source["sha256"], f"{source_label}.sha256")
            if hashlib.sha256(evidence_path.read_bytes()).hexdigest() != expected:
                raise PortableFormBundleError(f"{source_label}.sha256 does not match source")
            _string(source["source_version"], f"{source_label}.source_version")
            dependencies.add(evidence_path)

        forms_by_key[form_key] = _PortableForm(
            definition=definition,
            schema=schema,
            ui=ui,
            mappings=mappings,
        )

    bundle_digest = hashlib.sha256(_canonical_json(manifest).encode("utf-8")).hexdigest()
    return PortableFormBundle(
        root=root,
        manifest=manifest,
        schemas_by_id=schemas_by_id,
        forms_by_key=forms_by_key,
        dependency_paths=tuple(sorted(dependencies)),
        bundle_digest=bundle_digest,
    )
