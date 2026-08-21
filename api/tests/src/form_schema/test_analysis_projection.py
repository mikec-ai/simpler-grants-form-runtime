import copy
import csv
import json
from pathlib import Path

import pytest

from src.form_schema.analysis_projection import (
    AnalysisProjectionError,
    build_projection,
    discover_package_inputs,
    project_fields,
    select_packages,
    write_projection,
)
from src.form_schema.analysis_projection_cli import main
from src.form_schema.forms import _ALL_FORMS

FORMS_ROOT = Path(__file__).parents[3] / "src" / "form_schema" / "forms"
COMMITTED_OUTPUT = Path(__file__).parents[4] / "documentation" / "form-analysis"


def _packages():
    return discover_package_inputs(FORMS_ROOT, _ALL_FORMS)


def test_discovery_reads_actual_registered_implementation_packages() -> None:
    packages = _packages()
    keys = {package.form_key for package in packages}
    assert keys == {
        "PHSFellowshipSupplemental",
        "RRBudget",
        "RRBudget10",
        "RRMPBudget",
        "RRMPSubawardBudget",
        "RRSF424",
        "RRSubawardBudget10_30",
        "RRSubawardBudget30",
        "SF424",
    }
    assert len({package.form.short_form_name for package in packages}) == 9


def test_projection_excludes_calculations_from_question_denominator() -> None:
    package = next(package for package in _packages() if package.form_key == "RRMPBudget")
    fields, exceptions = project_fields(package)
    calculations = [field for field in fields if field.field_class == "calculation"]
    assert len(calculations) == 43
    assert all(field.canonical_question_id == "" for field in calculations)
    assert exceptions == []


def test_structurally_equivalent_subaward_variants_share_one_denominator() -> None:
    packages = select_packages(_packages(), {"RRSubawardBudget30", "RRSubawardBudget10_30"})
    projection = build_projection(packages)
    forms = {row["form_key"]: row for row in projection["forms"]}
    assert forms["RRSubawardBudget30"]["calculation_fields"] == 56
    assert forms["RRSubawardBudget10_30"]["calculation_fields"] == 56
    assert forms["RRSubawardBudget30"]["question_occurrences"] == 98
    assert forms["RRSubawardBudget10_30"]["question_occurrences"] == 98
    assert forms["RRSubawardBudget30"]["unique_questions"] == 44
    assert forms["RRSubawardBudget10_30"]["unique_questions"] == 43
    assert projection["summary"]["semantic_exceptions"] == 0
    assert projection["summary"]["published_coverage_eligible"] is False


def test_sf424_projects_complete_source_bound_question_metadata() -> None:
    projection = build_projection(select_packages(_packages(), {"SF424"}))
    form = projection["forms"][0]
    assert form["unmapped_fields"] == 0
    assert form["question_occurrences"] == 71
    assert form["calculation_fields"] == 1
    assert form["attachment_fields"] == 4
    assert form["technical_fields"] == 20
    assert form["semantic_exceptions"] == 0
    assert projection["summary"]["published_coverage_eligible"] is False


def test_backfilled_forms_preserve_complete_question_level_xml_evidence() -> None:
    for package in _packages():
        metadata = package.form.form_json_schema.get("x-simpler-field-metadata")
        assert metadata is not None, package.form_key
        fields, _ = project_fields(package)
        questions = [field for field in fields if field.field_class == "question"]
        assert questions, package.form_key
        assert all(field.xml_path for field in questions), package.form_key
        assert all(field.type_source for field in questions), package.form_key
        assert all(field.type for field in questions), package.form_key
        assert all(field.xsd_source for field in questions), package.form_key
        assert all(field.xsd_sha256 for field in questions), package.form_key
        assert all(field.cardinality_maximum for field in questions), package.form_key


def test_missing_semantic_mapping_is_an_explicit_reconciliation_item() -> None:
    projection = build_projection(select_packages(_packages(), {"RRBudget"}))
    assert projection["summary"]["semantic_exceptions"] == 4
    assert {row["resolution"] for row in projection["exceptions"]} == {"requires_semantic_mapping"}
    assert projection["summary"]["published_coverage_eligible"] is False


def test_versioned_field_metadata_projects_without_reclassification() -> None:
    projection = build_projection(select_packages(_packages(), {"PHSFellowshipSupplemental"}))
    form = projection["forms"][0]
    assert form["question_occurrences"] == 47
    assert form["unique_questions"] == 37
    assert form["calculation_fields"] == 2
    assert form["attachment_fields"] == 17
    assert form["technical_fields"] == 99
    assert form["semantic_exceptions"] == 0
    assert len(projection["form_questions"]) == 47
    assert all(row["type_source"] for row in projection["form_questions"])
    assert all(row["type"] for row in projection["form_questions"])
    assert all(row["xsd_source"] for row in projection["form_questions"])
    assert any(row["source_behavior_ids"] for row in projection["form_questions"])
    assert any(row["runtime_behavior_rule_ids"] for row in projection["form_questions"])
    assert all(row["cardinality_maximum"] for row in projection["form_questions"])


