"""Load immutable, source-pinned form packages into the native Form runtime."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from src.constants.lookup_constants import FormType
from src.db.models.competition_models import Form

CONTRACT = "common-grants-resolved-form-package/v1"
PORTABLE_RESOLVED_CONTRACT = "portable-grants-resolved-form-package/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")


class ResolvedFormPackageError(ValueError):
    """Raised when a resolved package is incomplete, unpinned, or inconsistent."""


@dataclasses.dataclass(frozen=True)
class ResolvedFormPackage:
    """Verified package artifacts and their native Simpler form metadata."""

    package_root: Path
    dependency_paths: tuple[Path, ...]
    package_digest: str
    _manifest_json: str
    _json_schema_json: str
    _ui_schema_json: str
    _mappings_json: str
    _rule_schema_json: str | None
    _xml_transform_json: str | None

    @property
    def manifest(self) -> dict[str, Any]:
        return json.loads(self._manifest_json)

    @property
    def json_schema(self) -> dict[str, Any]:
        return json.loads(self._json_schema_json)

    @property
    def ui_schema(self) -> list[dict[str, Any]]:
        return json.loads(self._ui_schema_json)

    @property
    def mappings(self) -> dict[str, Any]:
        return json.loads(self._mappings_json)

    @property
    def rule_schema(self) -> dict[str, Any] | None:
        return json.loads(self._rule_schema_json) if self._rule_schema_json is not None else None

    @property
    def xml_transform(self) -> dict[str, Any] | None:
        if self._xml_transform_json is None:
            return None
        return json.loads(self._xml_transform_json)

    def to_form(self) -> Form:
        """Materialize an independently allocated native Form instance."""

        manifest = self.manifest
        metadata = manifest["form"]
        json_schema = self.json_schema
        mappings = self.mappings
        for key in ("x-mapping-from-cg", "x-mapping-to-cg"):
            mapping = mappings[key]
            existing = json_schema.get(key)
            if existing is not None and existing != mapping:
                raise ResolvedFormPackageError(
                    f"json_schema.{key} conflicts with the verified mappings artifact"
                )
            json_schema[key] = mapping
        json_schema["x-simpler-form-package"] = {
            "contract": manifest["contract"],
            "package_digest": self.package_digest,
            "source_set": manifest["source_set"],
            "compiler": manifest["compiler"],
            "question_bindings": manifest["question_bindings"],
            "review_boundary": manifest["review_boundary"],
        }

        form_type_value = metadata.get("form_type")
        form_type = FormType(form_type_value) if form_type_value is not None else None
        instruction_id = metadata.get("form_instruction_id")

        return Form(
            form_id=uuid.UUID(metadata["form_id"]),
            legacy_form_id=metadata.get("legacy_form_id"),
            form_name=metadata["form_name"],
            short_form_name=metadata["short_form_name"],
            form_version=metadata["form_version"],
            agency_code=metadata["agency_code"],
            omb_number=metadata.get("omb_number"),
            form_json_schema=json_schema,
            # Form.form_ui_schema is list-shaped throughout the current runtime. The
            # model annotation is corrected independently in the template-composition PR.
            form_ui_schema=self.ui_schema,  # type: ignore[arg-type]
            form_rule_schema=self.rule_schema,
            json_to_xml_schema=self.xml_transform,
            form_instruction_id=uuid.UUID(instruction_id) if instruction_id else None,
            form_type=form_type,
            sgg_version=metadata.get("sgg_version"),
            is_deprecated=metadata.get("is_deprecated", False),
        )


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ResolvedFormPackageError(f"{label} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise ResolvedFormPackageError(f"{label} keys must be strings")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ResolvedFormPackageError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ResolvedFormPackageError(f"{label} must be a non-empty string")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ResolvedFormPackageError(
            f"{label} has invalid keys; missing={missing}, unknown={unknown}"
        )


def _sha256(value: object, label: str) -> str:
    digest = _string(value, label)
    if not _SHA256.fullmatch(digest):
        raise ResolvedFormPackageError(f"{label} must be a lowercase SHA-256 digest")
    return digest


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolvedFormPackageError(f"could not read {label}: {path}") from exc


def _artifact_path(package_root: Path, value: object, label: str) -> Path:
    relative = Path(_string(value, f"{label}.path"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ResolvedFormPackageError(f"{label}.path must remain inside the package")
    resolved = (package_root / relative).resolve()
    if not resolved.is_relative_to(package_root):
        raise ResolvedFormPackageError(f"{label}.path escapes the package")
    if not resolved.is_file():
        raise ResolvedFormPackageError(f"{label}.path does not identify a file: {relative}")
    return resolved


def _load_artifact(package_root: Path, descriptor: object, label: str) -> object:
    value = _object(descriptor, label)
    _exact_keys(value, {"path", "sha256"}, label)
    path = _artifact_path(package_root, value["path"], label)
    expected = _sha256(value["sha256"], f"{label}.sha256")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ResolvedFormPackageError(
            f"{label}.sha256 does not match {value['path']}: expected {expected}, got {actual}"
        )
    return _read_json(path, label)


def _verify_source(package_root: Path, value: object, label: str) -> None:
    source = _object(value, label)
    _exact_keys(source, {"source_path", "package_path", "sha256"}, label)
    source_path = Path(_string(source["source_path"], f"{label}.source_path"))
    if source_path.is_absolute() or ".." in source_path.parts:
        raise ResolvedFormPackageError(f"{label}.source_path must be repository-relative")
    path = _artifact_path(package_root, source["package_path"], label)
    expected = _sha256(source["sha256"], f"{label}.sha256")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ResolvedFormPackageError(
            f"{label}.sha256 does not match {source['package_path']}: "
            f"expected {expected}, got {actual}"
        )


def _validate_source_set(package_root: Path, value: object) -> None:
    source_set = _object(value, "source_set")
    _exact_keys(
        source_set,
        {
            "repository",
            "revision",
            "attestation",
            "closure",
            "graph_sha256",
            "form",
            "questions",
        },
        "source_set",
    )
    _string(source_set["repository"], "source_set.repository")
    revision = _string(source_set["revision"], "source_set.revision")
    if not _REVISION.fullmatch(revision):
        raise ResolvedFormPackageError("source_set.revision must be a full lowercase git SHA")
    if source_set["attestation"] != "snapshot_only":
        raise ResolvedFormPackageError("source_set.attestation is unsupported")
    if source_set["closure"] not in {"partial_evidence", "complete"}:
        raise ResolvedFormPackageError("source_set.closure is unknown")

    _verify_source(package_root, source_set["form"], "source_set.form")

    questions = _array(source_set["questions"], "source_set.questions")
    seen: set[str] = set()
    for index, raw_question in enumerate(questions):
        label = f"source_set.questions[{index}]"
        question = _object(raw_question, label)
        _exact_keys(
            question,
            {"question_id", "source_path", "package_path", "sha256"},
            label,
        )
        question_id = _string(question["question_id"], f"{label}.question_id")
        if question_id in seen:
            raise ResolvedFormPackageError(f"duplicate source question: {question_id}")
        seen.add(question_id)
        _verify_source(
            package_root,
            {key: value for key, value in question.items() if key != "question_id"},
            label,
        )

    graph = {
        key: source_set[key]
        for key in ("repository", "revision", "attestation", "closure", "form", "questions")
    }
    actual_graph_sha256 = hashlib.sha256(_canonical_json(graph).encode("utf-8")).hexdigest()
    expected_graph_sha256 = _sha256(source_set["graph_sha256"], "source_set.graph_sha256")
    if actual_graph_sha256 != expected_graph_sha256:
        raise ResolvedFormPackageError(
            "source_set.graph_sha256 does not match the canonical source graph"
        )


def _validate_form(value: object) -> None:
    form = _object(value, "form")
    required = {
        "form_id",
        "legacy_form_id",
        "form_name",
        "short_form_name",
        "form_version",
        "agency_code",
        "omb_number",
        "form_instruction_id",
        "form_type",
        "sgg_version",
        "is_deprecated",
    }
    _exact_keys(form, required, "form")
    try:
        uuid.UUID(_string(form["form_id"], "form.form_id"))
    except ValueError as exc:
        raise ResolvedFormPackageError("form.form_id must be a UUID") from exc
    for key in ("form_name", "short_form_name", "form_version", "agency_code"):
        _string(form[key], f"form.{key}")
    if form["legacy_form_id"] is not None and not isinstance(form["legacy_form_id"], int):
        raise ResolvedFormPackageError("form.legacy_form_id must be an integer or null")
    if form["omb_number"] is not None and not isinstance(form["omb_number"], str):
        raise ResolvedFormPackageError("form.omb_number must be a string or null")
    if form["form_instruction_id"] is not None:
        try:
            uuid.UUID(_string(form["form_instruction_id"], "form.form_instruction_id"))
        except ValueError as exc:
            raise ResolvedFormPackageError(
                "form.form_instruction_id must be a UUID or null"
            ) from exc
    if form["form_type"] is not None:
        try:
            FormType(_string(form["form_type"], "form.form_type"))
        except ValueError as exc:
            raise ResolvedFormPackageError("form.form_type is unknown") from exc
    if form["sgg_version"] is not None and not isinstance(form["sgg_version"], str):
        raise ResolvedFormPackageError("form.sgg_version must be a string or null")
    if not isinstance(form["is_deprecated"], bool):
        raise ResolvedFormPackageError("form.is_deprecated must be a boolean")


def _validate_question_bindings(value: object, source_question_ids: set[str]) -> None:
    bindings = _array(value, "question_bindings")
    seen_pointers: set[str] = set()
    for index, raw_binding in enumerate(bindings):
        label = f"question_bindings[{index}]"
        binding = _object(raw_binding, label)
        _exact_keys(binding, {"question_id", "form_pointer", "overrides"}, label)
        question_id = _string(binding["question_id"], f"{label}.question_id")
        if question_id not in source_question_ids:
            raise ResolvedFormPackageError(f"{label}.question_id is absent from source_set")
        pointer = _string(binding["form_pointer"], f"{label}.form_pointer")
        if not pointer.startswith("/properties/"):
            raise ResolvedFormPackageError(f"{label}.form_pointer must begin with /properties/")
        if pointer in seen_pointers:
            raise ResolvedFormPackageError(f"duplicate form_pointer: {pointer}")
        seen_pointers.add(pointer)
        _object(binding["overrides"], f"{label}.overrides")


def _pointer_tokens(pointer: str) -> list[str]:
    return [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]


def _resolve_pointer(document: object, pointer: str, label: str) -> object:
    current = document
    for token in _pointer_tokens(pointer):
        if not isinstance(current, dict) or token not in current:
            raise ResolvedFormPackageError(f"{label} does not resolve in json_schema: {pointer}")
        current = current[token]
    return current


def _resolve_data_path(json_schema: dict[str, Any], path: list[str], label: str) -> None:
    current: object = json_schema
    for segment in path:
        current_object = _object(current, label)
        properties = _object(current_object.get("properties"), f"{label}.properties")
        if segment not in properties:
            raise ResolvedFormPackageError(
                f"{label} does not resolve in json_schema: {'.'.join(path)}"
            )
        current = properties[segment]


def _direct_mapping_leaves(
    node: object, path: tuple[str, ...], label: str
) -> list[tuple[tuple[str, ...], str]]:
    value = _object(node, label)
    if set(value) == {"field"}:
        return [(path, _string(value["field"], f"{label}.field"))]
    if "field" in value:
        raise ResolvedFormPackageError(f"{label} mixes a field leaf with nested mapping keys")
    leaves: list[tuple[tuple[str, ...], str]] = []
    for key, child in value.items():
        leaves.extend(_direct_mapping_leaves(child, (*path, key), f"{label}.{key}"))
    return leaves


def _validate_package_cross_references(
    manifest: dict[str, Any], json_schema: dict[str, Any], mappings: dict[str, Any]
) -> None:
    for index, binding in enumerate(manifest["question_bindings"]):
        label = f"question_bindings[{index}]"
        target = _object(
            _resolve_pointer(json_schema, binding["form_pointer"], f"{label}.form_pointer"),
            f"{label}.target",
        )
        if target.get("x-question-id") != binding["question_id"]:
            raise ResolvedFormPackageError(
                f"{label}.question_id does not match the bound schema x-question-id"
            )

    from_leaves = _direct_mapping_leaves(
        mappings["x-mapping-from-cg"], (), "mappings.x-mapping-from-cg"
    )
    for mapped_form_path, _from_common_grants_path in from_leaves:
        _resolve_data_path(json_schema, list(mapped_form_path), "x-mapping-from-cg form path")

    to_leaves = _direct_mapping_leaves(mappings["x-mapping-to-cg"], (), "mappings.x-mapping-to-cg")
    for _to_common_grants_path, to_form_reference in to_leaves:
        _resolve_data_path(json_schema, to_form_reference.split("."), "x-mapping-to-cg form path")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _contains_question_id(value: object, question_id: str) -> bool:
    if isinstance(value, dict):
        if value.get("x-question-id") == question_id:
            return True
        return any(_contains_question_id(child, question_id) for child in value.values())
    if isinstance(value, list):
        return any(_contains_question_id(child, question_id) for child in value)
    return False


def create_resolved_form_package(
    *,
    manifest: dict[str, Any],
    json_schema: dict[str, Any],
    ui_schema: list[dict[str, Any]],
    mappings: dict[str, Any],
    rule_schema: dict[str, Any] | None = None,
    xml_transform: dict[str, Any] | None = None,
    dependency_paths: tuple[Path, ...] = (),
) -> ResolvedFormPackage:
    """Create the immutable native package seam from verified portable artifacts.

    This is the in-memory counterpart to :func:`load_resolved_form_package`. It keeps
    the native ``Form`` materialization boundary in one place while allowing a
    dependency-neutral compiler to supply already verified artifacts.
    """

    _exact_keys(
        manifest,
        {
            "contract",
            "source_set",
            "compiler",
            "form",
            "question_bindings",
            "review_boundary",
        },
        "manifest",
    )
    if manifest["contract"] != PORTABLE_RESOLVED_CONTRACT:
        raise ResolvedFormPackageError(
            f"manifest.contract must equal {PORTABLE_RESOLVED_CONTRACT}"
        )
    _object(manifest["source_set"], "source_set")
    compiler = _object(manifest["compiler"], "compiler")
    _exact_keys(compiler, {"name", "version", "verification", "sha256"}, "compiler")
    _string(compiler["name"], "compiler.name")
    _string(compiler["version"], "compiler.version")
    if compiler["verification"] != "content_addressed":
        raise ResolvedFormPackageError("compiler.verification must be content_addressed")
    _sha256(compiler["sha256"], "compiler.sha256")
    _validate_form(manifest["form"])

    if not isinstance(json_schema, dict):
        raise ResolvedFormPackageError("json_schema must be an object")
    if not all(isinstance(node, dict) for node in ui_schema):
        raise ResolvedFormPackageError("ui_schema entries must be objects")
    _exact_keys(mappings, {"x-mapping-from-cg", "x-mapping-to-cg"}, "mappings")
    _object(mappings["x-mapping-from-cg"], "mappings.x-mapping-from-cg")
    _object(mappings["x-mapping-to-cg"], "mappings.x-mapping-to-cg")

    bindings = _array(manifest["question_bindings"], "question_bindings")
    seen_binding_ids: set[str] = set()
    for index, raw_binding in enumerate(bindings):
        label = f"question_bindings[{index}]"
        binding = _object(raw_binding, label)
        binding_id = _string(binding.get("binding_id"), f"{label}.binding_id")
        if binding_id in seen_binding_ids:
            raise ResolvedFormPackageError(f"duplicate binding_id: {binding_id}")
        seen_binding_ids.add(binding_id)
        question_id = _string(binding.get("question_id"), f"{label}.question_id")
        pointer = _string(binding.get("form_pointer"), f"{label}.form_pointer")
        target = _resolve_pointer(json_schema, pointer, f"{label}.form_pointer")
        if not _contains_question_id(target, question_id):
            raise ResolvedFormPackageError(
                f"{label}.question_id does not match its resolved schema occurrence"
            )

    review_boundary = _object(manifest["review_boundary"], "review_boundary")
    if not isinstance(review_boundary.get("published_coverage_eligible"), bool):
        raise ResolvedFormPackageError(
            "review_boundary.published_coverage_eligible must be a boolean"
        )

    canonical_manifest = _canonical_json(manifest)
    package_digest = hashlib.sha256(canonical_manifest.encode("utf-8")).hexdigest()
    return ResolvedFormPackage(
        package_root=Path(),
        dependency_paths=tuple(sorted(path.resolve() for path in dependency_paths)),
        package_digest=package_digest,
        _manifest_json=canonical_manifest,
        _json_schema_json=_canonical_json(json_schema),
        _ui_schema_json=_canonical_json(ui_schema),
        _mappings_json=_canonical_json(mappings),
        _rule_schema_json=_canonical_json(rule_schema) if rule_schema is not None else None,
        _xml_transform_json=(
            _canonical_json(xml_transform) if xml_transform is not None else None
        ),
    )


def load_resolved_form_package(package_root: Path) -> ResolvedFormPackage:
    """Verify and load one self-contained, pre-resolved form package."""

    package_root = package_root.resolve()
    manifest_path = _artifact_path(package_root, "manifest.json", "manifest")
    manifest = _object(_read_json(manifest_path, "manifest"), "manifest")
    _exact_keys(
        manifest,
        {
            "contract",
            "source_set",
            "compiler",
            "form",
            "artifacts",
            "question_bindings",
            "review_boundary",
        },
        "manifest",
    )
    if manifest["contract"] != CONTRACT:
        raise ResolvedFormPackageError(f"manifest.contract must equal {CONTRACT}")

    _validate_source_set(package_root, manifest["source_set"])
    _validate_form(manifest["form"])

    compiler = _object(manifest["compiler"], "compiler")
    _exact_keys(
        compiler,
        {"name", "version", "verification", "sha256"},
        "compiler",
    )
    _string(compiler["name"], "compiler.name")
    _string(compiler["version"], "compiler.version")
    if compiler["verification"] not in {"manual_canary", "content_addressed"}:
        raise ResolvedFormPackageError("compiler.verification is unknown")
    if compiler["verification"] == "content_addressed":
        _sha256(compiler["sha256"], "compiler.sha256")
    elif compiler["sha256"] is not None:
        raise ResolvedFormPackageError("manual_canary compiler.sha256 must be null")

    source_questions = {question["question_id"] for question in manifest["source_set"]["questions"]}
    _validate_question_bindings(manifest["question_bindings"], source_questions)

    review_boundary = _object(manifest["review_boundary"], "review_boundary")
    _exact_keys(
        review_boundary,
        {
            "semantic_mappings",
            "mapping_composition",
            "ui_projection",
            "common_grants_model_validation",
            "published_coverage_eligible",
        },
        "review_boundary",
    )
    review_states = {"source_authored", "agent_proposed", "human_reviewed"}
    for key in ("semantic_mappings", "mapping_composition", "ui_projection"):
        if review_boundary[key] not in review_states:
            raise ResolvedFormPackageError(f"review_boundary.{key} is unknown")
    if review_boundary["common_grants_model_validation"] not in {
        "not_validated",
        "source_pinned",
    }:
        raise ResolvedFormPackageError("review_boundary.common_grants_model_validation is unknown")
    if not isinstance(review_boundary["published_coverage_eligible"], bool):
        raise ResolvedFormPackageError(
            "review_boundary.published_coverage_eligible must be a boolean"
        )
    has_unreviewed_boundary = (
        "agent_proposed" in review_boundary.values()
        or review_boundary["common_grants_model_validation"] == "not_validated"
        or compiler["verification"] == "manual_canary"
        or manifest["source_set"]["attestation"] == "snapshot_only"
        or manifest["source_set"]["closure"] != "complete"
    )
    if review_boundary["published_coverage_eligible"] and has_unreviewed_boundary:
        raise ResolvedFormPackageError(
            "published coverage requires reviewed projections, source-pinned model validation, "
            "and a content-addressed compiler"
        )

    artifacts = _object(manifest["artifacts"], "artifacts")
    _exact_keys(
        artifacts,
        {"json_schema", "ui_schema", "mappings", "rule_schema", "xml_transform"},
        "artifacts",
    )
    json_schema = _object(
        _load_artifact(package_root, artifacts["json_schema"], "artifacts.json_schema"),
        "json_schema",
    )
    ui_schema_raw = _array(
        _load_artifact(package_root, artifacts["ui_schema"], "artifacts.ui_schema"),
        "ui_schema",
    )
    if not all(isinstance(node, dict) for node in ui_schema_raw):
        raise ResolvedFormPackageError("ui_schema entries must be objects")
    ui_schema: list[dict[str, Any]] = ui_schema_raw
    mappings = _object(
        _load_artifact(package_root, artifacts["mappings"], "artifacts.mappings"),
        "mappings",
    )
    _exact_keys(mappings, {"x-mapping-from-cg", "x-mapping-to-cg"}, "mappings")
    _object(mappings["x-mapping-from-cg"], "mappings.x-mapping-from-cg")
    _object(mappings["x-mapping-to-cg"], "mappings.x-mapping-to-cg")
    _validate_package_cross_references(manifest, json_schema, mappings)

    rule_schema = None
    if artifacts["rule_schema"] is not None:
        rule_schema = _object(
            _load_artifact(package_root, artifacts["rule_schema"], "artifacts.rule_schema"),
            "rule_schema",
        )
    xml_transform = None
    if artifacts["xml_transform"] is not None:
        xml_transform = _object(
            _load_artifact(package_root, artifacts["xml_transform"], "artifacts.xml_transform"),
            "xml_transform",
        )

    dependency_paths = {manifest_path}
    source_set = manifest["source_set"]
    dependency_paths.add(
        _artifact_path(package_root, source_set["form"]["package_path"], "source_set.form")
    )
    dependency_paths.update(
        _artifact_path(package_root, question["package_path"], "source_set.question")
        for question in source_set["questions"]
    )
    dependency_paths.update(
        _artifact_path(package_root, descriptor["path"], f"artifacts.{name}")
        for name, descriptor in artifacts.items()
        if descriptor is not None
    )

    canonical_manifest = _canonical_json(manifest)
    package_digest = hashlib.sha256(canonical_manifest.encode("utf-8")).hexdigest()
    return ResolvedFormPackage(
        package_root=package_root,
        dependency_paths=tuple(sorted(dependency_paths)),
        package_digest=package_digest,
        _manifest_json=canonical_manifest,
        _json_schema_json=_canonical_json(json_schema),
        _ui_schema_json=_canonical_json(ui_schema),
        _mappings_json=_canonical_json(mappings),
        _rule_schema_json=_canonical_json(rule_schema) if rule_schema is not None else None,
        _xml_transform_json=(_canonical_json(xml_transform) if xml_transform is not None else None),
    )
