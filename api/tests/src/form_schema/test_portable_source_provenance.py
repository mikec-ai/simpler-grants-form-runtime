import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.form_schema.portable_source_provenance import (
    SourceProvenanceError,
    verify_catalog_sources,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
VERIFIER = REPOSITORY_ROOT / "scripts/verify_portable_source_provenance.py"
REPOSITORY = "https://example.test/source-records.git"


def _git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, str, bytes]:
    repo = tmp_path / "source-repository"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.name", "Portable Source Test")
    _git(repo, "config", "user.email", "portable-source@example.test")
    source = repo / "sources/reference.xsd"
    source.parent.mkdir()
    content = b'<schema version="1"/>\n'
    source.write_bytes(content)
    _git(repo, "add", "sources/reference.xsd")
    _git(repo, "commit", "--quiet", "-m", "Add exact source")
    revision = _git(repo, "rev-parse", "HEAD")

    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "sources": {
                    "reference-xsd": {
                        "kind": "authoritative_source",
                        "repository": REPOSITORY,
                        "revision": revision,
                        "path": "sources/reference.xsd",
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "source_version": "Reference 1.0",
                    }
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    repositories = tmp_path / "repositories.json"
    repositories.write_text(
        json.dumps(
            {
                "contract": "portable-source-repositories/v1",
                "repositories": [{"repository": REPOSITORY, "path": str(repo)}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return catalog, repositories, repo, revision, content


def _run(catalog: Path, repositories: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--catalog",
            str(catalog),
            "--repositories",
            str(repositories),
            *extra,
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )


def test_verifies_exact_historical_blob_without_using_worktree(tmp_path: Path) -> None:
    catalog, repositories, repo, _, _ = _fixture(tmp_path)
    (repo / "sources/reference.xsd").write_text("changed but uncommitted\n")

    result = _run(catalog, repositories)

    assert result.returncode == 0
    assert "status: verified" in result.stdout
    assert "sources: 1" in result.stdout
    assert "repositories: 1" in result.stdout
    assert result.stderr == ""


def test_verifies_pinned_revision_after_a_later_commit(tmp_path: Path) -> None:
    catalog, repositories, repo, _, _ = _fixture(tmp_path)
    (repo / "sources/reference.xsd").write_text('<schema version="2"/>\n')
    _git(repo, "add", "sources/reference.xsd")
    _git(repo, "commit", "--quiet", "-m", "Change current source")

    result = verify_catalog_sources(catalog, repositories)

    assert result.sources == 1
    assert result.repositories == 1


def test_fails_closed_on_source_digest_mismatch(tmp_path: Path) -> None:
    catalog, repositories, _, _, _ = _fixture(tmp_path)
    document = json.loads(catalog.read_text(encoding="utf-8"))
    document["sources"]["reference-xsd"]["sha256"] = "0" * 64
    catalog.write_text(json.dumps(document), encoding="utf-8")

    result = _run(catalog, repositories)

    assert result.returncode == 1
    assert "code: source_provenance_failed" in result.stdout
    assert "sha256 mismatch" in result.stderr
    assert "<schema" not in result.stdout + result.stderr


def test_fails_closed_when_repository_has_no_local_binding(tmp_path: Path) -> None:
    catalog, repositories, _, _, _ = _fixture(tmp_path)
    mapping = json.loads(repositories.read_text(encoding="utf-8"))
    mapping["repositories"][0]["repository"] = "https://example.test/other.git"
    repositories.write_text(json.dumps(mapping), encoding="utf-8")

    result = _run(catalog, repositories)

    assert result.returncode == 1
    assert "has no local binding" in result.stderr


def test_fails_closed_when_pinned_revision_is_missing(tmp_path: Path) -> None:
    catalog, repositories, _, _, _ = _fixture(tmp_path)
    document = json.loads(catalog.read_text(encoding="utf-8"))
    document["sources"]["reference-xsd"]["revision"] = "f" * 40
    catalog.write_text(json.dumps(document), encoding="utf-8")

    result = _run(catalog, repositories)

    assert result.returncode == 1
    assert "pinned revision is unavailable" in result.stderr


def test_fails_closed_when_path_is_missing_at_pinned_revision(tmp_path: Path) -> None:
    catalog, repositories, _, _, _ = _fixture(tmp_path)
    document = json.loads(catalog.read_text(encoding="utf-8"))
    document["sources"]["reference-xsd"]["path"] = "sources/missing.xsd"
    catalog.write_text(json.dumps(document), encoding="utf-8")

    result = _run(catalog, repositories)

    assert result.returncode == 1
    assert "path is unavailable at pinned revision" in result.stderr


def test_rejects_path_traversal_before_invoking_git(tmp_path: Path) -> None:
    catalog, repositories, _, _, _ = _fixture(tmp_path)
    document = json.loads(catalog.read_text(encoding="utf-8"))
    document["sources"]["reference-xsd"]["path"] = "../reference.xsd"
    catalog.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(SourceProvenanceError, match="normalized relative Git path"):
        verify_catalog_sources(catalog, repositories)


def test_requires_preserved_source_version(tmp_path: Path) -> None:
    catalog, repositories, _, _, _ = _fixture(tmp_path)
    document = json.loads(catalog.read_text(encoding="utf-8"))
    del document["sources"]["reference-xsd"]["source_version"]
    catalog.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(SourceProvenanceError, match="source_version"):
        verify_catalog_sources(catalog, repositories)


def test_unknown_flag_is_structured_usage_error(tmp_path: Path) -> None:
    catalog, repositories, _, _, _ = _fixture(tmp_path)

    result = _run(catalog, repositories, "--fetch")

    assert result.returncode == 2
    assert "error:\n  code: usage" in result.stdout
    assert "unrecognized arguments: --fetch" in result.stderr


def test_help_is_structured_and_version_is_bare() -> None:
    help_result = subprocess.run(
        [sys.executable, str(VERIFIER), "--help"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    version_result = subprocess.run(
        [sys.executable, str(VERIFIER), "-v"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )

    assert help_result.returncode == 0
    assert "flags[4]{name,required,description}:" in help_result.stdout
    assert version_result.returncode == 0
    assert version_result.stdout == "0.1.0\n"
