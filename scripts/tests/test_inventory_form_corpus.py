from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "inventory_form_corpus.py"
RULES = Path(__file__).parents[1] / "form_corpus_disposition_rules.json"
SPEC = importlib.util.spec_from_file_location("inventory_form_corpus", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def commit(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def test_classification_separates_sources_oracles_mappings_and_tests() -> None:
    _, rules = MODULE.load_rules(RULES)
    cases = {
        "api/x/draft_package/work/a.xsd": ("source", "publish_build_artifact"),
        "api/x/draft_package/source-ledger.json": ("source_evidence", "migrate"),
        "api/x/draft_package/xml-transform.json": ("mapping", "migrate"),
        "api/x/resolved_package/json-schema.json": ("oracle", "publish_build_artifact"),
        "api/tests/x/test_form.py": ("test", "preserve"),
    }
    for path, expected in cases.items():
        actual = MODULE.classify(path, rules)
        assert (actual["category"], actual["disposition"]) == expected


def test_inventory_is_deterministic_and_records_intermediate_versions(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    form = repo / "api/src/form_schema/forms/example/1/0"
    form.mkdir(parents=True)
    source = form / "draft_package/work/example.xsd"
    source.parent.mkdir(parents=True)
    source.write_text("v1")
    test_file = repo / "api/tests/test_example.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_one(): pass\n")
    base = commit(repo, "base")
    git(repo, "branch", "baseline", base)

    source.write_text("v2")
    first = commit(repo, "source update")
    source.write_text("v3")
    mapping = form / "draft_package/xml-transform.json"
    mapping.write_text("{}\n")
    head = commit(repo, "mapping")
    metadata = [
        {
            "number": 8,
            "title": "Example",
            "url": "https://example.test/8",
            "state": "open",
            "draft": True,
            "head_ref": "feature",
            "head_oid": head,
            "base_ref": "main",
            "base_oid": base,
            "commit_oids": [first, head],
        }
    ]

    one = MODULE.build_inventory(
        repo=repo,
        repository="example/repo",
        pull_requests=metadata,
        rules_path=RULES,
        remote="origin",
        reachable_from="baseline",
    )
    two = MODULE.build_inventory(
        repo=repo,
        repository="example/repo",
        pull_requests=metadata,
        rules_path=RULES,
        remote="origin",
        reachable_from="baseline",
    )

    assert MODULE.canonical_json(one) == MODULE.canonical_json(two)
    assert one["summary"]["form_count"] == 1
    source_versions = [
        item
        for item in one["artifact_versions"]
        if item["path"].endswith("example.xsd")
    ]
    assert {item["sha256"] for item in source_versions} == {
        __import__("hashlib").sha256(value).hexdigest() for value in (b"v2", b"v3")
    }
    assert all(item["destination"].endswith("example.xsd") for item in source_versions)
    assert any(item["category"] == "mapping" for item in one["artifact_versions"])
    assert one["preservation_ref_plan"]["all_unreachable_commits_planned"]
    assert not one["preservation_ref_plan"]["all_unreachable_commits_durably_preserved"]
    assert len(one["preservation_ref_plan"]["refs"]) == 1
    assert (
        one["preservation_ref_plan"]["refs"][0]["ref_kind_required"] == "annotated_tag"
    )
    assert one["preservation_ref_plan"]["refs"][0]["local_ancestry_verified"]
    assert one["pull_requests"][0]["requires_preservation_ref"]
    assert not one["preservation_ref_plan"]["verification_performed"]
    assert one["preservation_ref_plan"]["verified_at"] is None


def test_cli_writes_content_addressed_report(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    form = repo / "api/src/form_schema/forms/example/1/0"
    form.mkdir(parents=True)
    (form / "form_json.py").write_text("FORM = {}\n")
    base = commit(repo, "base")
    git(repo, "branch", "baseline", base)
    (form / "form_json.py").write_text("FORM = {'title': 'Example'}\n")
    head = commit(repo, "form")
    metadata = tmp_path / "prs.json"
    metadata.write_text(
        json.dumps(
            {
                "pull_requests": [
                    {
                        "number": 8,
                        "title": "Example",
                        "url": "https://example.test/8",
                        "state": "open",
                        "draft": True,
                        "head_ref": "feature",
                        "head_oid": head,
                        "base_ref": "main",
                        "base_oid": base,
                        "commit_oids": [head],
                    }
                ]
            }
        )
    )
    output = tmp_path / "output"
    subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--repo-dir",
            str(repo),
            "--metadata-file",
            str(metadata),
            "--rules",
            str(RULES),
            "--output-dir",
            str(output),
            "--reachable-from",
            "baseline",
        ],
        check=True,
    )
    payload = json.loads((output / "inventory.json").read_text())
    assert payload["content_sha256"]
    assert (output / "SUMMARY.md").exists()
    assert "inventory.json" in (output / "SHA256SUMS").read_text()


def test_remote_verification_requires_annotated_tag_and_peeled_target(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    remote = tmp_path / "private.git"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    subprocess.run(
        ["git", "init", "--bare", str(remote)], check=True, capture_output=True
    )
    git(repo, "remote", "add", "private", str(remote))
    form = repo / "api/src/form_schema/forms/example/1/0"
    form.mkdir(parents=True)
    (form / "form_json.py").write_text("FORM = {}\n")
    base = commit(repo, "base")
    git(repo, "branch", "baseline", base)
    (form / "form_json.py").write_text("FORM = {'title': 'Example'}\n")
    head = commit(repo, "form")
    tag = f"archive/form-corpus/tip-{head[:12]}"
    git(repo, "tag", "--annotate", tag, head, "--message", "Preserve test tip")
    git(repo, "push", "private", f"refs/tags/{tag}")
    metadata = [
        {
            "number": 8,
            "title": "Example",
            "url": "https://example.test/8",
            "state": "open",
            "draft": True,
            "head_ref": "feature",
            "head_oid": head,
            "base_ref": "main",
            "base_oid": base,
            "commit_oids": [head],
        }
    ]
    inventory = MODULE.build_inventory(
        repo=repo,
        repository="example/repo",
        pull_requests=metadata,
        rules_path=RULES,
        remote="private",
        reachable_from="baseline",
        verify_preservation_refs=True,
        verification_timestamp="2026-08-22T15:30:00Z",
        verification_run_id="test-run-1",
    )
    plan = inventory["preservation_ref_plan"]
    assert plan["all_unreachable_commits_durably_preserved"]
    assert plan["remote_verification_checked_at"]
    assert plan["verification_performed"]
    assert plan["verified_at"] == "2026-08-22T15:30:00Z"
    assert plan["verification_run_id"] == "test-run-1"
    assert plan["refs"][0]["remote_tag_object_oid"] != head
    assert plan["refs"][0]["remote_peeled_target_commit_oid"] == head


def test_verification_timestamp_requires_timezone() -> None:
    try:
        MODULE.normalize_verification_timestamp("2026-08-22T15:30:00")
    except MODULE.InventoryError as exc:
        assert "UTC offset" in str(exc)
    else:
        raise AssertionError("naive timestamp should be rejected")


def test_unknown_flag_fails_with_exit_two_and_actionable_help() -> None:
    result = subprocess.run(
        ["python3", str(SCRIPT), "--not-a-real-option"],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 2
    assert "unrecognized arguments: --not-a-real-option" in result.stderr
    assert "usage:" in result.stderr
