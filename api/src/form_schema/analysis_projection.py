"""Deterministic analytical projections from resolved native form packages.

The projection is deliberately downstream of form compilation. It never decides that two
fields are semantically equivalent from labels. It uses only explicit semantic identifiers
carried by the package, and it keeps calculations, technical fields, and unresolved records
outside the applicant-question denominator.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.db.models.competition_models import Form

CONTRACT = "simpler-form-analysis-projection/v1"
VERSION = "0.1.0"


class AnalysisProjectionError(ValueError):
    """Raised when form packages cannot be projected without losing evidence."""


@dataclass(frozen=True)
class PackageInput:
    """A native form and the package evidence used to build it."""

    form_key: str
    package_dir: Path
    form: Form
    manifest: dict[str, Any]
    runtime_rules: dict[str, Any] | None


@dataclass(frozen=True)
class FieldRecord:
    form_key: str
    form_name: str
    form_version: str
    runtime_path: str
    xml_path: str
    label: str
    field_class: str
    canonical_question_id: str
    source_question_id: str
    mapping_status: str
    role: str
    dimensions: str
    component_ids: str
    json_type: str
    type_source: str
    type: str
    xsd_source: str
    xsd_sha256: str
    source_version: str
    published_coverage_eligible: bool


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisProjectionError(f"could not read JSON: {path}") from exc
    if not isinstance(value, dict):
        raise AnalysisProjectionError(f"expected an object: {path}")
    return value


def _manifest_form_key(manifest: Mapping[str, Any], package_dir: Path) -> str:
    form = manifest.get("form")
    if isinstance(form, dict):
        value = form.get("form_id") or form.get("short_form_name")
        if isinstance(value, str) and value:
            return value
    return package_dir.parents[3].name


def _candidate_short_name(package_dir: Path, manifest: Mapping[str, Any]) -> str | None:
    form = manifest.get("form")
    if isinstance(form, dict):
        short_name = form.get("short_form_name")
        if isinstance(short_name, str) and short_name:
            return short_name
    candidate_path = package_dir / "candidate.json"
    if candidate_path.is_file():
        candidate = _read_json(candidate_path)
        metadata = candidate.get("metadata")
        if isinstance(metadata, dict):
            short_name = metadata.get("short_form_name")
            if isinstance(short_name, str) and short_name:
                return short_name
    return None


def _validate_artifacts(package_dir: Path, manifest: Mapping[str, Any]) -> None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return
    for artifact_name, descriptor in artifacts.items():
        relative_path: object
        expected_sha256: object
        if isinstance(descriptor, str):
            relative_path = artifact_name
            expected_sha256 = descriptor
        elif isinstance(descriptor, dict):
            relative_path = descriptor.get("path")
            expected_sha256 = descriptor.get("sha256")
        elif descriptor is None:
            continue
        else:
            raise AnalysisProjectionError(
                f"invalid artifact descriptor in {package_dir / 'manifest.json'}: {artifact_name}"
            )
        if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
            raise AnalysisProjectionError(
                f"incomplete artifact descriptor in {package_dir / 'manifest.json'}: {artifact_name}"
            )
        artifact_path = package_dir / relative_path
        if not artifact_path.is_file():
            raise AnalysisProjectionError(f"missing pinned package artifact: {artifact_path}")
        if _sha256(artifact_path) != expected_sha256:
            raise AnalysisProjectionError(f"package artifact hash drift: {artifact_path}")


def discover_package_inputs(forms_root: Path, forms: Sequence[Form]) -> list[PackageInput]:
    """Discover source packages and bind them to their actual resolved native forms."""

    by_short_name = {form.short_form_name: form for form in forms}
    if len(by_short_name) != len(forms):
        raise AnalysisProjectionError("registered forms contain duplicate short_form_name values")
    by_form_type = {form.form_type.value: form for form in forms if form.form_type is not None}
    if len(by_form_type) != len([form for form in forms if form.form_type is not None]):
        raise AnalysisProjectionError("registered forms contain duplicate form_type values")

    discovered: list[PackageInput] = []
    seen_form_keys: set[str] = set()
    for manifest_path in sorted(forms_root.glob("*/1/0/*_package/manifest.json")):
        package_dir = manifest_path.parent
        manifest = _read_json(manifest_path)
        _validate_artifacts(package_dir, manifest)
        manifest_form_key = _manifest_form_key(manifest, package_dir)
        short_name = _candidate_short_name(package_dir, manifest)
        form = by_form_type.get(manifest_form_key)
        if form is None and short_name is not None:
            form = by_short_name.get(short_name)
        if form is None:
            raise AnalysisProjectionError(
                "package identity is not registered: "
                f"{manifest_form_key}/{short_name} ({package_dir})"
            )
        form_key = form.form_type.value if form.form_type is not None else manifest_form_key
        if form_key in seen_form_keys:
            raise AnalysisProjectionError(f"duplicate package form key: {form_key}")
        seen_form_keys.add(form_key)

        runtime_path = package_dir / "runtime-rules.json"
        runtime_rules = _read_json(runtime_path) if runtime_path.is_file() else None
        discovered.append(
            PackageInput(
                form_key=form_key,
                package_dir=package_dir,
                form=form,
                manifest=manifest,
                runtime_rules=runtime_rules,
            )
        )
    return discovered


def _source_evidence(package: PackageInput) -> tuple[str, str]:
    evidence = package.manifest.get("source_evidence")
    if isinstance(evidence, dict):
        xsd = evidence.get("xsd")
        if isinstance(xsd, dict):
            source = xsd.get("source_ref") or xsd.get("path") or ""
            digest = xsd.get("sha256") or ""
            return str(source), str(digest)

    source_set = package.manifest.get("source_set")
    if isinstance(source_set, dict):
        candidates: list[tuple[str, str]] = []
        values: list[object] = [source_set.get("form")]
        dependencies = source_set.get("dependencies")
        if isinstance(dependencies, list):
            values.extend(dependencies)
        for value in values:
            if not isinstance(value, dict):
                continue
            source_path = value.get("source_path")
            if isinstance(source_path, str) and source_path.lower().endswith(".xsd"):
                candidates.append((source_path, str(value.get("sha256") or "")))
        if len(candidates) == 1:
            return candidates[0]
    return "", ""


def _runtime_behavior_targets(
    runtime_rules: Mapping[str, Any] | None,
) -> tuple[set[str], set[str], set[str]]:
    calculations: set[str] = set()
    calculation_behavior_keys: set[str] = set()
    conditions: set[str] = set()
    if runtime_rules is None:
        return calculations, calculation_behavior_keys, conditions
    rules = runtime_rules.get("rules")
    if not isinstance(rules, list):
        raise AnalysisProjectionError("runtime-rules.json rules must be an array")
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise AnalysisProjectionError(f"runtime rule {index} must be an object")
        mechanism = rule.get("mechanism")
        source_value = rule.get("source_value")
        behavior_key = source_value.get("behavior_key") if isinstance(source_value, dict) else None
        if mechanism == "calculation" and isinstance(behavior_key, str) and behavior_key:
            calculation_behavior_keys.add(behavior_key)
        target = rule.get("target")
        path = target.get("path") if isinstance(target, dict) else None
        if not isinstance(path, str) or not path:
            continue
        if mechanism == "calculation":
            calculations.add(path)
        elif mechanism == "condition":
            conditions.add(path)
    return calculations, calculation_behavior_keys, conditions


def _walk_schema(
    node: Mapping[str, Any],
    path: tuple[tuple[str, bool], ...] = (),
) -> Iterator[tuple[tuple[tuple[str, bool], ...], Mapping[str, Any]]]:
    node_type = node.get("type")
    if node_type == "object":
        properties = node.get("properties", {})
        if not isinstance(properties, dict):
            raise AnalysisProjectionError("object schema properties must be an object")
        for name, child in properties.items():
            if not isinstance(name, str) or not isinstance(child, dict):
                raise AnalysisProjectionError("schema properties must contain object children")
            yield from _walk_schema(child, path + ((name, False),))
        return
    if node_type == "array":
        items = node.get("items")
        if not isinstance(items, dict) or not path:
            raise AnalysisProjectionError("array schema must have object items below a property")
        array_path = path[:-1] + ((path[-1][0], True),)
        yield from _walk_schema(items, array_path)
        return
    yield path, node


def _runtime_path(path: tuple[tuple[str, bool], ...]) -> str:
    return ".".join(f"{name}[]" if repeated else name for name, repeated in path)


def _authoring(node: Mapping[str, Any]) -> Mapping[str, Any]:
    value = node.get("x-authoring")
    return value if isinstance(value, dict) else {}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _semantic_identity(node: Mapping[str, Any]) -> tuple[str, str, str]:
    mapping = node.get("x-semantic-mapping")
    if isinstance(mapping, dict):
        concept_id = mapping.get("concept_id")
        status = mapping.get("status")
        if isinstance(concept_id, str) and concept_id:
            return concept_id, str(status or "unreviewed"), str(node.get("x-question-key") or "")

    authoring = _authoring(node)
    candidates = _strings(authoring.get("semantic_candidates"))
    statuses = _strings(authoring.get("review_statuses"))
    node_id = authoring.get("node_id")
    if len(candidates) == 1:
        return (
            candidates[0],
            statuses[0] if len(statuses) == 1 else "unreviewed",
            str(node_id or ""),
        )
    return "", "unmapped", str(node.get("x-question-key") or node_id or "")


def _xml_type(node: Mapping[str, Any]) -> tuple[str, str]:
    authoring = _authoring(node)
    type_source = node.get("x-xml-type-source") or authoring.get("type_source") or ""
    xml_type = node.get("x-xml-type") or authoring.get("xml_type") or ""
    return str(type_source), str(xml_type)


def project_fields(package: PackageInput) -> tuple[list[FieldRecord], list[dict[str, str]]]:
    """Project all source-bound leaf fields and report semantic contradictions."""

    calculations, calculation_behavior_keys, _ = _runtime_behavior_targets(package.runtime_rules)
    xsd_source, xsd_sha256 = _source_evidence(package)
    boundary = package.manifest.get("review_boundary")
    publishable = bool(
        isinstance(boundary, dict) and boundary.get("published_coverage_eligible") is True
    )

    records: list[FieldRecord] = []
    exceptions: list[dict[str, str]] = []
    seen_source_paths: set[str] = set()
    for path, node in _walk_schema(package.form.form_json_schema):
        runtime_path = _runtime_path(path)
        authoring = _authoring(node)
        source_path = node.get("x-source-path") or authoring.get("source_path") or ""
        if not isinstance(source_path, str):
            raise AnalysisProjectionError(
                f"{package.form_key} contains a non-string source path: {runtime_path}"
            )
        if source_path and source_path in seen_source_paths:
            raise AnalysisProjectionError(
                f"{package.form_key} contains duplicate source path: {source_path}"
            )
        if source_path:
            seen_source_paths.add(source_path)

        canonical_id, mapping_status, source_question_id = _semantic_identity(node)
        declared_kind = str(authoring.get("record_kind") or "")
        behavior_keys = set(_strings(authoring.get("behavior_keys")))
        modules = _strings(authoring.get("modules"))
        is_calculation = (
            source_path in calculations
            or bool(behavior_keys & calculation_behavior_keys)
            or "budget-calculation" in modules
            or node.get("readOnly") is True
            or node.get("x-interaction") == "computed"
            or declared_kind == "derived_calculation"
        )
        is_technical = (
            node.get("x-interaction") == "hidden"
            or declared_kind == "technical_field"
            or (source_path and source_path.rsplit(".", 1)[-1].startswith("ATT"))
        )
        if is_calculation:
            field_class = "calculation"
        elif is_technical:
            field_class = "technical_field"
        elif canonical_id:
            field_class = "question"
        else:
            field_class = "unmapped_field"

        if field_class != "question" and canonical_id:
            exceptions.append(
                {
                    "form_key": package.form_key,
                    "runtime_path": runtime_path,
                    "xml_path": source_path,
                    "exception": f"{field_class}_has_semantic_mapping",
                    "canonical_question_id": canonical_id,
                    "resolution": "excluded_from_question_denominator",
                }
            )
            canonical_id = ""
            mapping_status = "excluded_non_question"

        roles = _strings(authoring.get("roles"))
        dimensions = _strings(authoring.get("dimensions"))
        type_source, xml_type = _xml_type(node)
        source_ref = authoring.get("source_ref")
        source_version = authoring.get("source_version")
        records.append(
            FieldRecord(
                form_key=package.form_key,
                form_name=package.form.form_name,
                form_version=package.form.form_version,
                runtime_path=runtime_path,
                xml_path=source_path,
                label=str(node.get("title") or runtime_path.rsplit(".", 1)[-1]),
                field_class=field_class,
                canonical_question_id=canonical_id,
                source_question_id=source_question_id,
                mapping_status=mapping_status,
                role="|".join(roles),
                dimensions="|".join(dimensions),
                component_ids="|".join(modules),
                json_type=str(node.get("type") or ""),
                type_source=type_source,
                type=xml_type,
                xsd_source=str(source_ref or xsd_source),
                xsd_sha256=xsd_sha256,
                source_version=str(source_version or ""),
                published_coverage_eligible=publishable and mapping_status == "accepted",
            )
        )
    return records, exceptions


def _question_rows(fields: Sequence[FieldRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[FieldRecord]] = defaultdict(list)
    for field in fields:
        if field.field_class == "question" and field.canonical_question_id:
            grouped[field.canonical_question_id].append(field)

    rows: list[dict[str, Any]] = []
    for question_id, occurrences in sorted(grouped.items()):
        forms = sorted({item.form_key for item in occurrences})
        statuses = sorted({item.mapping_status for item in occurrences})
        labels = sorted({item.label for item in occurrences})
        rows.append(
            {
                "canonical_question_id": question_id,
                "label": labels[0],
                "label_variants": "|".join(labels),
                "form_count": len(forms),
                "forms": "|".join(forms),
                "mapping_statuses": "|".join(statuses),
                "published_coverage_eligible": all(
                    item.published_coverage_eligible for item in occurrences
                ),
            }
        )
    return rows


def _association_rows(fields: Sequence[FieldRecord]) -> list[dict[str, Any]]:
    rows = [
        asdict(field)
        for field in fields
        if field.field_class == "question" and field.canonical_question_id
    ]
    return sorted(
        rows,
        key=lambda row: (
            str(row["form_key"]),
            str(row["canonical_question_id"]),
            str(row["runtime_path"]),
        ),
    )


def _pair_rows(fields: Sequence[FieldRecord], form_keys: Sequence[str]) -> list[dict[str, Any]]:
    by_form: dict[str, set[str]] = {form_key: set() for form_key in form_keys}
    accepted_by_form: dict[str, set[str]] = {form_key: set() for form_key in form_keys}
    for field in fields:
        if field.field_class != "question" or not field.canonical_question_id:
            continue
        by_form[field.form_key].add(field.canonical_question_id)
        if field.mapping_status == "accepted":
            accepted_by_form[field.form_key].add(field.canonical_question_id)

    rows: list[dict[str, Any]] = []
    for index, form_a in enumerate(form_keys):
        for form_b in form_keys[index + 1 :]:
            a = by_form[form_a]
            b = by_form[form_b]
            common = a & b
            union = a | b
            accepted_a = accepted_by_form[form_a]
            accepted_b = accepted_by_form[form_b]
            accepted_common = accepted_a & accepted_b
            accepted_union = accepted_a | accepted_b
            rows.append(
                {
                    "form_a": form_a,
                    "form_b": form_b,
                    "questions_a": len(a),
                    "questions_b": len(b),
                    "questions_common": len(common),
                    "questions_union": len(union),
                    "similarity": len(common) / len(union) if union else "",
                    "percent_a_shared_by_b": len(common) / len(a) if a else "",
                    "percent_b_shared_by_a": len(common) / len(b) if b else "",
                    "mapping_basis": "working_explicit_semantic_ids",
                    "accepted_questions_common": len(accepted_common),
                    "accepted_questions_union": len(accepted_union),
                    "accepted_similarity": (
                        len(accepted_common) / len(accepted_union) if accepted_union else ""
                    ),
                }
            )
    return rows


def build_projection(packages: Sequence[PackageInput]) -> dict[str, Any]:
    """Build all analysis tables from native packages without mutating them."""

    form_keys = [package.form_key for package in packages]
    if len(set(form_keys)) != len(form_keys):
        raise AnalysisProjectionError("package inputs contain duplicate form keys")

    fields: list[FieldRecord] = []
    exceptions: list[dict[str, str]] = []
    form_rows: list[dict[str, Any]] = []
    for package in sorted(packages, key=lambda value: value.form_key):
        package_fields, package_exceptions = project_fields(package)
        fields.extend(package_fields)
        exceptions.extend(package_exceptions)
        classes: dict[str, int] = defaultdict(int)
        unique_questions: set[str] = set()
        for field in package_fields:
            classes[field.field_class] += 1
            if field.field_class == "question" and field.canonical_question_id:
                unique_questions.add(field.canonical_question_id)
        form_rows.append(
            {
                "form_key": package.form_key,
                "form_name": package.form.form_name,
                "form_version": package.form.form_version,
                "short_form_name": package.form.short_form_name,
                "package_contract": str(package.manifest.get("contract") or ""),
                "question_occurrences": classes["question"],
                "unique_questions": len(unique_questions),
                "calculation_fields": classes["calculation"],
                "technical_fields": classes["technical_field"],
                "unmapped_fields": classes["unmapped_field"],
                "semantic_exceptions": len(package_exceptions),
                "published_coverage_eligible": False,
            }
        )

    field_rows = [asdict(field) for field in fields]
    question_rows = _question_rows(fields)
    association_rows = _association_rows(fields)
    pair_rows = _pair_rows(fields, sorted(form_keys))
    return {
        "contract": CONTRACT,
        "summary": {
            "forms": len(packages),
            "fields": len(field_rows),
            "canonical_questions": len(question_rows),
            "form_question_associations": len(association_rows),
            "form_pairs": len(pair_rows),
            "semantic_exceptions": len(exceptions),
            "accepted_mappings": sum(
                field.mapping_status == "accepted" and field.field_class == "question"
                for field in fields
            ),
            "published_coverage_eligible": False,
            "quality_status": (
                "needs_reconciliation"
                if exceptions or any(row["unmapped_fields"] for row in form_rows)
                else "provisional_clean"
            ),
        },
        "forms": form_rows,
        "questions": question_rows,
        "form_questions": association_rows,
        "form_pairs": pair_rows,
        "fields": field_rows,
        "exceptions": sorted(
            exceptions,
            key=lambda row: (row["form_key"], row["runtime_path"], row["exception"]),
        ),
        "claims_boundary": {
            "working_metrics": "explicit semantic identifiers carried by implementation packages",
            "accepted_metrics": "accepted mappings only",
            "calculated_outputs": "excluded from applicant-question denominators",
            "technical_fields": "excluded from applicant-question denominators",
            "missing_xml_types": "reported as evidence gaps and never inferred from JSON types",
        },
    }


def _csv_value(value: object) -> object:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> int:
    if rows:
        fieldnames = list(rows[0])
        if any(list(row) != fieldnames for row in rows):
            raise AnalysisProjectionError(f"CSV rows have inconsistent columns: {path.name}")
    else:
        fieldnames = []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        if fieldnames:
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _csv_value(value) for key, value in row.items()})
    return len(rows)


def write_projection(output_dir: Path, projection: Mapping[str, Any]) -> dict[str, Any]:
    """Write deterministic JSON and CSV artifacts and return their digest manifest."""

    output_dir.mkdir(parents=True, exist_ok=True)
    table_names = ("forms", "questions", "form_questions", "form_pairs", "fields", "exceptions")
    outputs: list[dict[str, Any]] = []
    for name in table_names:
        rows = projection.get(name)
        if not isinstance(rows, list):
            raise AnalysisProjectionError(f"projection.{name} must be an array")
        path = output_dir / f"{name}.csv"
        count = _write_csv(path, rows)
        outputs.append({"name": name, "path": path.name, "rows": count, "sha256": _sha256(path)})

    data_path = output_dir / "projection.json"
    data_path.write_text(
        json.dumps(projection, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    outputs.append(
        {
            "name": "projection",
            "path": data_path.name,
            "rows": 1,
            "sha256": _sha256(data_path),
        }
    )
    manifest = {
        "contract": CONTRACT,
        "summary": projection["summary"],
        "outputs": outputs,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def select_packages(packages: Iterable[PackageInput], form_keys: set[str]) -> list[PackageInput]:
    values = list(packages)
    if not form_keys:
        return values
    by_key = {package.form_key: package for package in values}
    missing = sorted(form_keys - set(by_key))
    if missing:
        raise AnalysisProjectionError(f"unknown form keys: {', '.join(missing)}")
    return [by_key[key] for key in sorted(form_keys)]
