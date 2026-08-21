"""Agent-facing CLI for deterministic form-analysis exports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn

from src.form_schema.analysis_projection import (
    VERSION,
    AnalysisProjectionError,
    build_projection,
    discover_package_inputs,
    select_packages,
    write_projection,
)
from src.form_schema.forms import _ALL_FORMS


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        _stdout(f"error: {json.dumps(message)}")
        _stdout(f"help: {json.dumps(self.format_usage().strip())}")
        raise SystemExit(2)


def _stdout(value: str) -> None:
    sys.stdout.write(value + "\n")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="form-analysis-export", add_help=True)
    parser.add_argument("-v", "-V", "--version", action="version", version=VERSION)
    parser.add_argument("command", nargs="?", choices=("inspect", "export"), default="inspect")
    parser.add_argument(
        "--forms-root",
        type=Path,
        default=Path(__file__).with_name("forms"),
        help="Form package root (default: native form registry directory)",
    )
    parser.add_argument("--form", action="append", default=[], help="Exact form key; repeatable")
    parser.add_argument("--out", type=Path, help="Output directory; required for export")
    return parser


def _toon_string(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _summary_to_toon(summary: dict[str, object], outputs: list[dict[str, object]] | None) -> str:
    lines = ["projection:"]
    for key, value in summary.items():
        lines.append(f"  {key}: {_toon_string(value)}")
    if outputs is not None:
        lines.append(f"outputs[{len(outputs)}]{{name,path,rows,sha256}}:")
        for output in outputs:
            lines.append(
                "  "
                + ",".join(_toon_string(output[key]) for key in ("name", "path", "rows", "sha256"))
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        packages = discover_package_inputs(args.forms_root, _ALL_FORMS)
        selected = select_packages(packages, set(args.form))
        projection = build_projection(selected)
        if args.command == "inspect":
            if args.out is not None:
                parser.error("--out is only valid with export")
            _stdout(_summary_to_toon(projection["summary"], None))
            _stdout('help[1]: "Run form-analysis-export export --out <directory> to write tables"')
            return 0
        if args.out is None:
            parser.error("--out is required for export")
        manifest = write_projection(args.out, projection)
        _stdout(_summary_to_toon(manifest["summary"], manifest["outputs"]))
        return 0
    except AnalysisProjectionError as exc:
        _stdout(f"error: {_toon_string(str(exc))}")
        _stdout('help: "Run form-analysis-export --help for valid inputs"')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
