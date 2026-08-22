import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from defusedxml import ElementTree

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
BUNDLE = REPOSITORY_ROOT / "form-specs"
ORACLE_EXPORTER = REPOSITORY_ROOT / "scripts/export_portable_form_oracles.py"
ANALYSIS_EXPORTER = REPOSITORY_ROOT / "scripts/export_portable_form_analysis.py"
WORKBOOK_BUILDER = REPOSITORY_ROOT / "scripts/build_portable_form_analysis_workbook.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
    )


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_oracle_export_is_deterministic_and_complete(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_result = _run(str(ORACLE_EXPORTER), "--bundle", str(BUNDLE), "--output-dir", str(first))
    second_result = _run(str(ORACLE_EXPORTER), "--bundle", str(BUNDLE), "--output-dir", str(second))

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    assert "forms: 8" in first_result.stdout
    assert _tree_digest(first) == _tree_digest(second)

    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"] == {
        "accepted_semantic_mappings": 0,
        "forms": 8,
        "native_implementation_oracles": 8,
        "published_coverage_eligible": False,
        "resolved_runtime_oracles": 8,
    }
    assert {path.stem for path in (first / "resolved").glob("*.json")} == {
        "KeyContacts",
        "RRBudget",
        "RRBudget10",
        "RRMPBudget",
        "RRMPSubawardBudget",
        "RRSubawardBudget30",
        "RRSubawardBudget10_30",
        "SF424",
    }


def test_analysis_workbook_is_built_only_from_generated_tables(tmp_path: Path) -> None:
    analysis = tmp_path / "analysis"
    workbook = analysis / "form-analysis.xlsx"
    export_result = _run(
        str(ANALYSIS_EXPORTER),
        "--bundle",
        str(BUNDLE),
        "--output-dir",
        str(analysis),
    )
    workbook_result = _run(
        str(WORKBOOK_BUILDER),
        "--analysis-dir",
        str(analysis),
        "--output",
        str(workbook),
    )

    assert export_result.returncode == 0, export_result.stderr
    assert workbook_result.returncode == 0, workbook_result.stderr
    assert "sheets: 6" in workbook_result.stdout
    assert workbook.is_file()

    with zipfile.ZipFile(workbook) as archive:
        xml = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    assert [node.attrib["name"] for node in xml.findall("x:sheets/x:sheet", namespace)] == [
        "Overview",
        "Forms",
        "Form Pairs",
        "Questions",
        "Role-qualified Questions",
        "Form Question Map",
    ]


def test_generated_outputs_are_not_tracked_runtime_inputs() -> None:
    assert not (BUNDLE / "oracles").exists()
    assert not list((REPOSITORY_ROOT / "documentation/form-analysis").glob("*.csv"))
    assert not list((REPOSITORY_ROOT / "documentation/form-analysis").glob("*.json"))
    assert not list((REPOSITORY_ROOT / "documentation/form-analysis").glob("*.xlsx"))

    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    assert all(
        not evidence["path"].startswith("oracles/")
        for form in manifest["forms"]
        for evidence in form["supplemental_evidence"]
    )


def test_native_oracle_selection_is_declarative_and_fails_on_drift(
    tmp_path: Path,
) -> None:
    source = ORACLE_EXPORTER.read_text(encoding="utf-8")
    assert "src.form_schema.forms.key_contacts" not in source
    assert "src.form_schema.forms.sf424" not in source

    bundle = tmp_path / "form-specs"
    shutil.copytree(BUNDLE, bundle)
    registry_path = bundle / "conformance/native-oracles.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["oracles"][0]["implementation_source"]["sha256"] = "0" * 64
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    result = _run(
        str(ORACLE_EXPORTER),
        "--bundle",
        str(bundle),
        "--output-dir",
        str(tmp_path / "oracles"),
    )

    assert result.returncode == 1
    assert "native oracle implementation source drift" in result.stderr


@pytest.mark.parametrize(
    "script",
    [ORACLE_EXPORTER, WORKBOOK_BUILDER],
)
def test_build_artifact_clis_reject_unknown_flags(script: Path) -> None:
    result = _run(str(script), "--wat")

    assert result.returncode == 2
    assert "code: usage" in result.stdout
    assert "unrecognized arguments: --wat" in result.stderr
