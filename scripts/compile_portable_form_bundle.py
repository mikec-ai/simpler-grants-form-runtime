#!/usr/bin/env python3
"""Compile portable form declarations into the runtime bundle manifest.

This compiler deliberately knows nothing about grants form identities, question
semantics, roles, calculations, or source-system paths. Those decisions belong
in the versioned JSON declarations that it validates and assembles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Never

import jsonschema

VERSION = "0.2.0"
DEFAULT_BUNDLE = Path(__file__).resolve().parents[1] / "form-specs"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CompileError(ValueError):
    """A fail-closed declaration or compilation error."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        _emit_error("usage", message, 2)


def _emit_error(code: str, message: str, status: int) -> Never:
    sys.stdout.write(
        "error:\n"
        f"  code: {code}\n"
        "  command: python scripts/compile_portable_form_bundle.py --help\n"
    )
    sys.stderr.write(f"{message}\n")
    raise SystemExit(status)


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CompileError(f"cannot read hashed artifact {path}: {exc}") from exc


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompileError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CompileError(f"{label} must be a JSON object: {path}")
    return value


def _resolve_inside(root: Path, relative: str, label: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise CompileError(f"{label} path must be nonempty and relative: {relative!r}")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise CompileError(f"{label} path escapes bundle root: {relative}") from exc
    return path


def compile_bundle(bundle_root: Path) -> tuple[dict[str, Any], list[str]]:
    root = bundle_root.resolve()
    catalog = _read_object(root / "catalog.json", "catalog")
    exact_keys = {
        "contract",
        "runtime_contract",
        "contract_schema",
        "bundle",
        "sources",
        "schemas",
        "validation_fragments",
        "compatibility",
        "form_declarations",
    }
    if set(catalog) != exact_keys:
        missing = sorted(exact_keys - set(catalog))
        unknown = sorted(set(catalog) - exact_keys)
        raise CompileError(
            f"catalog keys mismatch; missing={missing}, unknown={unknown}"
        )
    if catalog["contract"] != "portable-grants-form-catalog/v2":
        raise CompileError(
            "catalog.contract must equal portable-grants-form-catalog/v2"
        )
    if catalog["runtime_contract"] != "portable-grants-form-bundle/v2":
        raise CompileError(
            "catalog.runtime_contract must equal portable-grants-form-bundle/v2"
        )
    descriptor = catalog["contract_schema"]
    if not isinstance(descriptor, dict) or set(descriptor) != {"path", "sha256"}:
        raise CompileError("catalog.contract_schema must contain only path and sha256")
    schema_path = _resolve_inside(root, descriptor["path"], "contract schema")
    if _sha256(schema_path) != descriptor["sha256"]:
        raise CompileError(f"contract schema hash mismatch: {descriptor['path']}")
    contract_schema = _read_object(schema_path, "contract schema")
    try:
        jsonschema.Draft202012Validator.check_schema(contract_schema)
        contract_validator = jsonschema.Draft202012Validator(
            contract_schema,
            format_checker=jsonschema.FormatChecker(),
        )
        contract_validator.validate(catalog)
    except jsonschema.SchemaError as exc:
        raise CompileError(f"contract schema is invalid: {exc.message}") from exc
    except jsonschema.ValidationError as exc:
        raise CompileError(
            f"catalog violates the portable contract: {exc.message}"
        ) from exc
    descriptors = catalog["form_declarations"]
    if not isinstance(descriptors, list) or not descriptors:
        raise CompileError("catalog form_declarations must be a nonempty array")

    forms: list[dict[str, Any]] = []
    form_keys: list[str] = []
    seen_paths: set[str] = set()
    for index, descriptor in enumerate(descriptors):
        if not isinstance(descriptor, dict) or set(descriptor) != {"path", "sha256"}:
            raise CompileError(
                f"form_declarations[{index}] must contain only path and sha256"
            )
        relative = descriptor["path"]
        expected = descriptor["sha256"]
        if not isinstance(relative, str) or relative in seen_paths:
            raise CompileError(
                f"duplicate or invalid form declaration path: {relative!r}"
            )
        if not isinstance(expected, str) or SHA256.fullmatch(expected) is None:
            raise CompileError(f"invalid form declaration sha256: {relative}")
        path = _resolve_inside(root, relative, "form declaration")
        actual = _sha256(path)
        if actual != expected:
            raise CompileError(
                f"form declaration hash mismatch: {relative}; expected {expected}, got {actual}"
            )
        form = _read_object(path, "form declaration")
        try:
            contract_validator.validate(form)
        except jsonschema.ValidationError as exc:
            raise CompileError(
                f"form declaration violates the portable contract: {relative}: {exc.message}"
            ) from exc
        if form.get("contract") != "portable-grants-form-declaration/v2":
            raise CompileError(
                f"form declaration contract must equal portable-grants-form-declaration/v2: "
                f"{relative}"
            )
        if "source_evidence" in form or "source_refs" not in form:
            raise CompileError(
                f"form declaration must name catalog source_refs, not embed source_evidence: "
                f"{relative}"
            )
        source_refs = form["source_refs"]
        if not isinstance(source_refs, list) or not source_refs:
            raise CompileError(
                f"form declaration source_refs must be a nonempty array: {relative}"
            )
        if len(source_refs) != len(set(source_refs)):
            raise CompileError(
                f"form declaration source_refs contain duplicates: {relative}"
            )
        resolved_sources = []
        for source_ref in source_refs:
            if not isinstance(source_ref, str) or source_ref not in catalog["sources"]:
                raise CompileError(
                    f"form declaration source_ref does not resolve: {relative}: {source_ref!r}"
                )
            resolved_sources.append(catalog["sources"][source_ref])
        compiled_form: dict[str, Any] = {}
        for key, value in form.items():
            if key == "contract":
                continue
            if key == "source_refs":
                compiled_form["source_evidence"] = resolved_sources
            else:
                compiled_form[key] = value
        form = compiled_form
        form_key = form.get("form_key")
        if not isinstance(form_key, str) or not form_key:
            raise CompileError(f"form declaration has invalid form_key: {relative}")
        if form_key in form_keys:
            raise CompileError(f"duplicate form_key: {form_key}")
        seen_paths.add(relative)
        form_keys.append(form_key)
        forms.append(form)

    manifest = {
        "contract": catalog["runtime_contract"],
        "contract_schema": catalog["contract_schema"],
        "bundle": catalog["bundle"],
        "sources": catalog["sources"],
        "schemas": catalog["schemas"],
        "validation_fragments": catalog["validation_fragments"],
        "compatibility": catalog["compatibility"],
        "forms": forms,
    }
    try:
        contract_validator.validate(manifest)
    except jsonschema.ValidationError as exc:
        raise CompileError(
            f"compiled bundle violates the portable contract: {exc.message}"
        ) from exc
    return manifest, form_keys


def _validate_compiled_bundle(bundle_root: Path, manifest: dict[str, Any]) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    api_root = repository_root / "api"
    if not (api_root / "src/form_schema/portable_form_kernel.py").is_file():
        raise CompileError("dependency-neutral portable form kernel is unavailable")
    sys.path.insert(0, str(api_root))
    try:
        from src.form_schema.portable_form_kernel import (
            PortableFormKernelError,
            load_portable_form_kernel,
        )

        with tempfile.TemporaryDirectory(prefix="portable-form-compile-") as temporary:
            validation_root = Path(temporary) / "form-specs"
            shutil.copytree(
                bundle_root,
                validation_root,
                ignore=shutil.ignore_patterns("manifest.json"),
            )
            (validation_root / "manifest.json").write_bytes(_serialized(manifest))
            try:
                load_portable_form_kernel(validation_root)
            except PortableFormKernelError as exc:
                raise CompileError(
                    f"compiled bundle failed kernel validation: {exc}"
                ) from exc
    finally:
        sys.path.remove(str(api_root))


def _serialized(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _parser() -> Parser:
    parser = Parser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument(
        "--check", action="store_true", help="verify manifest is current"
    )
    parser.add_argument("-V", "--version", action="version", version=VERSION)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest, form_keys = compile_bundle(args.bundle)
        output = args.bundle.resolve() / "manifest.json"
        compiled = _serialized(manifest)
        current = output.read_bytes() if output.exists() else None
        _validate_compiled_bundle(args.bundle.resolve(), manifest)
        if args.check and current != compiled:
            raise CompileError("compiled manifest is stale; run without --check")
        if not args.check and current != compiled:
            with tempfile.NamedTemporaryFile(
                dir=output.parent, delete=False
            ) as temporary:
                temporary.write(compiled)
                temporary_path = Path(temporary.name)
            try:
                os.replace(temporary_path, output)
            finally:
                temporary_path.unlink(missing_ok=True)
        status = "current" if args.check or current == compiled else "compiled"
        sys.stdout.write(
            "bundle:\n"
            f"  status: {status}\n"
            f"  forms: {len(form_keys)}\n"
            f"  manifest: {json.dumps(str(output))}\n"
            f"  sha256: {_sha256(output)}\n"
        )
        return 0
    except CompileError as exc:
        _emit_error("compile_failed", str(exc), 1)


if __name__ == "__main__":
    raise SystemExit(main())
