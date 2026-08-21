"""Fail-closed compiler for explicit source-authored SGM contracts."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


class SourceAuthoredSGMError(ValueError):
    """Raised when an explicit source-authored contract is incomplete or drifts."""


LAYERS = ("json_schema", "ui_schema", "rule_schema", "xml_transform")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SourceAuthoredSGMError(f"Expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_sha(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise SourceAuthoredSGMError(f"Expected JSONL objects: {path}")
    paths = [row.get("path") for row in rows]
    if None in paths or len(paths) != len(set(paths)):
        raise SourceAuthoredSGMError(f"Duplicate or missing source paths: {path}")
    return rows


def _verify_inputs(root: Path, config: dict[str, Any]) -> None:
    for name, item in config["inputs"].items():
        path = root / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise SourceAuthoredSGMError(f"Source-authored input drift: {name}")


def _verify_evidence_links(root: Path, config: dict[str, Any]) -> None:
    inputs = config["inputs"]
    assertions = config["evidence_assertions"]
    behavior_path = root / inputs["behavior_artifact"]["path"]
    behavior_rows = _load_jsonl(behavior_path)
    behaviors = [behavior for row in behavior_rows for behavior in row.get("behaviors", [])]
    if len(behavior_rows) != assertions["behavior_records"]:
        raise SourceAuthoredSGMError("Behavior record-count drift")
    if len(behaviors) != assertions["behaviors"]:
        raise SourceAuthoredSGMError("Behavior-count drift")
    dat_digest = inputs["dat"]["sha256"]
    dat_path = inputs["dat"]["path"]
    for behavior in behaviors:
        if behavior.get("form_id") != config["form_id"]:
            raise SourceAuthoredSGMError("Behavior form identity drift")
        expected_provenance = f"sha256:{dat_digest} {dat_path}"
        if expected_provenance not in behavior.get("provenance", []):
            raise SourceAuthoredSGMError("Behavior/DAT provenance drift")

    contract = load_json(root / inputs["normalized_contract"]["path"])
    if contract["source_artifact"]["sha256"] != inputs["source_records"]["sha256"]:
        raise SourceAuthoredSGMError("Normalized-contract source-record drift")
    if contract["behavior_artifact"]["sha256"] != inputs["behavior_artifact"]["sha256"]:
        raise SourceAuthoredSGMError("Normalized-contract behavior drift")
    if contract["upstream_alignment"]["sha256"] != inputs["common_grants_baseline"]["sha256"]:
        raise SourceAuthoredSGMError("CommonGrants provenance drift")
    static_evidence = contract["dimension_evidence"]["static_assurances"]
    if static_evidence["source_artifact"]["sha256"] != inputs["static_catalog"]["sha256"]:
        raise SourceAuthoredSGMError("Static-content provenance drift")

    pdf = load_json(root / inputs["pdf_reconciliation"]["path"])
    reviewed_pages = sum(source["reviewed_pages"] for source in pdf["source_artifacts"])
    if reviewed_pages != assertions["rendered_pdf_pages"]:
        raise SourceAuthoredSGMError("Rendered-page review count drift")
    readonly = next(
        source
        for source in pdf["source_artifacts"]
        if source["artifact_role"] == "readonly_rendering"
    )
    if readonly["sha256"] != assertions["static_pdf_sha256"]:
        raise SourceAuthoredSGMError("Static catalog/PDF source drift")
    static_catalog = load_json(root / inputs["static_catalog"]["path"])
    if static_catalog["source"]["sha256"] != readonly["sha256"]:
        raise SourceAuthoredSGMError("Static catalog does not cite pinned read-only PDF")


def _declarations(config: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    authoring = config["authoring"]
    result = []
    for item in authoring["json_properties"]:
        result.append(("json_schema", item["name"], item))
    for ordinal, item in enumerate(authoring["ui_nodes"]):
        result.append(("ui_schema", str(ordinal), item))
    for item in authoring["rules"]:
        result.append(("rule_schema", item["name"], item))
    for item in authoring["xml_mappings"]:
        result.append(("xml_transform", item["name"], item))
    return result


def compile_source_authored_sgm(root: str | Path, config: dict[str, Any]) -> dict[str, Any]:
    """Compile explicit declarations after complete source and dimension accounting."""

    root = Path(root)
    if (
        config.get("format_version") != 1
        or config.get("projection_type") != "source_authored_sgm_contract"
    ):
        raise SourceAuthoredSGMError("Unsupported source-authored SGM config")
    _verify_inputs(root, config)
    _verify_evidence_links(root, config)
    source_path = root / config["inputs"]["source_records"]["path"]
    rows = _load_jsonl(source_path)
    countable = {row["path"] for row in rows if row.get("countable") is True}
    countable_records = [row for row in rows if row.get("countable") is True]
    containers = {row["path"] for row in rows if row.get("record_kind") == "container"}
    technical = {row["path"] for row in rows if row.get("record_kind") == "technical_field"}
    expected = config["source_accounting"]
    if len(countable) != expected["countable_paths"]:
        raise SourceAuthoredSGMError("Countable source-path total drift")
    cardinality_signature = json_sha(
        [
            {
                key: row.get(key)
                for key in (
                    "path",
                    "required",
                    "min_occurs",
                    "max_occurs",
                    "data_type",
                    "constraints",
                )
            }
            for row in countable_records
        ]
    )
    if cardinality_signature != expected["cardinality_constraint_signature_sha256"]:
        raise SourceAuthoredSGMError("Cardinality/constraint source signature drift")
    if len(containers) != expected["container_paths"]:
        raise SourceAuthoredSGMError("Container source-path total drift")
    if len(technical) != expected["technical_paths"]:
        raise SourceAuthoredSGMError("Technical source-path total drift")

    used: set[str] = set()
    seen: set[tuple[str, str]] = set()
    declarations = _declarations(config)
    for layer, key, declaration in declarations:
        identity = (layer, key)
        if identity in seen:
            raise SourceAuthoredSGMError(f"Duplicate declaration: {layer} {key}")
        seen.add(identity)
        source_paths = declaration.get("source_paths")
        if not isinstance(source_paths, list) or not source_paths:
            raise SourceAuthoredSGMError(f"Unbound declaration: {layer} {key}")
        unknown = set(source_paths) - countable
        if unknown:
            raise SourceAuthoredSGMError(
                f"Unknown or non-countable declaration paths: {layer} {key}: {sorted(unknown)}"
            )
        if declaration.get("evidence_status") != "source_bound":
            raise SourceAuthoredSGMError(f"Unsupported evidence status: {layer} {key}")
        if "value" not in declaration:
            raise SourceAuthoredSGMError(f"Missing declaration value: {layer} {key}")
        used.update(source_paths)
    missing = countable - used
    if missing:
        raise SourceAuthoredSGMError(f"Unaccounted countable source paths: {sorted(missing)}")

    contract = load_json(root / config["inputs"]["normalized_contract"]["path"])
    actual_dimensions = contract["dimension_evidence"]
    for dimension, assertion in config["dimension_assertions"].items():
        actual = actual_dimensions.get(dimension)
        if actual is None:
            raise SourceAuthoredSGMError(f"Missing normalized dimension: {dimension}")
        if actual.get("status") != "encoded" or actual.get("count") != assertion["count"]:
            raise SourceAuthoredSGMError(f"Dimension drift: {dimension}")
        if sorted(actual.get("paths", [])) != sorted(assertion.get("paths", [])):
            raise SourceAuthoredSGMError(f"Dimension path drift: {dimension}")
    static = config["static_assertion"]
    static_actual = actual_dimensions.get("static_assurances", {})
    if (
        static_actual.get("status") != "encoded"
        or static_actual.get("count") != static["count"]
        or static_actual.get("content_ids") != static["content_ids"]
    ):
        raise SourceAuthoredSGMError("Static-content dimension drift")

    pdf = load_json(root / config["inputs"]["pdf_reconciliation"]["path"])
    if (
        pdf.get("review_state") != "agent_visual_source_review_complete"
        or pdf.get("source_coverage", {}).get("ocr_used") is not False
        or pdf.get("source_coverage", {}).get("all_rendered_pages_agent_read") is not True
    ):
        raise SourceAuthoredSGMError("SF424 rendered-page evidence gate is not passing")

    authoring = config["authoring"]
    json_schema = deepcopy(authoring["json_schema_base"])
    json_schema["properties"] = {
        item["name"]: deepcopy(item["value"]) for item in authoring["json_properties"]
    }
    xml = {"_xml_config": deepcopy(authoring["xml_config"])}
    xml.update({item["name"]: deepcopy(item["value"]) for item in authoring["xml_mappings"]})
    return {
        "metadata": deepcopy(config["metadata"]),
        "artifacts": {
            "json_schema": json_schema,
            "ui_schema": [deepcopy(item["value"]) for item in authoring["ui_nodes"]],
            "rule_schema": {item["name"]: deepcopy(item["value"]) for item in authoring["rules"]},
            "xml_transform": xml,
        },
    }


def declaration_summary(config: dict[str, Any]) -> dict[str, int]:
    authoring = config["authoring"]
    return {
        "json_properties": len(authoring["json_properties"]),
        "ui_nodes": len(authoring["ui_nodes"]),
        "rules": len(authoring["rules"]),
        "xml_mappings": len(authoring["xml_mappings"]),
    }