def test_versioned_field_metadata_counting_contradiction_fails_closed() -> None:
    package = copy.deepcopy(
        next(package for package in _packages() if package.form_key == "PHSFellowshipSupplemental")
    )
    metadata = package.form.form_json_schema["x-simpler-field-metadata"]
    record = next(
        record for record in metadata["records"] if record["classification"] == "calculated_output"
    )
    record["counts_as_applicant_question"] = True
    with pytest.raises(AnalysisProjectionError, match="classification/counting contradiction"):
        project_fields(package)


def test_versioned_field_metadata_dangling_pointer_fails_closed() -> None:
    package = copy.deepcopy(
        next(package for package in _packages() if package.form_key == "PHSFellowshipSupplemental")
    )
    metadata = package.form.form_json_schema["x-simpler-field-metadata"]
    record = next(
        record for record in metadata["records"] if record["classification"] == "applicant_question"
    )
    record["runtime_schema_pointer"] = "/properties/not_a_real_field"
    with pytest.raises(AnalysisProjectionError, match="dangling schema pointer"):
        project_fields(package)


def test_pairwise_metrics_are_directional_and_set_based() -> None:
    projection = build_projection(select_packages(_packages(), {"RRBudget", "RRBudget10"}))
    [pair] = projection["form_pairs"]
    assert pair["form_a"] == "RRBudget"
    assert pair["form_b"] == "RRBudget10"
    assert pair["questions_common"] > 0
    assert pair["similarity"] == pytest.approx(pair["questions_common"] / pair["questions_union"])
    assert pair["percent_a_shared_by_b"] == pytest.approx(
        pair["questions_common"] / pair["questions_a"]
    )
    assert pair["percent_b_shared_by_a"] == pytest.approx(
        pair["questions_common"] / pair["questions_b"]
    )
    assert pair["accepted_similarity"] == ""


def test_output_is_deterministic_and_preserves_billys_xml_columns(tmp_path: Path) -> None:
    projection = build_projection(select_packages(_packages(), {"RRBudget", "RRBudget10"}))
    first = write_projection(tmp_path / "first", projection)
    second = write_projection(tmp_path / "second", projection)
    assert first == second
    for output in first["outputs"]:
        assert (tmp_path / "first" / output["path"]).read_bytes() == (
            tmp_path / "second" / output["path"]
        ).read_bytes()

    with (tmp_path / "first" / "form_questions.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert {"xml_path", "type_source", "type", "xsd_source", "xsd_sha256"} <= set(rows[0])
    assert all(row["xml_path"] for row in rows)
    assert all(row["xsd_source"] for row in rows)


def test_committed_projection_is_current(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    manifest = write_projection(generated, build_projection(_packages()))
    for output in manifest["outputs"]:
        path = output["path"]
        assert generated.joinpath(path).read_bytes() == COMMITTED_OUTPUT.joinpath(path).read_bytes()
    assert (
        generated.joinpath("manifest.json").read_bytes()
        == COMMITTED_OUTPUT.joinpath("manifest.json").read_bytes()
    )


def test_unknown_form_fails_closed() -> None:
    with pytest.raises(AnalysisProjectionError, match="unknown form keys"):
        select_packages(_packages(), {"not-a-form"})


def test_package_artifact_drift_fails_closed(tmp_path: Path) -> None:
    source = next(package for package in _packages() if package.form_key == "RRBudget10")
    package_dir = tmp_path / "rr_budget10" / "1" / "0" / "draft_package"
    package_dir.mkdir(parents=True)
    manifest = copy.deepcopy(source.manifest)
    for artifact_name in manifest["artifacts"]:
        (package_dir / artifact_name).write_bytes(
            source.package_dir.joinpath(artifact_name).read_bytes()
        )
    (package_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (package_dir / "candidate.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(AnalysisProjectionError, match="artifact hash drift"):
        discover_package_inputs(tmp_path, _ALL_FORMS)


def test_cli_emits_toon_and_unknown_flags_exit_two(tmp_path: Path, capsys) -> None:
    assert main(["export", "--form", "RRBudget10", "--out", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert output.startswith("projection:\n")
    assert "outputs[7]{name,path,rows,sha256}:" in output
    assert json.loads((tmp_path / "projection.json").read_text())["contract"] == (
        "simpler-form-analysis-projection/v1"
    )

    with pytest.raises(SystemExit) as exc:
        main(["export", "--unknown"])
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().out
