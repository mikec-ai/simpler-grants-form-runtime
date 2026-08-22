#!/usr/bin/env python3
"""Inventory a stacked PR corpus without checking large evidence into the repository.

The report is content-addressed. It records every file version visible at a scoped
commit boundary, every PR commit, and the complete form corpus at the selected tip.
Semantic equivalence is intentionally out of scope: identical content hashes prove
byte identity only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
DEFAULT_FORM_ROOT = "api/src/form_schema/forms"


class InventoryError(RuntimeError):
    """Raised when exact provenance cannot be established."""


def run(command: list[str], *, cwd: Path, text: bool = True) -> str | bytes:
    result = subprocess.run(command, cwd=cwd, capture_output=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise InventoryError(f"{' '.join(command)} failed: {stderr}")
    return result.stdout.decode() if text else result.stdout


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: re.Pattern[str]
    category: str
    disposition: str
    destination: str


def load_rules(path: Path) -> tuple[str, list[Rule]]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    rules = [
        Rule(
            id=item["id"],
            pattern=re.compile(item["pattern"], re.IGNORECASE),
            category=item["category"],
            disposition=item["disposition"],
            destination=item["destination"],
        )
        for item in payload["rules"]
    ]
    if not rules or rules[-1].id != "fallback":
        raise InventoryError("disposition rules must end with a fallback rule")
    return hashlib.sha256(raw).hexdigest(), rules


def classify(path: str, rules: Iterable[Rule]) -> dict[str, str]:
    for rule in rules:
        if rule.pattern.search(path):
            return {
                "rule": rule.id,
                "category": rule.category,
                "disposition": rule.disposition,
                "destination": rule.destination.format(path=path),
            }
    raise InventoryError(f"no disposition rule matched {path}")


def ensure_object(repo: Path, oid: str, remote: str) -> None:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{oid}^{{commit}}"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return
    run(["git", "fetch", "--quiet", remote, oid], cwd=repo)


def git_blob(repo: Path, revision: str, path: str) -> tuple[str, str, int] | None:
    try:
        blob_oid = str(
            run(["git", "rev-parse", f"{revision}:{path}"], cwd=repo)
        ).strip()
    except InventoryError:
        return None
    content = run(["git", "cat-file", "blob", blob_oid], cwd=repo, text=False)
    assert isinstance(content, bytes)
    return blob_oid, hashlib.sha256(content).hexdigest(), len(content)


def diff_entries(repo: Path, parent: str | None, commit: str) -> list[dict[str, str]]:
    command = ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", "-M"]
    if parent is None:
        command.append("--root")
    command.append(commit)
    output = str(run(command, cwd=repo))
    entries: list[dict[str, str]] = []
    for line in output.splitlines():
        columns = line.split("\t")
        status = columns[0]
        if status.startswith("R"):
            entries.append({"status": "renamed_from", "path": columns[1]})
            entries.append({"status": "renamed_to", "path": columns[2]})
        else:
            entries.append({"status": status[0], "path": columns[1]})
    return entries


def commit_record(repo: Path, oid: str) -> dict[str, Any]:
    raw = str(
        run(
            ["git", "show", "-s", "--format=%H%x00%T%x00%P%x00%aI%x00%s", oid],
            cwd=repo,
        )
    ).rstrip("\n")
    commit, tree, parents, authored_at, subject = raw.split("\x00", 4)
    return {
        "oid": commit,
        "tree_oid": tree,
        "parent_oids": parents.split() if parents else [],
        "authored_at": authored_at,
        "subject": subject,
    }


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise InventoryError(
            f"git merge-base --is-ancestor {ancestor} {descendant} failed: "
            f"{result.stderr.decode(errors='replace').strip()}"
        )
    return result.returncode == 0


def remote_tag_refs(repo: Path, remote: str) -> tuple[dict[str, str], dict[str, str]]:
    try:
        output = str(
            run(
                [
                    "git",
                    "ls-remote",
                    remote,
                    "refs/tags/archive/form-corpus/*",
                    "refs/tags/archive/form-corpus/*^{}",
                ],
                cwd=repo,
            )
        )
    except InventoryError:
        return {}, {}
    objects: dict[str, str] = {}
    peeled: dict[str, str] = {}
    for line in output.splitlines():
        oid, ref = line.split("\t", 1)
        if ref.endswith("^{}"):
            peeled[ref.removesuffix("^{}")] = oid
        else:
            objects[ref] = oid
    return objects, peeled


def normalize_verification_timestamp(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InventoryError(
            "verification timestamp must be ISO 8601, for example 2026-08-22T15:30:00Z"
        ) from exc
    if parsed.tzinfo is None:
        raise InventoryError("verification timestamp must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def fetch_pr_metadata(
    repository: str, start: int, end: int, repo: Path
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for number in range(start, end + 1):
        pr = json.loads(
            str(run(["gh", "api", f"repos/{repository}/pulls/{number}"], cwd=repo))
        )
        commits = json.loads(
            str(
                run(
                    [
                        "gh",
                        "api",
                        "--paginate",
                        f"repos/{repository}/pulls/{number}/commits",
                    ],
                    cwd=repo,
                )
            )
        )
        records.append(
            {
                "number": number,
                "title": pr["title"],
                "url": pr["html_url"],
                "state": pr["state"],
                "draft": pr["draft"],
                "head_ref": pr["head"]["ref"],
                "head_oid": pr["head"]["sha"],
                "base_ref": pr["base"]["ref"],
                "base_oid": pr["base"]["sha"],
                "commit_oids": [item["sha"] for item in commits],
            }
        )
    return records


def load_metadata(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    return payload["pull_requests"] if isinstance(payload, dict) else payload


def list_tree_files(repo: Path, revision: str, root: str) -> list[str]:
    output = str(
        run(["git", "ls-tree", "-r", "--name-only", revision, "--", root], cwd=repo)
    )
    return sorted(line for line in output.splitlines() if line)


def list_form_directories(repo: Path, revision: str, form_root: str) -> list[str]:
    output = str(
        run(
            ["git", "ls-tree", "-d", "--name-only", f"{revision}:{form_root}"], cwd=repo
        )
    )
    return sorted(line for line in output.splitlines() if line)


def build_inventory(
    *,
    repo: Path,
    repository: str,
    pull_requests: list[dict[str, Any]],
    rules_path: Path,
    corpus_tip: str | None = None,
    form_root: str = DEFAULT_FORM_ROOT,
    remote: str = "origin",
    reachable_from: str = "mirror-base",
    verify_preservation_refs: bool = False,
    verification_timestamp: str | None = None,
    verification_run_id: str | None = None,
) -> dict[str, Any]:
    rules_sha256, rules = load_rules(rules_path)
    ordered_prs = sorted(pull_requests, key=lambda item: item["number"])
    if not ordered_prs:
        raise InventoryError("at least one pull request is required")

    all_oids = {
        oid
        for pr in ordered_prs
        for oid in [pr["base_oid"], pr["head_oid"], *pr["commit_oids"]]
    }
    for oid in sorted(all_oids):
        ensure_object(repo, oid, remote)
    baseline_oid = str(run(["git", "rev-parse", reachable_from], cwd=repo)).strip()

    artifact_by_key: dict[tuple[str, str], dict[str, Any]] = {}

    def add_artifact(
        *,
        path: str,
        revision: str,
        occurrence: dict[str, Any],
        fallback_revision: str | None = None,
    ) -> str | None:
        blob = git_blob(repo, revision, path)
        if blob is None and fallback_revision is not None:
            blob = git_blob(repo, fallback_revision, path)
        if blob is None:
            return None
        blob_oid, sha256, size = blob
        key = (path, blob_oid)
        artifact = artifact_by_key.get(key)
        if artifact is None:
            artifact_id = f"sha256:{sha256}:{path}"
            artifact = {
                "id": artifact_id,
                "path": path,
                "git_blob_oid": blob_oid,
                "sha256": sha256,
                "size_bytes": size,
                **classify(path, rules),
                "occurrences": [],
            }
            artifact_by_key[key] = artifact
        if occurrence not in artifact["occurrences"]:
            artifact["occurrences"].append(occurrence)
        return artifact["id"]

    commits: dict[str, dict[str, Any]] = {}
    pr_records: list[dict[str, Any]] = []
    for pr in ordered_prs:
        commit_ids: list[str] = []
        pr_artifact_ids: set[str] = set()
        for oid in pr["commit_oids"]:
            record = commits.setdefault(oid, commit_record(repo, oid))
            record.setdefault("pull_requests", []).append(pr["number"])
            commit_ids.append(oid)
            parent = record["parent_oids"][0] if record["parent_oids"] else None
            for entry in diff_entries(repo, parent, oid):
                use_parent = entry["status"] in {"D", "renamed_from"}
                revision = parent if use_parent and parent is not None else oid
                artifact_id = add_artifact(
                    path=entry["path"],
                    revision=revision,
                    fallback_revision=pr["base_oid"] if use_parent else None,
                    occurrence={
                        "scope": "commit",
                        "pull_request": pr["number"],
                        "commit_oid": oid,
                        "status": entry["status"],
                    },
                )
                if artifact_id:
                    pr_artifact_ids.add(artifact_id)
        pr_records.append(
            {
                **pr,
                "commit_oids": commit_ids,
                "artifact_ids": sorted(pr_artifact_ids),
            }
        )

    for record in commits.values():
        record["pull_requests"] = sorted(set(record["pull_requests"]))
        record["reachable_from_baseline"] = is_ancestor(
            repo, record["oid"], baseline_oid
        )

    for pr in pr_records:
        unreachable = [
            oid
            for oid in pr["commit_oids"]
            if not commits[oid]["reachable_from_baseline"]
        ]
        pr["commits_not_reachable_from_baseline"] = unreachable
        pr["requires_preservation_ref"] = bool(unreachable)

    at_risk_oids = sorted(
        oid for oid, record in commits.items() if not record["reachable_from_baseline"]
    )
    candidate_tips = sorted(
        {
            pr["head_oid"]
            for pr in pr_records
            if any(oid in at_risk_oids for oid in pr["commit_oids"])
        }
    )
    maximal_tips = [
        tip
        for tip in candidate_tips
        if not any(
            tip != other and is_ancestor(repo, tip, other) for other in candidate_tips
        )
    ]
    remote_objects, remote_peeled = (
        remote_tag_refs(repo, remote) if verify_preservation_refs else ({}, {})
    )
    verified_at = normalize_verification_timestamp(verification_timestamp)
    if verify_preservation_refs and verified_at is None:
        verified_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    preservation_refs: list[dict[str, Any]] = []
    for tip_oid in maximal_tips:
        covered = [oid for oid in at_risk_oids if is_ancestor(repo, oid, tip_oid)]
        ref = f"refs/tags/archive/form-corpus/tip-{tip_oid[:12]}"
        tag_name = ref.removeprefix("refs/tags/")
        annotation = f"Preserve form corpus PR evidence at maximal DAG tip {tip_oid}"
        object_oid = remote_objects.get(ref)
        peeled_oid = remote_peeled.get(ref)
        preservation_refs.append(
            {
                "ref": ref,
                "ref_kind_required": "annotated_tag",
                "target_commit_oid": tip_oid,
                "annotation_message": annotation,
                "create_command": [
                    "git",
                    "tag",
                    "--annotate",
                    tag_name,
                    tip_oid,
                    "--message",
                    annotation,
                ],
                "push_command": ["git", "push", remote, ref],
                "verify_command": ["git", "ls-remote", remote, ref, f"{ref}^{{}}"],
                "related_pull_requests": sorted(
                    {
                        number
                        for oid in covered
                        for number in commits[oid]["pull_requests"]
                    }
                ),
                "covers_commit_oids": covered,
                "local_ancestry_verified": all(
                    is_ancestor(repo, oid, tip_oid) for oid in covered
                ),
                "remote_tag_object_oid": object_oid,
                "remote_peeled_target_commit_oid": peeled_oid,
                "durable_remote_preservation_verified": (
                    object_oid is not None
                    and object_oid != tip_oid
                    and peeled_oid == tip_oid
                ),
                "reason": "Maximal DAG tip covers commits not reachable from baseline",
            }
        )
        for oid in covered:
            commits[oid].setdefault("proposed_preservation_refs", []).append(ref)
    covered_oids = {
        oid for item in preservation_refs for oid in item["covers_commit_oids"]
    }

    tip = corpus_tip or ordered_prs[-1]["head_oid"]
    ensure_object(repo, tip, remote)
    form_names = list_form_directories(repo, tip, form_root)
    forms: list[dict[str, Any]] = []
    for form_name in form_names:
        path = f"{form_root}/{form_name}"
        tree_oid = str(run(["git", "rev-parse", f"{tip}:{path}"], cwd=repo)).strip()
        artifact_ids = []
        for file_path in list_tree_files(repo, tip, path):
            artifact_id = add_artifact(
                path=file_path,
                revision=tip,
                occurrence={"scope": "corpus_tip", "revision": tip, "form": form_name},
            )
            if artifact_id:
                artifact_ids.append(artifact_id)
        forms.append(
            {
                "id": form_name,
                "path": path,
                "tree_oid": tree_oid,
                "file_count": len(artifact_ids),
                "artifact_ids": sorted(artifact_ids),
            }
        )

    artifacts = sorted(
        artifact_by_key.values(), key=lambda item: (item["path"], item["git_blob_oid"])
    )
    for artifact in artifacts:
        artifact["occurrences"].sort(
            key=lambda item: (
                item["scope"],
                item.get("pull_request", -1),
                item.get("commit_oid", ""),
                item.get("form", ""),
            )
        )
        destination_blob = git_blob(repo, baseline_oid, artifact["destination"])
        if destination_blob and destination_blob[1] == artifact["sha256"]:
            artifact["disposition_status"] = (
                "preserved_at_ref"
                if artifact["destination"] == artifact["path"]
                else "migrated_verified"
            )
            artifact["destination_evidence"] = {
                "commit_oid": baseline_oid,
                "path": artifact["destination"],
                "git_blob_oid": destination_blob[0],
                "sha256": destination_blob[1],
            }
        else:
            artifact["disposition_status"] = "planned"
            artifact["destination_evidence"] = None
    category_counts = Counter(item["category"] for item in artifacts)
    disposition_counts = Counter(item["disposition"] for item in artifacts)
    fallback_count = sum(item["rule"] == "fallback" for item in artifacts)
    pr_artifact_version_count = sum(
        any(occurrence["scope"] == "commit" for occurrence in item["occurrences"])
        for item in artifacts
    )
    corpus_artifact_version_count = sum(
        any(occurrence["scope"] == "corpus_tip" for occurrence in item["occurrences"])
        for item in artifacts
    )

    inventory: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "repository": repository,
        "scope": {
            "pull_request_numbers": [item["number"] for item in ordered_prs],
            "corpus_tip_oid": tip,
            "form_root": form_root,
            "disposition_rules_sha256": rules_sha256,
            "reachability_baseline_ref": reachable_from,
            "reachability_baseline_oid": baseline_oid,
        },
        "summary": {
            "pull_request_count": len(pr_records),
            "commit_count": len(commits),
            "form_count": len(forms),
            "artifact_version_count": len(artifacts),
            "pr_artifact_version_count": pr_artifact_version_count,
            "corpus_artifact_version_count": corpus_artifact_version_count,
            "fallback_rule_count": fallback_count,
            "categories": dict(sorted(category_counts.items())),
            "dispositions": dict(sorted(disposition_counts.items())),
        },
        "pull_requests": pr_records,
        "commits": sorted(commits.values(), key=lambda item: item["oid"]),
        "forms": forms,
        "corpus_snapshot": {
            "tip_oid": tip,
            "tip_source": (
                "explicit --corpus-tip"
                if corpus_tip
                else f"head of highest scoped PR #{ordered_prs[-1]['number']}"
            ),
            "form_root": form_root,
            "form_count": len(forms),
            "forms": forms,
            "interpretation": (
                "This is one pinned 28-form tree snapshot. It is separate from the "
                "PR evidence history and does not imply a one-form-per-PR relationship."
            ),
        },
        "pr_evidence": {
            "pull_request_numbers": [item["number"] for item in ordered_prs],
            "commit_count": len(commits),
            "artifact_version_count": pr_artifact_version_count,
            "artifact_scope": "file versions changed at scoped PR commit boundaries",
            "complete_per_pr_head_trees_included": False,
            "interpretation": (
                "These PRs contain architecture, runtime, analysis, and form work. "
                "They are not treated as a one-to-one list of forms, and the PR ledger "
                "does not claim to inventory every unchanged file at every PR head."
            ),
        },
        "artifact_versions": artifacts,
        "preservation_ref_plan": {
            "remote": remote,
            "ref_creation_performed": False,
            "verification_requested": verify_preservation_refs,
            "verification_performed": verify_preservation_refs,
            "verified_at": verified_at if verify_preservation_refs else None,
            "verification_run_id": (
                verification_run_id if verify_preservation_refs else None
            ),
            "remote_verification_checked_at": (
                verified_at if verify_preservation_refs else None
            ),
            "refs": preservation_refs,
            "commit_oids_not_reachable_from_baseline": at_risk_oids,
            "all_unreachable_commits_planned": set(at_risk_oids).issubset(covered_oids),
            "all_unreachable_commits_durably_preserved": bool(preservation_refs)
            and all(
                item["durable_remote_preservation_verified"]
                for item in preservation_refs
            ),
            "status": (
                "verified_remote"
                if preservation_refs
                and all(
                    item["durable_remote_preservation_verified"]
                    for item in preservation_refs
                )
                else "proposed_unapplied_or_unverified"
            ),
            "instruction": (
                "After human review, create these refs only on the named private remote; "
                "do not create them on the public upstream remote."
            ),
        },
        "preservation_boundary": (
            "The CI artifact is a reproducible export with finite retention. Durable Git "
            "preservation exists only after the proposed private annotated tags are created "
            "and a verification run records their tag-object and peeled target OIDs."
        ),
        "interpretation_boundary": (
            "Content hashes establish byte identity only; this inventory makes no semantic "
            "equivalence or reviewed-mapping claim."
        ),
    }
    inventory["content_sha256"] = hashlib.sha256(canonical_json(inventory)).hexdigest()
    return inventory


def summary_markdown(inventory: dict[str, Any]) -> str:
    summary = inventory["summary"]
    unreachable_count = len(
        inventory["preservation_ref_plan"]["commit_oids_not_reachable_from_baseline"]
    )
    preservation_ref_count = len(inventory["preservation_ref_plan"]["refs"])
    corpus_artifact_version_count = summary["corpus_artifact_version_count"]
    lines = [
        "# Form corpus preservation inventory",
        "",
        f"Inventory content hash: `{inventory['content_sha256']}`",
        "",
        "## Scope",
        "",
        f"- Pull requests: {summary['pull_request_count']}",
        f"- Unique commits: {summary['commit_count']}",
        f"- Forms at corpus tip: {summary['form_count']}",
        f"- Content-addressed artifact versions: {summary['artifact_version_count']}",
        f"- Artifact versions observed in PR commits: {summary['pr_artifact_version_count']}",
        f"- Artifact versions present at the pinned corpus tip: {corpus_artifact_version_count}",
        f"- Fallback dispositions requiring review: {summary['fallback_rule_count']}",
        f"- Commits not reachable from baseline: {unreachable_count}",
        f"- Proposed private preservation refs: {preservation_ref_count}",
        "",
        "## Forms",
        "",
        (
            "The following forms are the tree at the pinned corpus tip; the scoped PRs are "
            "not interpreted as one PR per form."
        ),
        "",
    ]
    lines.extend(
        f"- `{form['id']}`: {form['file_count']} files, tree `{form['tree_oid']}`"
        for form in inventory["forms"]
    )
    lines.extend(["", "## Dispositions", ""])
    lines.extend(
        f"- `{key}`: {value}" for key, value in summary["dispositions"].items()
    )
    lines.extend(
        [
            "",
            "The JSON report is authoritative for paths, hashes, occurrences, and destinations.",
            "Hash equality is byte equality only and does not establish semantic equivalence.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="mikec-ai/simpler-grants-form-runtime")
    parser.add_argument("--repo-dir", type=Path, default=Path.cwd())
    parser.add_argument("--pr-start", type=int, default=8)
    parser.add_argument("--pr-end", type=int, default=36)
    parser.add_argument("--metadata-file", type=Path)
    parser.add_argument(
        "--rules",
        type=Path,
        default=Path(__file__).with_name("form_corpus_disposition_rules.json"),
    )
    parser.add_argument("--corpus-tip")
    parser.add_argument("--form-root", default=DEFAULT_FORM_ROOT)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--reachable-from", default="mirror-base")
    parser.add_argument(
        "--verify-preservation-refs",
        action="store_true",
        help="Query the private remote and verify proposed annotated archive tags",
    )
    parser.add_argument(
        "--verified-at",
        help="ISO 8601 timestamp for the verification operation",
    )
    parser.add_argument(
        "--verification-run-id",
        help="CI or local run identifier associated with verification",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/form-corpus-inventory")
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        pull_requests = (
            load_metadata(args.metadata_file)
            if args.metadata_file
            else fetch_pr_metadata(
                args.repository, args.pr_start, args.pr_end, args.repo_dir
            )
        )
        inventory = build_inventory(
            repo=args.repo_dir.resolve(),
            repository=args.repository,
            pull_requests=pull_requests,
            rules_path=args.rules.resolve(),
            corpus_tip=args.corpus_tip,
            form_root=args.form_root,
            remote=args.remote,
            reachable_from=args.reachable_from,
            verify_preservation_refs=args.verify_preservation_refs,
            verification_timestamp=(
                args.verified_at or os.getenv("FORM_CORPUS_VERIFIED_AT")
            ),
            verification_run_id=(
                args.verification_run_id
                or os.getenv("GITHUB_RUN_ID")
                or ("local" if args.verify_preservation_refs else None)
            ),
        )
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        inventory_path = output_dir / "inventory.json"
        summary_path = output_dir / "SUMMARY.md"
        inventory_path.write_bytes(canonical_json(inventory))
        summary_path.write_text(summary_markdown(inventory))
        checksums = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (inventory_path, summary_path)
        }
        (output_dir / "SHA256SUMS").write_text(
            "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items()))
        )
    except (InventoryError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"form corpus inventory failed: {exc}", file=sys.stderr)
        return 1
    receipt = {"output_dir": str(output_dir), **inventory["summary"]}
    print("result:")
    for key, value in sorted(receipt.items()):
        if isinstance(value, dict):
            print(f"  {key}:")
            for nested_key, nested_value in sorted(value.items()):
                print(f"    {nested_key}: {json.dumps(nested_value)}")
        else:
            print(f"  {key}: {json.dumps(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
