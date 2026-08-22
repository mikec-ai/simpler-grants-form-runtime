#!/usr/bin/env python3
"""Verify portable catalog sources against exact blobs in local Git repositories."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Never

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "api"))

from src.form_schema.portable_source_provenance import (  # ruff: ignore[module-import-not-at-top-of-file]
    SourceProvenanceError,
    verify_catalog_sources,
)

VERSION = "0.1.0"
COMMAND = "python scripts/verify_portable_source_provenance.py"


def _emit_error(code: str, message: str, status: int) -> Never:
    sys.stdout.write(
        f"error:\n  code: {code}\n  command: {json.dumps(COMMAND + ' --help')}\n"
    )
    sys.stderr.write(f"{message}\n")
    raise SystemExit(status)


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        _emit_error("usage", message, 2)


def _parser() -> Parser:
    parser = Parser(add_help=False, description=__doc__)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--repositories", type=Path)
    parser.add_argument("--help", action="store_true")
    parser.add_argument("-v", "-V", "--version", action="version", version=VERSION)
    return parser


def _emit_help() -> None:
    sys.stdout.write(
        "command:\n"
        "  name: verify_portable_source_provenance\n"
        '  description: "Verify portable catalog sources against exact blobs in local Git repositories"\n'
        f"  usage: {json.dumps(COMMAND + ' --catalog <path> --repositories <path>')}\n"
        "flags[4]{name,required,description}:\n"
        '  --catalog,true,"Portable catalog JSON containing sources"\n'
        '  --repositories,true,"Local repository map JSON"\n'
        '  --help,false,"Show this reference"\n'
        '  -v|-V|--version,false,"Show the bare CLI version"\n'
        "examples[1]:\n"
        '  "python scripts/verify_portable_source_provenance.py --catalog form-specs/catalog.json --repositories local-source-repositories.json"\n'
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.help:
        _emit_help()
        return 0
    if args.catalog is None:
        _emit_error("usage", "--catalog is required", 2)
    if args.repositories is None:
        _emit_error("usage", "--repositories is required", 2)
    try:
        result = verify_catalog_sources(args.catalog, args.repositories)
    except SourceProvenanceError as exc:
        _emit_error("source_provenance_failed", str(exc), 1)
    sys.stdout.write(
        "verification:\n"
        "  status: verified\n"
        f"  sources: {result.sources}\n"
        f"  repositories: {result.repositories}\n"
        f"  catalog: {json.dumps(str(args.catalog.resolve()))}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
