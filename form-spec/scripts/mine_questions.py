#!/usr/bin/env python3
"""Mine candidate questions out of the forms that already ship.

The parity work is done and the forms are correct; re-deriving them from PDFs would throw
that away. So the bank is mined from the goldens instead, and this script is what proposes
it. Its output is a proposal for review, never a generated spec: naming a question is a
judgement about meaning, and the whole point of the bank is that a person makes it.

Three signals, strongest first:

1. **A shared reference.** Two fields pointing at `common_shared_v1#/person_name` are the
   same question, and SGG already says so. Nothing to infer.
2. **An identical shape and title.** Same type, constraints, enum, and label, in two forms.
3. **An identical shape and field name.** Catches a question asked under two labels, which
   is the case a shape-only match would merge too eagerly and a title match would miss.

It also proposes **packages**: fields that always travel together and share a name prefix,
like `assistance_listing_number` and `assistance_listing_program_title`. A package is one
question with several members rather than several questions, which is what stops the bank
filling up with halves of things.

Usage (from the repo root, needs the API's toolchain for the goldens):
    python3 form-spec/scripts/mine_questions.py --forms <dump.json>
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
from typing import Any

#: Keywords that describe the value. Two fields agreeing on all of them have the same shape.
SHAPE_KEYWORDS = (
    "type", "format", "pattern", "enum", "minLength", "maxLength",
    "minimum", "maximum", "minItems", "maxItems",
)

#: Words that carry no meaning in a field name, so they are dropped when looking for the
#: prefix a group of fields shares.
NOISE = {"amount", "number", "title", "name", "id", "identifier", "code", "date", "explanation"}


def leaves(schema: dict, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], dict]]:
    """Every scalar field in a resolved schema, with the data path that reaches it."""
    out: list[tuple[tuple[str, ...], dict]] = []
    merged = dict(schema)
    for branch in schema.get("allOf", []):
        if isinstance(branch, dict) and "if" not in branch:
            for key, value in branch.items():
                if key == "properties":
                    merged.setdefault("properties", {}).update(value)
                else:
                    merged.setdefault(key, value)
    properties = merged.get("properties")
    if properties:
        for name, sub in properties.items():
            out.extend(leaves(sub, (*path, name)))
        return out
    items = merged.get("items")
    if isinstance(items, dict):
        return leaves(items, (*path, "[]"))
    if path:
        out.append((path, merged))
    return out


def shape(schema: dict) -> str:
    """A field's value constraints, as a comparable key."""
    return json.dumps({k: schema[k] for k in SHAPE_KEYWORDS if k in schema}, sort_keys=True)


def shape_label(schema: dict) -> str:
    """The same thing, short enough to read in a table.

    A code list is summarized by its size and first member: printing 261 country names in a
    cell hides the one fact that matters, which is that two fields share the list.
    """
    parts: list[str] = [str(schema.get("type", "?"))]
    if "format" in schema:
        parts.append(schema["format"])
    if "enum" in schema:
        members = schema["enum"]
        first = str(members[0])[:24] if members else ""
        parts.append(f"enum({len(members)}: {first}...)" if len(members) > 3 else f"enum{members}")
    for keyword in ("minLength", "maxLength", "minimum", "maximum", "minItems", "maxItems"):
        if keyword in schema:
            parts.append(f"{keyword}={schema[keyword]}")
    if "pattern" in schema:
        parts.append("pattern")
    return " ".join(parts)


def shared_refs(raw: Any, path: tuple[str, ...] = ()) -> dict[tuple[str, ...], str]:
    """The shared-schema definition each field points at, from the unresolved schema."""
    out: dict[tuple[str, ...], str] = {}

    def ref_of(node: dict) -> str | None:
        candidates = [node.get("$ref")]
        for branch in node.get("allOf", []):
            if isinstance(branch, dict):
                candidates.append(branch.get("$ref"))
        for candidate in candidates:
            if isinstance(candidate, str) and "#/" in candidate and "$defs" not in candidate:
                document, _, field = candidate.partition("#/")
                return f"{pathlib.PurePosixPath(document).stem}#{field}"
        return None

    def walk(node: Any, here: tuple[str, ...]) -> None:
        if not isinstance(node, dict):
            return
        found = ref_of(node)
        if found and here:
            out[here] = found
        for name, sub in (node.get("properties") or {}).items():
            walk(sub, (*here, name))
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, (*here, "[]"))
        for branch in node.get("allOf", []):
            if isinstance(branch, dict) and "if" not in branch:
                walk(branch, here)

    walk(raw or {}, path)
    return out


def resolve_local_defs(raw: dict) -> dict:
    """Inline `#/$defs/...` so a form's own definitions do not hide its fields."""
    defs = raw.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            target = defs.get(ref.removeprefix("#/$defs/"), {})
            rest = {k: v for k, v in node.items() if k != "$ref"}
            return {**walk(target), **walk(rest)}
        return {k: walk(v) for k, v in node.items()}

    return walk({k: v for k, v in raw.items() if k != "$defs"})


