#!/usr/bin/env python3
"""Build the portable form analysis workbook from generated CSV tables."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Never

import xlsxwriter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANALYSIS = ROOT / "build" / "portable-form-artifacts" / "analysis"
DEFAULT_OUTPUT = DEFAULT_ANALYSIS / "form-analysis.xlsx"
VERSION = "0.1.0"

SHEETS = {
    "Forms": "forms.csv",
    "Form Pairs": "form-pairs.csv",
    "Questions": "questions.csv",
    "Role-qualified Questions": "role-qualified-questions.csv",
    "Form Question Map": "form-question-map.csv",
}


def _rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def build(analysis_dir: Path, output: Path) -> dict[str, int]:
    tables = {name: _rows(analysis_dir / filename) for name, filename in SHEETS.items()}
    if any(not rows for rows in tables.values()):
        raise ValueError("analysis tables must contain headers")

    output.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(output, {"constant_memory": True})
    workbook.set_properties(
        {
            "title": "Declarative Form Reuse Analysis",
            "comments": "Generated from portable form declarations during CI.",
            "created": datetime(2000, 1, 1, tzinfo=UTC),
        }
    )
    header = workbook.add_format(
        {
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#17324D",
            "text_wrap": True,
        }
    )
    title = workbook.add_format(
        {"bold": True, "font_color": "#FFFFFF", "bg_color": "#17324D", "font_size": 20}
    )
    note = workbook.add_format({"bg_color": "#FFF4D6", "text_wrap": True})
    percent = workbook.add_format({"num_format": "0.0%"})

    overview = workbook.add_worksheet("Overview")
    overview.hide_gridlines(2)
    overview.merge_range("A1:H2", "Declarative Form Reuse Analysis", title)
    overview.merge_range(
        "A3:H3",
        "Generated from the same portable declarations used to compile the forms.",
    )
    overview.write_row(
        "A5",
        [
            "Forms",
            "Question templates",
            "Role-qualified identities",
            "Question occurrences",
        ],
        header,
    )
    overview.write_formula("A6", "=COUNTA(Forms!A2:A1000)")
    overview.write_formula("B6", "=COUNTA(Questions!A2:A5000)")
    overview.write_formula("C6", "=COUNTA('Role-qualified Questions'!A2:A10000)")
    overview.write_formula("D6", "=COUNTIF('Form Question Map'!E2:E20000,\"semantic_question\")")
    overview.merge_range(
        "A9:H11",
        (
            "Boundary: mappings are agent-proposed unless explicitly accepted. "
            "Only accepted mappings may contribute to published coverage."
        ),
        note,
    )
    overview.set_column("A:H", 24)
    overview.freeze_panes(3, 0)

    for sheet_name, rows in tables.items():
        sheet = workbook.add_worksheet(sheet_name[:31])
        sheet.hide_gridlines(2)
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                cell_format = header if row_index == 0 else None
                if row_index > 0 and value in {"True", "False"}:
                    sheet.write_boolean(row_index, column_index, value == "True", cell_format)
                elif row_index > 0:
                    try:
                        number = float(value)
                    except ValueError:
                        sheet.write(row_index, column_index, value, cell_format)
                    else:
                        use_percent = (
                            "similarity" in rows[0][column_index].lower()
                            or "coverage" in rows[0][column_index].lower()
                        )
                        sheet.write_number(
                            row_index,
                            column_index,
                            number,
                            percent if use_percent else cell_format,
                        )
                else:
                    sheet.write(row_index, column_index, value, cell_format)
        sheet.freeze_panes(1, 0)
        sheet.autofilter(0, 0, len(rows) - 1, len(rows[0]) - 1)
        for column_index, heading in enumerate(rows[0]):
            width = min(max(len(heading) + 2, 14), 60)
            sheet.set_column(column_index, column_index, width)

    workbook.close()
    return {
        "sheets": len(tables) + 1,
        "forms": len(tables["Forms"]) - 1,
    }


class StructuredParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        sys.stdout.write(
            "error:\n"
            "  code: usage\n"
            "help:\n"
            "  command: python scripts/build_portable_form_analysis_workbook.py --help\n"
        )
        sys.stderr.write(f"{message}\n")
        raise SystemExit(2)


def parser() -> argparse.ArgumentParser:
    value = StructuredParser(description=__doc__)
    value.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS)
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    value.add_argument("--version", action="version", version=VERSION)
    return value


def cli(argv: list[str]) -> int:
    try:
        args = parser().parse_args(argv)
        counts = build(args.analysis_dir, args.output)
    except (OSError, ValueError, xlsxwriter.exceptions.XlsxWriterException) as exc:
        sys.stdout.write("error:\n  code: workbook_build_failed\n")
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write(
        "workbook:\n"
        "  status: generated\n"
        f"  sheets: {counts['sheets']}\n"
        f"  forms: {counts['forms']}\n"
        f"  output: {args.output}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
