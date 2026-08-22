#!/usr/bin/env python3
"""Export decision tables directly from the portable form declarations."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Never

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from src.form_schema.portable_form_kernel import (  # ruff: ignore[module-import-not-at-top-of-file]
    PortableFormKernelError,
    load_portable_form_kernel,
)

VERSION = "0.1.0"
DEFAULT_OUTPUT = ROOT / "build" / "portable-form-artifacts" / "analysis"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def export(bundle_root: Path, output_dir: Path) -> dict[str, int]:
    kernel = load_portable_form_kernel(bundle_root)
    projection = kernel.analysis_projection()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(
        json.dumps(projection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    associations = projection["form_question_associations"]
    association_rows = [
        {
            **row,
            "occurrence_evidence": json.dumps(
                row["occurrence_evidence"], ensure_ascii=False, sort_keys=True
            ),
            "semantic_review": json.dumps(
                row["semantic_review"], ensure_ascii=False, sort_keys=True
            ),
        }
        for row in associations
    ]
    write_csv(
        output_dir / "form-question-map.csv",
        [
            "form_key",
            "occurrence_id",
            "question_id",
            "semantic_identity",
            "schema_id",
            "validation_fragment_id",
            "analysis_classification",
            "role",
            "form_pointer",
            "occurrence_evidence",
            "mapping_status",
            "semantic_review",
            "included_in_proposed_overlap",
            "included_in_accepted_overlap",
            "xml_path",
            "type_source",
            "type",
            "xsd_source",
        ],
        association_rows,
    )

    question_rows: list[dict[str, Any]] = []
    associations_by_question: dict[str, list[dict[str, Any]]] = {}
    for association in associations:
        if association["analysis_classification"] != "semantic_question":
            continue
        associations_by_question.setdefault(association["question_id"], []).append(
            association
        )
    count_by_question = {row["question_id"]: row for row in projection["questions"]}
    for question_id, rows in sorted(associations_by_question.items()):
        schema_ids = sorted({row["schema_id"] for row in rows})
        titles = sorted(
            {
                kernel.schemas_by_id[schema_id].get("title", question_id)
                for schema_id in schema_ids
            }
        )
        counts = count_by_question[question_id]
        question_rows.append(
            {
                "question_id": question_id,
                "question_title": " | ".join(titles),
                "schema_variant_count": len(schema_ids),
                "proposed_form_count": counts["proposed_form_count"],
                "accepted_form_count": counts["accepted_form_count"],
                "published_form_count": counts["published_form_count"],
            }
        )
    write_csv(
        output_dir / "questions.csv",
        [
            "question_id",
            "question_title",
            "schema_variant_count",
            "proposed_form_count",
            "accepted_form_count",
            "published_form_count",
        ],
        question_rows,
    )

    write_csv(
        output_dir / "role-qualified-questions.csv",
        [
            "semantic_identity",
            "question_id",
            "role",
            "proposed_form_count",
            "accepted_form_count",
            "published_form_count",
        ],
        projection["role_qualified_semantics"],
    )

    pair_rows: list[dict[str, Any]] = []
    template_pairs = {
        (pair["form_a"], pair["form_b"]): pair
        for pair in projection["pairwise_form_overlap"]
    }
    for pair in projection["pairwise_role_qualified_overlap"]:
        template = template_pairs[pair["form_a"], pair["form_b"]]
        proposed = pair["proposed_overlap"]
        accepted = pair["accepted_overlap"]
        proposed_template = template["proposed_overlap"]
        pair_rows.append(
            {
                "form_a": pair["form_a"],
                "form_b": pair["form_b"],
                "comparison_basis": pair["comparison_basis"],
                "proposed_similarity": proposed["similarity"],
                "proposed_questions_in_common": proposed["questions_in_common"],
                "proposed_unique_questions": proposed["unique_questions"],
                "form_a_proposed_coverage": proposed["form_a_coverage"],
                "form_b_proposed_coverage": proposed["form_b_coverage"],
                "template_proposed_similarity": proposed_template["similarity"],
                "template_proposed_questions_in_common": proposed_template[
                    "questions_in_common"
                ],
                "accepted_similarity": accepted["similarity"],
                "accepted_questions_in_common": accepted["questions_in_common"],
            }
        )
    write_csv(
        output_dir / "form-pairs.csv",
        [
            "form_a",
            "form_b",
            "comparison_basis",
            "proposed_similarity",
            "proposed_questions_in_common",
            "proposed_unique_questions",
            "form_a_proposed_coverage",
            "form_b_proposed_coverage",
            "template_proposed_similarity",
            "template_proposed_questions_in_common",
            "accepted_similarity",
            "accepted_questions_in_common",
        ],
        pair_rows,
    )

    form_rows: list[dict[str, Any]] = []
    for form_key, form in sorted(kernel.forms_by_key.items()):
        form_associations = [row for row in associations if row["form_key"] == form_key]
        review = form.definition["review_boundary"]
        form_rows.append(
            {
                "form_key": form_key,
                "form_name": form.definition["metadata"]["form_name"],
                "form_version": form.definition["metadata"]["form_version"],
                "semantic_question_occurrences": sum(
                    row["analysis_classification"] == "semantic_question"
                    for row in form_associations
                ),
                "content_capture_mechanisms": sum(
                    row["analysis_classification"] == "content_capture_mechanism"
                    for row in form_associations
                ),
                "semantic_mapping_status": review["semantic_mappings"]["status"],
                "published_coverage_eligible": review["published_coverage_eligible"],
                "production_ready": review["production_ready"],
            }
        )
    write_csv(
        output_dir / "forms.csv",
        [
            "form_key",
            "form_name",
            "form_version",
            "semantic_question_occurrences",
            "content_capture_mechanisms",
            "semantic_mapping_status",
            "published_coverage_eligible",
            "production_ready",
        ],
        form_rows,
    )
    return {
        "forms": len(form_rows),
        "questions": len(question_rows),
        "associations": len(associations),
        "pairs": len(pair_rows),
    }


class StructuredParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        sys.stdout.write(
            "error:\n"
            "  code: usage\n"
            "help:\n"
            "  command: python scripts/export_portable_form_analysis.py --help\n"
        )
        sys.stderr.write(f"{message}\n")
        raise SystemExit(2)


def parser() -> argparse.ArgumentParser:
    value = StructuredParser(
        prog="export-portable-form-analysis",
        description="Export analysis tables from the verified portable declarations.",
    )
    value.add_argument("--bundle", type=Path, default=ROOT / "form-specs")
    value.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    value.add_argument("--version", action="version", version=VERSION)
    return value


def cli(argv: list[str]) -> int:
    try:
        args = parser().parse_args(argv)
        counts = export(args.bundle, args.output_dir)
    except (OSError, ValueError, PortableFormKernelError) as exc:
        sys.stdout.write("error:\n  code: export_failed\n")
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write(
        "export:\n"
        "  status: generated\n"
        f"  forms: {counts['forms']}\n"
        f"  questions: {counts['questions']}\n"
        f"  associations: {counts['associations']}\n"
        f"  pairs: {counts['pairs']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
