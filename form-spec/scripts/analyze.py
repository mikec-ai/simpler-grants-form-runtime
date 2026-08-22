#!/usr/bin/env python3
"""The three tables: what the bank holds, which forms ask what, and how forms overlap.

Reads the emitted artifacts, never the specs. That is the point of the contract: this
script would work identically against artifacts produced by a form builder, and it is the
read model a question browser would use.

A form composes a question directly or through another question -- Key Contacts reaches
`generics/person-name` through `poc/details` -- and it asks for a person's name either
way, so the tables count the transitive closure. The direct count is reported alongside,
because the difference is what says how much of the bank is built out of the rest of it.

Usage (from the repo root):
    python3 form-spec/scripts/analyze.py [--json]
"""

from __future__ import annotations

import itertools
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
DIST = REPO / "form-spec" / "dist"


def blocks(kind: str) -> dict[str, dict]:
    root = DIST / kind
    return {
        str(path.parent.relative_to(root)): json.loads(path.read_text())
        for path in sorted(root.rglob("schema.json"))
    }


def refs(node: object) -> set[str]:
    """Every bank question a schema references, by id."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str) and "question-bank/" in value:
                found.add(value.split("question-bank/", 1)[1].removesuffix("/schema.json"))
            else:
                found |= refs(value)
    elif isinstance(node, list):
        for item in node:
            found |= refs(item)
    return found


def form_local_leaves(schema: dict, defs: dict) -> set[str]:
    """Field names a form declares itself rather than composing from the bank.

    A field two forms both declare themselves is a question waiting to be named: the same
    thing asked twice, with the labels and limits kept in step by hand. That number should
    stay at zero, which is what makes the bank worth having rather than merely present.
    """
    out: set[str] = set()

    def walk(node: object, path: tuple[str, ...]) -> bool:
        """True when this subtree reaches the bank; collects the leaves that do not."""
        if not isinstance(node, dict):
            return False
        ref = node.get("$ref")
        if isinstance(ref, str):
            if "question-bank/" in ref:
                return True
            if ref.startswith("#/$defs/"):
                return walk(defs.get(ref.removeprefix("#/$defs/"), {}), path)
        banked = any(
            walk(branch, path)
            for branch in node.get("allOf", [])
            if isinstance(branch, dict) and "if" not in branch
        )
        properties = node.get("properties")
        if properties:
            for name, sub in properties.items():
                walk(sub, (*path, name))
            return True
        items = node.get("items")
        if isinstance(items, dict):
            return walk(items, path) or banked
        if path and not banked:
            out.add(path[-1])
        return banked

    walk(schema, ())
    return out


def closure(direct: set[str], bank_refs: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    queue = list(direct)
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(bank_refs.get(current, set()))
    return seen


def catalogue(kind: str, block_id: str) -> dict:
    path = DIST / kind / block_id / "index.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def main() -> int:
    bank = blocks("question-bank")
    forms = blocks("forms")
    bank_refs = {block_id: refs(schema) for block_id, schema in bank.items()}
    direct = {form_id: refs(schema) for form_id, schema in forms.items()}
    asked = {form_id: closure(used, bank_refs) for form_id, used in direct.items()}

    if "--json" in sys.argv:
        print(
            json.dumps(
                {
                    "questions": sorted(bank),
                    "asks": {f: sorted(q) for f, q in asked.items()},
                    "asksDirectly": {f: sorted(q) for f, q in direct.items()},
                },
                indent=2,
            )
        )
        return 0

    print("## Question inventory\n")
    print("| Question | Entity | Tags | Forms | Asked by |")
    print("| --- | --- | --- | --- | --- |")
    for block_id in sorted(bank, key=lambda q: (-len([f for f in asked if q in asked[f]]), q)):
        entry = catalogue("question-bank", block_id)
        using = sorted(f for f in asked if block_id in asked[f])
        tags = ", ".join(entry.get("tags", [])) or "—"
        print(
            f"| `{block_id}` | {entry.get('entity', '—')} | {tags} | "
            f"{len(using)} | {', '.join(using) or '—'} |"
        )

    print("\n## Form to question\n")
    print("| Form | Questions asked | Composed directly | Reached through another question |")
    print("| --- | --- | --- | --- |")
    for form_id in sorted(forms):
        print(
            f"| {form_id} | {len(asked[form_id])} | {len(direct[form_id])} | "
            f"{len(asked[form_id]) - len(direct[form_id])} |"
        )

    print("\n## Pairwise similarity\n")
    print("| Form A | Form B | Similarity | In common | Share of A | Share of B |")
    print("| --- | --- | --- | --- | --- | --- |")
    rows = []
    for a, b in itertools.combinations(sorted(forms), 2):
        qa, qb = asked[a], asked[b]
        both, either = qa & qb, qa | qb
        rows.append((
            len(both) / len(either) if either else 0.0,
            a,
            b,
            len(both),
            len(both) / len(qa) if qa else 0.0,
            len(both) / len(qb) if qb else 0.0,
        ))
    for score, a, b, both, share_a, share_b in sorted(rows, reverse=True):
        print(f"| {a} | {b} | {score:.0%} | {both} | {share_a:.0%} | {share_b:.0%} |")

    print("\n## Fields not yet in the bank\n")
    local: dict[str, set[str]] = {}
    for form_id, schema in sorted(forms.items()):
        for name in form_local_leaves(schema, schema.get("$defs", {})):
            local.setdefault(name, set()).add(form_id)
    shared = {name: where for name, where in local.items() if len(where) > 1}
    print(
        f"{len(local)} field names are declared by a form rather than composed from the bank; "
        f"**{len(shared)}** of them by more than one form."
    )
    if shared:
        print("\n| Field | Declared by | ")
        print("| --- | --- |")
        for name, where in sorted(shared.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            print(f"| `{name}` | {', '.join(sorted(where))} |")

    print("\n## Reuse\n")
    print("| Form | Questions asked | New to the bank | Already in the bank |")
    print("| --- | --- | --- | --- |")
    # In the order the forms were migrated, which is the order the curve is claimed in.
    known: set[str] = set()
    for form_id in ("key-contacts", "sf424", "sf424a", "sf424-short"):
        if form_id not in asked:
            continue
        new = asked[form_id] - known
        print(
            f"| {form_id} | {len(asked[form_id])} | {len(new)} | {len(asked[form_id]) - len(new)} |"
        )
        known |= asked[form_id]
    return 0


if __name__ == "__main__":
    sys.exit(main())
