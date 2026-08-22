#!/usr/bin/env python3
"""Does each form's JSON shape agree with its own XML target shape?

The question this answers is which shape differences between forms are **upstream reality**
and which are SGG's own divergence, because the two have different fates. A form whose JSON
nests exactly where its XSD nests is being faithful, and an adapter that reshapes it is doing
necessary work. A form whose JSON disagrees with its own XSD has a defect, and the right fix
is to the form rather than to the adapter.

The comparison uses `FORM_XML_TRANSFORM_RULES` as the stand-in for the XSD: a field mapped
with `type: "nested_object"` is a complex type in the wire format, and a field mapped without
it is a simple element. So for every field the form asks:

* the JSON holds an object and the XML says `nested_object` -> agree, nested
* the JSON holds a leaf and the XML says a plain target -> agree, flat
* anything else -> a divergence, reported with which side nests

Usage (from the repo root):
    python3 form-spec/scripts/scan_shape_agreement.py --forms <dump.json>
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
from typing import Any

#: Keys in an XML transform node that are not field names.
XML_META = {"xml_transform", "_xml_config"}


def merged(node: dict[str, Any]) -> dict[str, Any]:
    """A schema node with its `allOf` composition collapsed in."""
    out = dict(node)
    for branch in node.get("allOf", []):
        if not isinstance(branch, dict) or "if" in branch:
            continue
        inner = merged(branch)
        out.setdefault("properties", {}).update(inner.get("properties", {}))
        for key, value in inner.items():
            if key not in ("properties", "allOf"):
                out.setdefault(key, value)
    return out


def json_shape(schema: dict[str, Any]) -> dict[str, bool]:
    """Data path -> whether the JSON holds an object there."""
    out: dict[str, bool] = {}

    def walk(node: Any, path: str) -> None:
        if not isinstance(node, dict):
            return
        node = merged(node)
        properties = node.get("properties")
        if properties:
            for name, sub in properties.items():
                here = f"{path}.{name}".lstrip(".")
                inner = merged(sub) if isinstance(sub, dict) else {}
                items = inner.get("items")
                item_is_object = isinstance(items, dict) and bool(merged(items).get("properties"))
                out[here] = bool(inner.get("properties")) or item_is_object
                walk(sub, here)
            return
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, path)

    walk(schema, "")
    return out


def xml_shape(rules: dict[str, Any]) -> dict[str, bool]:
    """Data path -> whether the wire format nests there."""
    out: dict[str, bool] = {}

    def walk(node: Any, path: str) -> None:
        if not isinstance(node, dict):
            return
        for name, sub in node.items():
            if name in XML_META or not isinstance(sub, dict):
                continue
            here = f"{path}.{name}".lstrip(".")
            transform = sub.get("xml_transform") or {}
            children = [k for k in sub if k not in XML_META and isinstance(sub[k], dict)]
            out[here] = transform.get("type") == "nested_object" or bool(children)
            walk(sub, here)

    walk(rules or {}, "")
    return out


def scan(dump: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
    """Per form, the paths where the JSON and the wire format disagree about nesting."""
    findings: dict[str, list[tuple[str, str]]] = {}
    for form, artifacts in sorted(dump.items()):
        of_json = json_shape(artifacts.get("resolved") or {})
        of_xml = xml_shape(artifacts.get("xml") or {})
        for path, json_nests in sorted(of_json.items()):
            if path not in of_xml:
                continue
            if json_nests == of_xml[path]:
                continue
            findings.setdefault(form, []).append((
                path,
                "JSON nests, wire is flat" if json_nests else "wire nests, JSON is flat",
            ))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forms", required=True, help="JSON dump of the goldens")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    dump = json.loads(pathlib.Path(args.forms).read_text())
    findings = scan(dump)

    if args.json:
        print(json.dumps(findings, indent=2))
        return 0

    covered = sum(1 for a in dump.values() if xml_shape(a.get("xml") or {}))
    print(f"Compared {covered} of {len(dump)} forms against their own XML transform.\n")

    if not findings:
        print("Every form's JSON shape agrees with its wire format.")
    else:
        print("## Forms whose JSON shape disagrees with their own wire format\n")
        print("| Form | Path | Disagreement |")
        print("| --- | --- | --- |")
        for form, rows in sorted(findings.items()):
            for path, kind in rows:
                print(f"| {form} | `{path}` | {kind} |")

    print("\n## Where the same property holds different members\n")
    # Nesting alone is not the question. SF-424 and SF-424-Short both nest `contact_person`,
    # but one holds five name parts and the other holds the whole contact -- and the wire
    # format is what says whether that is a divergence or two genuinely different asks.
    print("| Property | Members | Wire element | Asked by |")
    print("| --- | --- | --- | --- |")
    for leaf, rows in sorted(members_by_property(dump).items()):
        shapes = {frozenset(m) for _, m, _ in rows}
        if len(rows) < 2 or len(shapes) < 2:
            continue
        # One row per distinct membership: the same address type repeated four times on one
        # form says nothing, and four different address types across forms says everything.
        seen: dict[tuple[frozenset[str], str], list[str]] = collections.defaultdict(list)
        for form, members, target in rows:
            seen[frozenset(members), target or "--"].append(form)
        for (members, target), forms in sorted(
            seen.items(), key=lambda item: (-len(item[0][0]), item[0][1])
        ):
            where = ", ".join(sorted(set(forms)))
            print(f"| `{leaf}` | {', '.join(sorted(members))} | {target} | {where} |")
    return 0


def members_by_property(
    dump: dict[str, Any],
) -> dict[str, list[tuple[str, list[str], str | None]]]:
    """Property name ->, per form, the members it holds and the wire element it maps to."""
    out: dict[str, list[tuple[str, list[str], str | None]]] = collections.defaultdict(list)

    def walk(
        node: dict[str, Any],
        path: str,
        form: str,
        targets: dict[str, str],
    ) -> None:
        for name, sub in (node.get("properties") or {}).items():
            if not isinstance(sub, dict):
                continue
            inner = merged(sub)
            items = inner.get("items")
            if isinstance(items, dict):
                inner = merged(items)
            here = f"{path}.{name}".lstrip(".")
            if inner.get("properties"):
                out[name].append((form, sorted(inner["properties"]), targets.get(here)))
                walk(inner, here, form, targets)

    for form, artifacts in sorted(dump.items()):
        walk(
            merged(artifacts.get("resolved") or {}),
            "",
            form,
            xml_targets(artifacts.get("xml") or {}),
        )
    return out


def xml_targets(rules: dict[str, Any]) -> dict[str, str]:
    """Data path -> the wire element it maps to."""
    out: dict[str, str] = {}

    def walk(node: Any, path: str) -> None:
        if not isinstance(node, dict):
            return
        for name, sub in node.items():
            if name in XML_META or not isinstance(sub, dict):
                continue
            here = f"{path}.{name}".lstrip(".")
            target = (sub.get("xml_transform") or {}).get("target")
            if target:
                out[here] = target
            walk(sub, here)

    walk(rules or {}, "")
    return out


if __name__ == "__main__":
    sys.exit(main())