class Field:
    __slots__ = ("form", "path", "schema", "ref")

    def __init__(self, form: str, path: tuple[str, ...], schema: dict, ref: str | None):
        self.form, self.path, self.schema, self.ref = form, path, schema, ref

    @property
    def name(self) -> str:
        return self.path[-1] if self.path[-1] != "[]" else self.path[-2]

    @property
    def dotted(self) -> str:
        return ".".join(self.path)

    @property
    def title(self) -> str:
        return str(self.schema.get("title") or "")


def collect(dump: dict) -> list[Field]:
    fields: list[Field] = []
    for form, artifacts in sorted(dump.items()):
        raw = artifacts.get("raw") or {}
        refs = shared_refs(resolve_local_defs(raw))
        for path, schema in leaves(artifacts.get("resolved") or {}):
            key = tuple(p for p in path)
            fields.append(Field(form, path, schema, refs.get(key)))
    return fields


def group(fields: list[Field]) -> list[dict]:
    """Candidate questions, each with the signal that found it."""
    remaining = list(fields)
    groups: list[dict] = []

    def take(key_of, signal: str) -> None:
        nonlocal remaining
        buckets: dict[Any, list[Field]] = collections.defaultdict(list)
        for field in remaining:
            key = key_of(field)
            if key is not None:
                buckets[key].append(field)
        kept: list[Field] = []
        for key, members in buckets.items():
            forms = {f.form for f in members}
            if len(forms) < 2 and signal != "shared reference":
                kept.extend(members)
                continue
            groups.append({"signal": signal, "key": key, "members": members})
        for field in remaining:
            if key_of(field) is None:
                kept.append(field)
        remaining = [f for f in kept]

    take(lambda f: f.ref, "shared reference")
    take(lambda f: (f.title, shape(f.schema)) if f.title else None, "same title and shape")
    take(lambda f: (f.name, shape(f.schema)), "same field name and shape")

    for field in remaining:
        groups.append({"signal": "unique", "key": (field.name,), "members": [field]})
    return groups


TOKEN = re.compile(r"[a-z0-9]+")


def ui_order(ui: Any) -> list[str]:
    """The field names a form renders, in order, flattened out of its UI schema."""
    out: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        definition = node.get("definition")
        for pointer in definition if isinstance(definition, list) else [definition]:
            if isinstance(pointer, str):
                out.append(pointer.rstrip("/").split("/")[-1])
        for child in node.get("children") or []:
            walk(child)

    walk(ui or [])
    return out


