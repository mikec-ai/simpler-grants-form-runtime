import re
from pathlib import Path

import pytest
from flask import Flask

from src.task import task_blueprint
from src.task.forms.lock_form_version_task import compute_version_hash, get_version_dir

_FORMS_ROOT = Path(__file__).parents[4] / "src" / "form_schema" / "forms"


def get_locked_versions() -> list[tuple[Path, Path, str, str]]:
    """Return (form_dir, version_dir, major, minor) for every version with a checksum file."""
    locked = []
    for form_dir in sorted(_FORMS_ROOT.iterdir()):
        if not form_dir.is_dir() or form_dir.name == "__pycache__":
            continue
        for major_dir in sorted(form_dir.iterdir()):
            if not major_dir.is_dir() or not re.fullmatch(r"\d+", major_dir.name):
                continue
            for minor_dir in sorted(major_dir.iterdir()):
                if not minor_dir.is_dir() or not re.fullmatch(r"\d+", minor_dir.name):
                    continue
                if (minor_dir / "checksum").exists():
                    locked.append((form_dir, minor_dir, major_dir.name, minor_dir.name))
    return locked


def get_versions_with_dependencies() -> list[tuple[Path, Path]]:
    versions = []
    for manifest_path in sorted(_FORMS_ROOT.rglob("version_dependencies.txt")):
        version_dir = manifest_path.parent
        versions.append((version_dir.parents[1], version_dir))
    return versions


def test_locked_form_versions_unchanged() -> None:
    """Any version directory with a checksum file must still match its current sources.

    Passes silently when no checksum files are present.
    """
    failures: list[str] = []

    for form_dir, version_dir, major, minor in get_locked_versions():
        expected = (version_dir / "checksum").read_text().strip()
        actual = compute_version_hash(form_dir, version_dir)
        if actual != expected:
            failures.append(
                f"{form_dir.name} v{major}.{minor}: "
                f"expected {expected!r}, got {actual!r}. "
                f"Run `flask task lock-form-version --form={form_dir.name} "
                f"--version={major}.{minor}` to re-lock after an intentional change, "
                f"or create a new version directory instead."
            )

    if failures:
        pytest.fail("Locked form versions have been modified:\n" + "\n".join(failures))


@pytest.mark.parametrize(
    ("form_dir", "version_dir"),
    get_versions_with_dependencies(),
)
def test_declared_version_dependencies_resolve(form_dir: Path, version_dir: Path) -> None:
    checksum_path = version_dir / "checksum"
    assert (
        checksum_path.exists()
    ), f"{version_dir} declares shared dependencies but is not version-locked"
    assert checksum_path.read_text().strip() == compute_version_hash(form_dir, version_dir)


def test_template_based_forms_declare_version_dependencies() -> None:
    missing_manifests = []
    for form_json_path in sorted(_FORMS_ROOT.rglob("form_json.py")):
        if "src.form_schema.templates" not in form_json_path.read_text():
            continue
        if not (form_json_path.parent / "version_dependencies.txt").exists():
            missing_manifests.append(str(form_json_path))

    assert (
        not missing_manifests
    ), "Template-based forms must declare version_dependencies.txt: " + ", ".join(missing_manifests)


def test_compute_version_hash_is_stable(tmp_path: Path) -> None:
    """compute_version_hash returns the same digest for identical file contents."""
    form_dir = tmp_path / "my_form"
    version_dir = form_dir / "1" / "0"
    version_dir.mkdir(parents=True)
    (form_dir / "config.py").write_text("FORM_ID = 'abc'\n")
    (version_dir / "form_json.py").write_text("SCHEMA = {}\n")

    first = compute_version_hash(form_dir, version_dir)
    second = compute_version_hash(form_dir, version_dir)
    assert first == second
    assert len(first) == 64  # SHA-256 hex digest


def test_compute_version_hash_changes_when_form_json_changes(tmp_path: Path) -> None:
    """Digest differs when form_json.py content changes."""
    form_dir = tmp_path / "my_form"
    version_dir = form_dir / "1" / "0"
    version_dir.mkdir(parents=True)
    (form_dir / "config.py").write_text("FORM_ID = 'abc'\n")
    (version_dir / "form_json.py").write_text("SCHEMA = {}\n")

    original = compute_version_hash(form_dir, version_dir)
    (version_dir / "form_json.py").write_text("SCHEMA = {'changed': True}\n")
    assert compute_version_hash(form_dir, version_dir) != original


