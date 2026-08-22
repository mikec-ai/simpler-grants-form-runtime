"""Dump every shipping form's schemas, for `mine_questions.py` to read.

Runs against the API package, so it needs the API's toolchain. Its output is the input to
mining: the forms that ship are the evidence for what the bank should hold.

Usage (from the repo root, with the API's environment):
    python3 form-spec/scripts/dump_goldens.py > form-spec/mined/goldens.json
"""

import importlib.util
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))

from src.form_schema.jsonschema_resolver import resolve_jsonschema  # noqa: E402

FORMS = REPO / "api/src/form_schema/forms"
out = {}
for d in sorted(FORMS.iterdir()):
    if not d.is_dir() or d.name.startswith("_"):
        continue
    for major in sorted(p for p in d.iterdir() if p.is_dir() and p.name.isdigit()):
        for minor in sorted(p for p in major.iterdir() if p.is_dir()):
            f = minor / "form_json.py"
            if not f.is_file():
                continue
            spec = importlib.util.spec_from_file_location(f"{d.name}_{major.name}_{minor.name}", f)
            m = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(m)
            except Exception as e:
                print(f"SKIP {d.name} {e}", file=sys.stderr)
                continue
            key = f"{d.name}"
            out[key] = {
                "raw": getattr(m, "FORM_JSON_SCHEMA", None),
                "resolved": resolve_jsonschema(getattr(m, "FORM_JSON_SCHEMA", {}) or {}),
                "ui": getattr(m, "FORM_UI_SCHEMA", None),
                "rules": getattr(m, "FORM_RULE_SCHEMA", None),
                "xml": getattr(m, "FORM_XML_TRANSFORM_RULES", None),
            }
print(json.dumps(out, default=str))
