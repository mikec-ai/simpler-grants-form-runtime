"""Offline verification of exact source records in a portable form catalog."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_MAP_CONTRACT = "portable-source-repositories/v1"


class SourceProvenanceError(ValueError):
    """A fail-closed source declaration or verification error."""


@dataclass(frozen=True)
class SourceVerificationResult:
    """Minimal aggregate returned after every declared source is verified."""

    sources: int
    repositories: int


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceProvenanceError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SourceProvenanceError(f"{label} must be a JSON object: {path}")
    return value


def _repository_bindings(path: Path) -> dict[str, Path]:
    document = _read_object(path, "repository map")
    expected_keys = {"contract", "repositories"}
    if set(document) != expected_keys:
        raise SourceProvenanceError("repository map must contain only contract and repositories")
    if document["contract"] != REPOSITORY_MAP_CONTRACT:
        raise SourceProvenanceError(f"repository map contract must equal {REPOSITORY_MAP_CONTRACT}")
    records = document["repositories"]
    if not isinstance(records, list) or not records:
        raise SourceProvenanceError("repository map repositories must be nonempty")

    bindings: dict[str, Path] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != {"repository", "path"}:
            raise SourceProvenanceError(
                f"repositories[{index}] must contain only repository and path"
            )
        repository = record["repository"]
        local_path = record["path"]
        if not isinstance(repository, str) or not repository:
            raise SourceProvenanceError(
                f"repositories[{index}].repository must be a nonempty string"
            )
        if not isinstance(local_path, str) or not local_path:
            raise SourceProvenanceError(f"repositories[{index}].path must be a nonempty string")
        if repository in bindings:
            raise SourceProvenanceError(
                f"repository map contains duplicate repository: {repository}"
            )
        candidate = Path(local_path)
        if not candidate.is_absolute():
            candidate = path.parent / candidate
        bindings[repository] = candidate.resolve()
    return bindings


def _source_path(source_id: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise SourceProvenanceError(f"source {source_id} path must be nonempty")
    if "\\" in value or "\x00" in value:
        raise SourceProvenanceError(f"source {source_id} path must be a portable POSIX Git path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SourceProvenanceError(
            f"source {source_id} path must be a normalized relative Git path"
        )
    if str(path) != value:
        raise SourceProvenanceError(
            f"source {source_id} path must be a normalized relative Git path"
        )
    return value


def _git(repo: Path, arguments: list[str], label: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise SourceProvenanceError(f"cannot execute local Git verification: {exc}") from exc
    if result.returncode != 0:
        raise SourceProvenanceError(label)
    return result.stdout


def _verify_repository(repository: str, repo: Path) -> None:
    if not repo.is_dir():
        raise SourceProvenanceError(
            f"local repository path does not exist for {repository}: {repo}"
        )
    _git(
        repo,
        ["rev-parse", "--git-dir"],
        f"local repository binding is not a Git repository: {repository}",
    )


def _verify_source(source_id: str, source: object, bindings: dict[str, Path]) -> str:
    if not isinstance(source, dict):
        raise SourceProvenanceError(f"source {source_id} must be an object")
    required = {"kind", "repository", "revision", "path", "sha256", "source_version"}
    missing = sorted(required - set(source))
    if missing:
        raise SourceProvenanceError(
            f"source {source_id} is missing provenance fields: {', '.join(missing)}"
        )

    repository = source["repository"]
    revision = source["revision"]
    expected_sha256 = source["sha256"]
    source_version = source["source_version"]
    if not isinstance(repository, str) or not repository:
        raise SourceProvenanceError(f"source {source_id} repository must be nonempty")
    if not isinstance(revision, str) or GIT_REVISION.fullmatch(revision) is None:
        raise SourceProvenanceError(
            f"source {source_id} revision must be a full lowercase Git commit id"
        )
    if not isinstance(expected_sha256, str) or SHA256.fullmatch(expected_sha256) is None:
        raise SourceProvenanceError(
            f"source {source_id} sha256 must be 64 lowercase hexadecimal characters"
        )
    if not isinstance(source_version, str) or not source_version:
        raise SourceProvenanceError(f"source {source_id} source_version must be nonempty")
    git_path = _source_path(source_id, source["path"])
    repo = bindings.get(repository)
    if repo is None:
        raise SourceProvenanceError(
            f"source {source_id} repository has no local binding: {repository}"
        )

    _git(
        repo,
        ["cat-file", "-e", f"{revision}^{{commit}}"],
        f"source {source_id} pinned revision is unavailable in local repository",
    )
    content = _git(
        repo,
        ["cat-file", "blob", f"{revision}:{git_path}"],
        f"source {source_id} path is unavailable at pinned revision: {git_path}",
    )
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if actual_sha256 != expected_sha256:
        raise SourceProvenanceError(
            f"source {source_id} sha256 mismatch; expected {expected_sha256}, got {actual_sha256}"
        )
    return repository


def verify_catalog_sources(
    catalog_path: Path, repository_map_path: Path
) -> SourceVerificationResult:
    """Verify source blobs at their exact pinned revisions using local Git only."""

    catalog = _read_object(catalog_path, "portable catalog")
    sources = catalog.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise SourceProvenanceError("portable catalog sources must be a nonempty object")
    bindings = _repository_bindings(repository_map_path)
    for repository, repo in bindings.items():
        _verify_repository(repository, repo)

    used_repositories = {
        _verify_source(source_id, source, bindings)
        for source_id, source in sources.items()
        if isinstance(source_id, str) and source_id
    }
    if len(used_repositories) == 0 or len(sources) != sum(
        isinstance(source_id, str) and bool(source_id) for source_id in sources
    ):
        raise SourceProvenanceError("portable catalog source ids must be nonempty strings")
    return SourceVerificationResult(sources=len(sources), repositories=len(used_repositories))