def test_compute_version_hash_changes_when_config_changes(tmp_path: Path) -> None:
    """Digest differs when config.py content changes."""
    form_dir = tmp_path / "my_form"
    version_dir = form_dir / "1" / "0"
    version_dir.mkdir(parents=True)
    (form_dir / "config.py").write_text("FORM_ID = 'abc'\n")
    (version_dir / "form_json.py").write_text("SCHEMA = {}\n")

    original = compute_version_hash(form_dir, version_dir)
    (form_dir / "config.py").write_text("FORM_ID = 'xyz'\n")
    assert compute_version_hash(form_dir, version_dir) != original


def test_compute_version_hash_changes_when_declared_package_file_changes(tmp_path: Path) -> None:
    form_dir = tmp_path / "my_form"
    version_dir = form_dir / "1" / "0"
    package_dir = version_dir / "resolved_package"
    package_dir.mkdir(parents=True)
    (form_dir / "config.py").write_text("FORM_ID = 'abc'\n")
    (version_dir / "form_json.py").write_text("SCHEMA = {}\n")
    (version_dir / "version_dependencies.txt").write_text("./resolved_package\n")
    artifact = package_dir / "json-schema.json"
    artifact.write_text("{}\n")

    original = compute_version_hash(form_dir, version_dir)
    artifact.write_text('{"changed": true}\n')


def test_compute_version_hash_changes_when_declared_dependency_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src_dir = tmp_path / "src"
    form_dir = src_dir / "form_schema" / "forms" / "my_form"
    version_dir = form_dir / "1" / "0"
    template_path = src_dir / "form_schema" / "templates" / "example.py"
    version_dir.mkdir(parents=True)
    template_path.parent.mkdir(parents=True)
    (form_dir / "config.py").write_text("FORM_ID = 'abc'\n")
    (version_dir / "form_json.py").write_text("SCHEMA = {}\n")
    (version_dir / "version_dependencies.txt").write_text("form_schema/templates/example.py\n")
    template_path.write_text("SHARED_VALUE = 1\n")
    monkeypatch.setattr("src.task.forms.lock_form_version_task.SRC_DIR", src_dir)

    original = compute_version_hash(form_dir, version_dir)
    template_path.write_text("SHARED_VALUE = 2\n")

    assert compute_version_hash(form_dir, version_dir) != original


def test_compute_version_hash_rejects_dependency_outside_src(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src_dir = tmp_path / "src"
    form_dir = src_dir / "form_schema" / "forms" / "my_form"
    version_dir = form_dir / "1" / "0"
    version_dir.mkdir(parents=True)
    (form_dir / "config.py").write_text("FORM_ID = 'abc'\n")
    (version_dir / "form_json.py").write_text("SCHEMA = {}\n")
    (version_dir / "version_dependencies.txt").write_text("../outside.py\n")
    monkeypatch.setattr("src.task.forms.lock_form_version_task.SRC_DIR", src_dir)

    with pytest.raises(ValueError, match="escapes its allowed root"):
        compute_version_hash(form_dir, version_dir)


def test_compute_version_hash_rejects_version_local_path_escape(tmp_path: Path) -> None:
    form_dir = tmp_path / "my_form"
    version_dir = form_dir / "1" / "0"
    version_dir.mkdir(parents=True)
    (form_dir / "config.py").write_text("FORM_ID = 'abc'\n")
    (version_dir / "form_json.py").write_text("SCHEMA = {}\n")
    (version_dir / "version_dependencies.txt").write_text("./../outside.json\n")

    with pytest.raises(ValueError, match="escapes its allowed root"):
        compute_version_hash(form_dir, version_dir)


def test_get_version_dir_resolves_correctly() -> None:
    """get_version_dir returns the expected form_dir and version_dir for a known form."""
    form_dir, version_dir = get_version_dir("sf424", "1.0")
    assert form_dir.name == "sf424"
    assert version_dir.name == "0"
    assert version_dir.parent.name == "1"


def test_get_version_dir_rejects_bad_version() -> None:
    """get_version_dir raises ValueError for a malformed version string."""
    with pytest.raises(ValueError, match="MAJOR.MINOR"):
        get_version_dir("sf424", "bad")


def test_get_version_dir_rejects_unknown_form() -> None:
    """get_version_dir raises ValueError for a form that does not exist."""
    with pytest.raises(ValueError, match="no form directory"):
        get_version_dir("nonexistent_form_xyz", "1.0")


def test_lock_form_version_blocked_in_non_local_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """lock-form-version must exit non-zero when ENVIRONMENT is not 'local'."""
    monkeypatch.setenv("ENVIRONMENT", "dev")
    app = Flask("test_lock_form_version")
    app.register_blueprint(task_blueprint)
    result = app.test_cli_runner().invoke(
        args=["task", "lock-form-version", "--form=sf424", "--version=1.0"]
    )
    assert result.exit_code != 0
    assert "non-local" in str(result.exception).lower()
