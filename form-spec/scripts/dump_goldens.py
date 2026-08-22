#!/usr/bin/env python3
"""Dump every shipping form's schemas, for the mining and scanning scripts to read.

Runs against the API package, so it needs the API's toolchain. Its output is the input to
mining: the forms that ship are the evidence for what the bank should hold.

Usage (from the repo root, with the API's environment):
    python3 form-spec/scripts/dump_goldens.py > form-spec/mined/goldens.json
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[2]
FORMS = REPO / "api/src/form_schema/forms"


def load_form_module(path: pathlib.Path, name: str) -> types.ModuleType:
    """Load one `form_json.py` on its own, without importing the forms package."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dump() -> dict[str, Any]:
    """Every form's raw and resolved schema, UI schema, rules, and XML transform."""
    # The API is imported here rather than at module scope because it is only importable
    # once its own directory is on the path, and a top-level import after a path change is
    # both a lint error and a genuine trap for the next reader.
    sys.path.insert(0, str(REPO / "api"))
    from src.form_schema.jsonschema_resolver import resolve_jsonschema

    out: dict[str, Any] = {}
    for form in sorted(FORMS.iterdir()):
        if not form.is_dir() or form.name.startswith("_"):
            continue
        for major in sorted(p for p in form.iterdir() if p.is_dir() and p.name.isdigit()):
            for minor in sorted(p for p in major.iterdir() if p.is_dir()):
                source = minor / "form_json.py"
                if not source.is_file():
                    continue
                try:
                    module = load_form_module(source, f"{form.name}_v{major.name}_{minor.name}")
                except Exception as error:
                    print(f"skipped {form.name}: {error}", file=sys.stderr)
                    continue
                schema = getattr(module, "FORM_JSON_SCHEMA", None) or {}
                out[form.name] = {
                    "raw": schema,
                    "resolved": resolve_jsonschema(schema),
                    "ui": getattr(module, "FORM_UI_SCHEMA", None),
                    "rules": getattr(module, "FORM_RULE_SCHEMA", None),
                    "xml": getattr(module, "FORM_XML_TRANSFORM_RULES", None),
                }
    return out


def main() -> int:
    print(json.dumps(dump(), default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
