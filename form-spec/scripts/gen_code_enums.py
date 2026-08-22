#!/usr/bin/env python3
"""Generate TypeSpec code enums from the SGG Python constants (design decision D7).

The state and country code lists are maintained in the SGG API as Python lists. They are
the authority; the bank must not fork them. This script projects them into TypeSpec so
that a form referencing `StateCode.CA` is compile-checked, and so that a change upstream
shows up as a diff here rather than as a silent divergence.

Usage (from the repo root):
    python3 form-spec/scripts/gen_code_enums.py
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SOURCE = REPO / "api" / "src" / "form_schema" / "shared" / "shared_form_constants.py"
TARGET = REPO / "form-spec" / "specs" / "question-bank" / "generated" / "codes.tsp"


def load_constants() -> dict[str, list[str]]:
    namespace: dict[str, object] = {}
    exec(compile(SOURCE.read_text(), str(SOURCE), "exec"), namespace)
    return {name: namespace[name] for name in ("STATES", "COUNTRIES")}  # type: ignore[misc]


def member(value: str) -> tuple[str, str]:
    """Split `"CA: California"` into the enum member name and its wire value."""
    code, _, _label = value.partition(":")
    return code.strip(), value


def emit_enum(name: str, doc: str, title: str, values: list[str]) -> str:
    lines = [f'@summary("{title}")', f'@doc("{doc}")', f"enum {name} {{"]
    for value in values:
        member_name, wire = member(value)
        lines.append(f'  {member_name}: "{wire}",')
    lines.append("}")
    return "\n".join(lines)


def main() -> int:
    constants = load_constants()
    body = "\n\n".join([
        emit_enum("StateCode", "US State or Territory Code", "State", constants["STATES"]),
        emit_enum("CountryCode", "Country Code", "Country", constants["COUNTRIES"]),
    ])
    header = (
        "// GENERATED FILE — do not edit.\n"
        "// Source: api/src/form_schema/shared/shared_form_constants.py\n"
        "// Regenerate: python3 form-spec/scripts/gen_code_enums.py\n"
        "\n"
        'import "../index.tsp";\n'
        "\n"
        "namespace QuestionBank.Generics;\n"
        "\n"
    )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(header + body + "\n")
    print(f"wrote {TARGET.relative_to(REPO)}: {sum(len(v) for v in constants.values())} members")
    return 0


if __name__ == "__main__":
    sys.exit(main())
