import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
EXPORTER = REPOSITORY_ROOT / "scripts/export_portable_form_analysis.py"
BUNDLE = REPOSITORY_ROOT / "form-specs"


def _run(output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(EXPORTER),
            "--bundle",
            str(BUNDLE),
            "--output-dir",
            str(output),
        ],
        capture_output=True,
        text=True,
    )


def _digest(root: Path) -> str:
    value = hashlib.sha256()
    for path in sorted(root.iterdir()):
        value.update(path.name.encode())
        value.update(path.read_bytes())
    return value.hexdigest()


def test_exporter_emits_complete_analysis_tables(tmp_path: Path) -> None:
    output = tmp_path / "analysis"
    result = _run(output)

    assert result.returncode == 0
    assert "forms: 6" in result.stdout
    assert "questions: 161" in result.stdout
    assert "associations: 527" in result.stdout
    assert {path.name for path in output.iterdir()} == {
        "analysis.json",
        "form-pairs.csv",
        "form-question-map.csv",
        "forms.csv",
        "questions.csv",
        "role-qualified-questions.csv",
    }

    pairs = list(csv.DictReader((output / "form-pairs.csv").open()))
    budget_pair = next(
        row for row in pairs if {row["form_a"], row["form_b"]} == {"RRBudget", "RRMPBudget"}
    )
    assert float(budget_pair["proposed_similarity"]) == pytest.approx(0.0)
    assert int(budget_pair["proposed_questions_in_common"]) == 0
    assert float(budget_pair["template_proposed_similarity"]) == pytest.approx(1.0)
    assert int(budget_pair["template_proposed_questions_in_common"]) == 101

    associations = list(csv.DictReader((output / "form-question-map.csv").open()))
    mechanisms = [
        row for row in associations if row["analysis_classification"] == "content_capture_mechanism"
    ]
    assert len(mechanisms) == 30
    assert all(row["included_in_proposed_overlap"] == "False" for row in mechanisms)
    assert {"xml_path", "type_source", "type", "xsd_source"} <= set(associations[0])


def test_exporter_is_deterministic_and_keeps_review_boundaries(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert _run(first).returncode == 0
    assert _run(second).returncode == 0
    assert _digest(first) == _digest(second)

    analysis = json.loads((first / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["summary"]["accepted_unique_questions"] == 0
    assert analysis["summary"]["published_associations"] == 0


def test_exporter_unknown_flag_fails_with_structured_stdout() -> None:
    result = subprocess.run(
        [sys.executable, str(EXPORTER), "--wat"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "code: usage" in result.stdout
    assert "unrecognized arguments: --wat" in result.stderr
