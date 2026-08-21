"""Verify and report the source-authored SF-424 SGM contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .source_authored_sgm import (
    SourceAuthoredSGMError,
    compile_source_authored_sgm,
    declaration_summary,
    json_sha,
    load_json,
    sha256,
)


def compile_sf424_source_authored(
    root: str | Path, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    root = Path(root)
    if config is None:
        config = load_json(root / "harness/sgm/source-authored/SF424.json")
    if config.get("form_id") != "SF424":
        raise SourceAuthoredSGMError("Expected SF424 source-authored config")
    return compile_source_authored_sgm(root, config)


def verify_sf424_source_authored(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    config_path = root / "harness/sgm/source-authored/SF424.json"
    config = load_json(config_path)
    generated = compile_sf424_source_authored(root, config)
    oracle_path = root / "artifacts/sgm/ready-six-shadow-targets.json"
    oracle = load_json(oracle_path)
    target = next(item for item in oracle["forms"] if item["form_id"] == "SF424")
    expected = {"metadata": target["metadata"], "artifacts": target["artifacts"]}
    if generated != expected:
        raise SourceAuthoredSGMError(
            "Source-authored SF424 does not exactly match the pinned SGM oracle"
        )
    digests = {
        layer: f"sha256:{json_sha(value)}" for layer, value in generated["artifacts"].items()
    }
    if digests != target["artifact_digests"]:
        raise SourceAuthoredSGMError("SF424 oracle artifact-digest mismatch")
    inputs = {
        name: {"path": item["path"], "sha256": item["sha256"]}
        for name, item in config["inputs"].items()
    }
    pdf = load_json(root / inputs["pdf_reconciliation"]["path"])
    return {
        "format_version": 1,
        "form_id": "SF424",
        "status": "source_authored_explicit_declaration_oracle_exact",
        "exact_target_match": True,
        "production_ready": False,
        "config": {
            "path": str(config_path.relative_to(root)),
            "sha256": sha256(config_path),
        },
        "source_inputs": inputs,
        "oracle": {
            "path": str(oracle_path.relative_to(root)),
            "sha256": sha256(oracle_path),
            "sgm_revision": oracle["source"]["revision"],
            "artifact_digests": target["artifact_digests"],
        },
        "generated_artifact_digests": digests,
        "generation_method": {
            "kind": "explicit_declaration_materialization",
            "declaration_values_embedded": True,
            "operational_component_composition": False,
            "catalog_role": "pinned_provenance_conventions_only",
        },
        "declarations": declaration_summary(config),
        "source_accounting": config["source_accounting"],
        "evidence_assertions": config["evidence_assertions"],
        "dimension_assertions": config["dimension_assertions"],
        "static_assertion": config["static_assertion"],
        "rendered_pdf_pages_reviewed": sum(
            source["reviewed_pages"] for source in pdf["source_artifacts"]
        ),
        "semantic_mapping_status": "agent_proposed",
        "policy_review_status": "agent_proposed",
        "human_acceptance_status": "not_requested",
        "accessibility_validation_status": "not_performed",
        "claims_boundary": config["claims_boundary"],
    }


def render_sf424_source_authored(report: dict[str, Any]) -> str:
    dimensions = report["dimension_assertions"]
    declarations = report["declarations"]
    return "\n".join(
        [
            "# SF-424 source-authored SGM parity",
            "",
            "The complete SGM contract is materialized from explicit source-bound declarations and SGM conventions, then compared with the pinned SGM target only as an oracle.",
            "",
            "- Exact target match: yes",
            "- Production ready: no",
            "- Generation method: explicit declaration materialization (not operational reusable-module composition)",
            f"- Countable source paths accounted for: {report['source_accounting']['countable_paths']}",
            f"- Cardinality/constraint signature: `{report['source_accounting']['cardinality_constraint_signature_sha256']}`",
            f"- JSON properties: {declarations['json_properties']}",
            f"- UI nodes: {declarations['ui_nodes']}",
            f"- Rules: {declarations['rules']}",
            f"- XML mappings: {declarations['xml_mappings']}",
            f"- Nested groups: {dimensions['nested_groups']['count']}",
            f"- Repetition structures: {dimensions['repetition']['count']}",
            f"- Enumerations: {dimensions['enumerations']['count']}",
            f"- Conditions: {dimensions['conditions']['count']}",
            f"- Calculations: {dimensions['calculations']['count']}",
            f"- Static certification items: {report['static_assertion']['count']}",
            f"- Rendered PDF pages reviewed: {report['rendered_pdf_pages_reviewed']}",
            "- Semantic mapping status: agent_proposed",
            "- Policy review status: agent_proposed",
            "",
            "## Claims boundary",
            "",
            report["claims_boundary"],
            "",
        ]
    )


def write_sf424_source_authored_artifacts(root: str | Path) -> tuple[Path, Path]:
    root = Path(root)
    report = verify_sf424_source_authored(root)
    json_path = root / "artifacts/sgm/sf424-source-authored-parity.json"
    md_path = root / "artifacts/sgm/sf424-source-authored-parity.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render_sf424_source_authored(report))
    return json_path, md_path
