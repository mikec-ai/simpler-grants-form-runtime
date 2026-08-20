import hashlib
import logging
import re
from pathlib import Path

import click
from grants_shared.util.local import error_if_not_local

from src.task.task_blueprint import task_blueprint

logger = logging.getLogger(__name__)

FORMS_DIR = Path(__file__).parents[2] / "form_schema" / "forms"
SRC_DIR = Path(__file__).parents[2]
VERSION_DEPENDENCIES_FILE = "version_dependencies.txt"


def _get_version_dependencies(version_dir: Path) -> list[Path]:
    manifest_path = version_dir / VERSION_DEPENDENCIES_FILE
    if not manifest_path.exists():
        return []

    src_dir = SRC_DIR.resolve()
    dependencies: list[Path] = []
    seen: set[Path] = set()

    for line_number, raw_line in enumerate(manifest_path.read_text().splitlines(), start=1):
        dependency_ref = raw_line.strip()
        if not dependency_ref or dependency_ref.startswith("#"):
            continue

        dependency_path = (src_dir / dependency_ref).resolve()
        if not dependency_path.is_relative_to(src_dir):
            raise ValueError(
                f"version dependency escapes src directory at "
                f"{manifest_path}:{line_number}: {dependency_ref!r}"
            )
        if not dependency_path.is_file():
            raise FileNotFoundError(
                f"version dependency not found at "
                f"{manifest_path}:{line_number}: {dependency_path}"
            )
        if dependency_path in seen:
            raise ValueError(
                f"duplicate version dependency at "
                f"{manifest_path}:{line_number}: {dependency_ref!r}"
            )

        seen.add(dependency_path)
        dependencies.append(dependency_path)

    return dependencies


def compute_version_hash(form_dir: Path, version_dir: Path) -> str:
    """Return the SHA-256 digest of a version and its declared source dependencies.

    Always hashes form_json.py, config.py, then dependencies in manifest order. Including
    each dependency's src-relative path prevents two same-content files from being swapped
    without invalidating the lock.
    """
    form_json_path = version_dir / "form_json.py"
    config_path = form_dir / "config.py"

    if not form_json_path.exists():
        raise FileNotFoundError(f"form_json.py not found: {form_json_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"config.py not found: {config_path}")

    h = hashlib.sha256()
    h.update(form_json_path.read_bytes())
    h.update(config_path.read_bytes())
    for dependency_path in _get_version_dependencies(version_dir):
        h.update(dependency_path.relative_to(SRC_DIR.resolve()).as_posix().encode())
        h.update(dependency_path.read_bytes())
    return h.hexdigest()


def get_version_dir(form_name: str, version: str) -> tuple[Path, Path]:
    """Return (form_dir, version_dir) for the given form name and version string."""
    if not re.fullmatch(r"\d+\.\d+", version):
        raise ValueError(f"version must be in MAJOR.MINOR format, got {version!r}")

    major, minor = version.split(".")
    form_dir = FORMS_DIR / form_name
    version_dir = form_dir / major / minor

    if not form_dir.is_dir():
        raise ValueError(f"no form directory found at {form_dir}")
    if not version_dir.is_dir():
        raise ValueError(f"no version directory found at {version_dir}")

    return form_dir, version_dir


@task_blueprint.cli.command(
    "lock-form-version",
    help="Hash a form version and its declared dependencies, then write a checksum file.",
)
@click.option("--form", required=True, help="Form directory name, e.g. sf424")
@click.option("--version", required=True, help="Version in MAJOR.MINOR format, e.g. 1.0")
def lock_form_version(form: str, version: str) -> None:
    error_if_not_local()
    try:
        form_dir, version_dir = get_version_dir(form, version)
    except ValueError as e:
        raise click.BadParameter(str(e)) from e
    checksum = compute_version_hash(form_dir, version_dir)
    checksum_path = version_dir / "checksum"
    checksum_path.write_text(checksum + "\n")
    click.echo(f"Wrote checksum for {form} v{version} → {checksum_path}")
    logger.info(
        "Locked form version", extra={"form": form, "version": version, "checksum": checksum}
    )