def packages(fields: list[Field], dump: dict) -> list[dict]:
    """Fields that travel together and share a name prefix: one question, several members.

    Two conditions, and both are needed. The prefix has to be at least two words once the
    words that carry no meaning on their own are dropped -- `number`, `title`, `amount` --
    because a one-word prefix groups `first_name` with `first_quarter_amount`. And the
    members have to be **adjacent in the rendered order** on some form, because that is what
    travelling together means: a form that asks for an assistance listing asks for its number
    and its title side by side, in one box.
    """
    orders = {form: ui_order(artifacts.get("ui")) for form, artifacts in dump.items()}
    by_name: dict[str, list[Field]] = collections.defaultdict(list)
    for field in fields:
        by_name[field.name].append(field)

    def tokens(name: str) -> list[str]:
        return [t for t in TOKEN.findall(name) if t not in NOISE]

    by_prefix: dict[tuple[str, ...], dict[str, set[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(set)
    )
    for field in fields:
        parts = tokens(field.name)
        for size in range(2, len(parts) + 1):
            by_prefix[tuple(parts[:size])][field.form].add(field.name)

    out: list[dict] = []
    for prefix, per_form in by_prefix.items():
        names = {name for names in per_form.values() for name in names}
        if len(names) < 2:
            continue
        adjacent_in = [
            form for form, members in per_form.items()
            if len(members) > 1 and adjacent(orders.get(form, []), members)
        ]
        if not adjacent_in:
            continue
        out.append(
            {
                "prefix": "-".join(prefix),
                "members": sorted(names),
                "forms": sorted(per_form),
                "adjacentIn": sorted(adjacent_in),
                "kind": classify(prefix, sorted(names), by_name),
            }
        )

    # Prefer the longest prefix describing a given set of members.
    # Longest prefix first on a tie: `point-of-contact` names the group, `point-of` does not.
    out.sort(
        key=lambda p: (
            -len(p["members"]), -len(p["forms"]), -p["prefix"].count("-"), p["prefix"]
        )
    )
    seen: set[frozenset[str]] = set()
    deduped: list[dict] = []
    for package in out:
        key = frozenset(package["members"])
        if key in seen or any(key < other for other in seen):
            continue
        seen.add(key)
        deduped.append(package)
    return deduped


#: A differing suffix containing one of these says the member elaborates on another's answer.
FOLLOW_UP_WORDS = {"explanation", "specify", "other", "description", "available", "detail"}


def classify(prefix: tuple[str, ...], members: list[str], by_name: dict[str, list[Field]]) -> str:
    """Which of three different things a co-occurring group actually is.

    The distinction decides what goes in the bank, so it is worth naming. Shape is the
    signal, because it is the one that does not depend on guessing what an English word
    means in a field name:

    * **answer and follow-up** -- one member elaborates on another's answer:
      `applicant_type_code` with `applicant_type_other_specify`. One question, whose second
      member is conditionally required on the first -- which the question itself can say.
    * **one question, composed more than once** -- the members have the same shape, or one of
      them *is* the bare prefix and the rest are qualified copies of it.
      `congressional_district_applicant` and `congressional_district_program_project` ask
      the same thing about two different subjects. One question, composed twice.
    * **package** -- the shapes differ, so the members are different attributes of one thing.
      `assistance_listing_number` and `assistance_listing_program_title` are the number and
      the title of one assistance listing, and the bank should hold one question with two
      members. Splitting them fills the bank with halves of things.

    Copies that disagree on their constraints are called out: the same question cannot have
    two different limits, so one of them is a defect.
    """
    suffixes = {name: tuple(TOKEN.findall(name))[len(prefix):] for name in members}
    words = {word for suffix in suffixes.values() for word in suffix}
    schemas = [by_name[name][0].schema for name in members if name in by_name]
    shapes = {shape(schema) for schema in schemas}

    if words & FOLLOW_UP_WORDS:
        return "answer and follow-up"

    qualified = any(not suffix for suffix in suffixes.values())
    if qualified or len(shapes) == 1:
        if len(shapes) > 1:
            return "one question, composed more than once -- CONSTRAINTS DISAGREE"
        return "one question, composed more than once"

    return "package"


def adjacent(order: list[str], members: set[str]) -> bool:
    """True when every member appears in one unbroken run of the rendered order."""
    positions = sorted(index for index, name in enumerate(order) if name in members)
    if len(positions) < 2:
        return False
    return positions[-1] - positions[0] == len(positions) - 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forms", required=True, help="JSON dump of the goldens")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--min-forms", type=int, default=2)
    args = parser.parse_args()

    dump = json.loads(pathlib.Path(args.forms).read_text())
    fields = collect(dump)
    groups = group(fields)
    shared = [g for g in groups if len({m.form for m in g["members"]}) >= args.min_forms]
    shared.sort(key=lambda g: -len({m.form for m in g["members"]}))

    if args.json:
        print(
            json.dumps(
                {
                    "fieldCount": len(fields),
                    "formCount": len(dump),
                    "candidates": [
                        {
                            "signal": g["signal"],
                            "key": list(g["key"]) if isinstance(g["key"], tuple) else g["key"],
                            "forms": sorted({m.form for m in g["members"]}),
                            "fields": sorted({m.dotted for m in g["members"]}),
                        }
                        for g in shared
                    ],
                    "packages": packages(fields, dump),
                },
                indent=2,
            )
        )
        return 0

    print(f"{len(fields)} fields across {len(dump)} forms.\n")
    print(f"## Candidate questions asked by {args.min_forms}+ forms\n")
    print("| Forms | Signal | Question | Asked as |")
    print("| --- | --- | --- | --- |")
    for g in shared:
        forms = sorted({m.form for m in g["members"]})
        names = sorted({m.name for m in g["members"]})
        print(
            f"| {len(forms)} | {g['signal']} | `{label(g)}` | "
            f"{', '.join(names[:5])}{' ...' if len(names) > 5 else ''} |"
        )

    once = [g for g in groups if len({m.form for m in g["members"]}) == 1]
    print(f"\n{len(once)} candidates appear on one form only.\n")

    print("## Package candidates\n")
    print("| Group | Kind | Members | Forms | Side by side on |")
    print("| --- | --- | --- | --- | --- |")
    grouped = packages(fields, dump)
    for package in sorted(grouped, key=lambda p: (p["kind"], -len(p["forms"]))):
        print(
            f"| `{package['prefix']}` | {package['kind']} | {', '.join(package['members'])} | "
            f"{len(package['forms'])} | {', '.join(package['adjacentIn'])} |"
        )
    return 0


def label(candidate: dict) -> str:
    """How a candidate reads in a table: its shared reference, or its title and shape."""
    key = candidate["key"]
    if isinstance(key, str):
        return key
    member = candidate["members"][0]
    return f"{key[0]} / {shape_label(member.schema)}"


if __name__ == "__main__":
    sys.exit(main())
