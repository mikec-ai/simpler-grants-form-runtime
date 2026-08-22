#!/usr/bin/env python3
"""Emit resolved runtime and native parity oracles as build artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Never

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from src.form_schema.forms.key_contacts import (
    FORM_JSON_SCHEMA as KEY_CONTACTS_SCHEMA,  # ruff: ignore[module-import-not-at-top-of-file]
)
from src.form_schema.forms.key_contacts import (
    FORM_UI_SCHEMA as KEY_CONTACTS_UI,  # ruff: ignore[module-import-not-at-top-of-file]
)
from src.form_schema.forms.key_contacts import (
    FORM_XML_TRANSFORM_RULES as KEY_CONTACTS_XML,  # ruff: ignore[module-import-not-at-top-of-file]
)
from src.form_schema.forms.sf424 import (
    FORM_JSON_SCHEMA as SF424_SCHEMA,  # ruff: ignore[module-import-not-at-top-of-file]
)
from src.form_schema.forms.sf424 import (
    FORM_RULE_SCHEMA as SF424_RULES,  # ruff: ignore[module-import-not-at-top-of-file]
)
from src.form_schema.forms.sf424 import (
    FORM_UI_SCHEMA as SF424_UI,  # ruff: ignore[module-import-not-at-top-of-file]
)
from src.form_schema.forms.sf424 import (
    FORM_XML_TRANSFORM_RULES as SF424_XML,  # ruff: ignore[module-import-not-at-top-of-file]
)
from src.form_schema.portable_form_bundle import (  # ruff: ignore[module-import-not-at-top-of-file]
    PortableFormBundleError,
    load_portable_form_bundle,
)

VERSION = "0.1.0"
DEFAULT_OUTPUT = ROOT / "build" / "portable-form-artifacts" / "oracles"


def _write_json(path: Path, value: Any) -> str:
    content = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(bundle_root: Path, output_dir: Path) -> dict[str, int]:
    bundle = load_portable_form_bundle(bundle_root)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    artifacts: list[dict[str, Any]] = []
    for form_key in sorted(bundle.forms_by_key):
        declaration = bundle.forms_by_key[form_key].definition
        form = bundle.to_form(form_key)
        relative = Path("resolved") / f"{form_key}.json"
        digest = _write_json(
            output_dir / relative,
            {
                "contract": "portable-resolved-form-oracle/v1",
                "form_key": form_key,
                "metadata": declaration["metadata"],
                "review_boundary": declaration["review_boundary"],
                "question_bindings": declaration["question_bindings"],
                "source_evidence": declaration["source_evidence"],
                "runtime": {
                    "json_schema": form.form_json_schema,
                    "ui_schema": form.form_ui_schema,
                    "rules": form.form_rule_schema,
                    "grants_gov_xml": form.json_to_xml_schema,
                },
            },
        )
        artifacts.append(
            {
                "kind": "resolved_runtime_oracle",
                "form_key": form_key,
                "path": relative.as_posix(),
                "sha256": digest,
            }
        )

    native = {
        "KeyContacts": {
            "json_schema": KEY_CONTACTS_SCHEMA,
            "ui_schema": KEY_CONTACTS_UI,
            "rules": None,
            "grants_gov_xml": KEY_CONTACTS_XML,
        },
        "SF424": {
            "json_schema": SF424_SCHEMA,
            "ui_schema": SF424_UI,
            "rules": SF424_RULES,
            "grants_gov_xml": SF424_XML,
        },
    }
    parity: list[dict[str, Any]] = []
    for form_key, native_runtime in native.items():
        portable_runtime = json.loads(
            (output_dir / "resolved" / f"{form_key}.json").read_text(encoding="utf-8")
        )["runtime"]
        for artifact_name, value in native_runtime.items():
            relative = Path("native") / form_key / f"{artifact_name}.json"
            digest = _write_json(output_dir / relative, value)
            artifacts.append(
                {
                    "kind": "native_implementation_oracle",
                    "form_key": form_key,
                    "artifact": artifact_name,
                    "path": relative.as_posix(),
                    "sha256": digest,
                }
            )
            parity.append(
                {
                    "form_key": form_key,
                    "artifact": artifact_name,
                    "byte_semantic_exact": portable_runtime[artifact_name] == value,
                }
            )

    parity_path = output_dir / "parity.json"
    parity_digest = _write_json(
        parity_path,
        {
            "contract": "portable-native-parity-report/v1",
            "comparisons": parity,
            "claims_boundary": {
                "semantic_mappings": "agent_proposed",
                "published_coverage_eligible": False,
                "schema_normalization_is_not_applied_in_this_exact_comparison": True,
            },
        },
    )
    artifacts.append(
        {
            "kind": "parity_report",
            "path": parity_path.relative_to(output_dir).as_posix(),
            "sha256": parity_digest,
        }
    )

    manifest_path = output_dir / "manifest.json"
    _write_json(
        manifest_path,
        {
            "contract": "portable-form-build-oracles/v1",
            "bundle_manifest": {
                "path": "form-specs/manifest.json",
                "sha256": _sha256(bundle_root / "manifest.json"),
            },
            "summary": {
                "forms": len(bundle.forms_by_key),
                "resolved_runtime_oracles": len(bundle.forms_by_key),
                "native_implementation_oracles": sum(len(value) for value in native.values()),
                "accepted_semantic_mappings": 0,
                "published_coverage_eligible": False,
            },
            "artifacts": sorted(artifacts, key=lambda row: row["path"]),
        },
    )
    return {
        "forms": len(bundle.forms_by_key),
        "artifacts": len(artifacts) + 1,
    }


class StructuredParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        sys.stdout.write(
            "error:\n"
            "  code: usage\n"
            "help:\n"
            "  command: python scripts/export_portable_form_oracles.py --help\n"
        )
        sys.stderr.write(f"{message}\n")
        raise SystemExit(2)


def parser() -> argparse.ArgumentParser:
    value = StructuredParser(
        prog="export-portable-form-oracles",
        description="Emit resolved and native implementation oracles for CI publication.",
    )
    value.add_argument("--bundle", type=Path, default=ROOT / "form-specs")
    value.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    value.add_argument("--version", action="version", version=VERSION)
    return value


def cli(argv: list[str]) -> int:
    try:
        args = parser().parse_args(argv)
        counts = export(args.bundle, args.output_dir)
    except (OSError, ValueError, PortableFormBundleError) as exc:
        sys.stdout.write("error:\n  code: oracle_export_failed\n")
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write(
        "oracle_export:\n"
        "  status: generated\n"
        f"  forms: {counts['forms']}\n"
        f"  artifacts: {counts['artifacts']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
