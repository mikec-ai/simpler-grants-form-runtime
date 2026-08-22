"""Helpers for proving that a projected form and its hand-written original agree.

Two independent assertions, because either alone is weak:

* **Structural.** Resolve both schemas and compare them leaf by leaf. Anything that
  differs must be named in the test's allow-list with a reason, so an accidental
  divergence fails while a deliberate improvement is on the record.

* **Behavioural.** Validate a corpus of payloads against both schemas and require
  identical verdicts. This is the assertion that matters: it is indifferent to how the
  schemas are composed and sensitive to every difference that could reach an applicant.
  The corpus is derived from the schema, so it grows with the form rather than needing to
  be maintained alongside it.
"""

from __future__ import annotations

import copy
import dataclasses
from typing import Any

from src.form_schema.jsonschema_validator import validate_json_schema

# ---------------------------------------------------------------------------
# structural


@dataclasses.dataclass(frozen=True)
class Difference:
    pointer: str
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind} at {self.pointer}: {self.detail}"


#: Keywords whose value is a conjunction: the order of the branches carries no meaning, so
#: comparing them positionally would report a permutation as a difference.
_UNORDERED_BRANCHES = ("allOf", "anyOf", "oneOf")


def schema_differences(projected: Any, golden: Any, pointer: str = "") -> list[Difference]:
    """Every leaf-level difference between two resolved schemas."""
    out: list[Difference] = []
    if isinstance(projected, dict) and isinstance(golden, dict):
        for key in sorted(set(projected) | set(golden)):
            child = f"{pointer}/{key}"
            if key not in projected:
                out.append(Difference(child, "only-in-golden", _brief(golden[key])))
            elif key not in golden:
                out.append(Difference(child, "only-in-projected", _brief(projected[key])))
            elif key in _UNORDERED_BRANCHES and _is_branch_list(projected[key], golden[key]):
                out.extend(_branch_differences(projected[key], golden[key], child))
            else:
                out.extend(schema_differences(projected[key], golden[key], child))
    elif isinstance(projected, list) and isinstance(golden, list):
        # `required` and `enum` are sets in effect; order carries no meaning.
        if _unordered(projected) and _unordered(golden):
            if sorted(projected) != sorted(golden):
                out.append(Difference(pointer, "set", f"{sorted(projected)} vs {sorted(golden)}"))
        elif len(projected) != len(golden):
            out.append(Difference(pointer, "length", f"{len(projected)} vs {len(golden)}"))
        else:
            for index, (a, b) in enumerate(zip(projected, golden)):
                out.extend(schema_differences(a, b, f"{pointer}/{index}"))
    elif projected != golden:
        out.append(Difference(pointer, "value", f"{projected!r} vs {golden!r}"))
    return out


def _is_branch_list(projected: Any, golden: Any) -> bool:
    return isinstance(projected, list) and isinstance(golden, list)


def _key(branch: Any) -> str:
    import json

    return json.dumps(branch, sort_keys=True)


def _branch_differences(projected: list[Any], golden: list[Any], pointer: str) -> list[Difference]:
    """Compare two conjunctions, ignoring the order the branches are written in.

    Identical branches are paired off first, so a reordered `allOf` reports nothing. What
    is left is compared position by position, which keeps the pointer precise enough to
    explain -- a branch whose `title` changed reports as that title, not as the whole
    branch.
    """
    remaining_golden = list(golden)
    unmatched: list[Any] = []
    for branch in projected:
        match = next((g for g in remaining_golden if _key(g) == _key(branch)), None)
        if match is None:
            unmatched.append(branch)
        else:
            remaining_golden.remove(match)

    if len(unmatched) == len(remaining_golden):
        out: list[Difference] = []
        for index, (ours, theirs) in enumerate(zip(unmatched, remaining_golden)):
            out.extend(schema_differences(ours, theirs, f"{pointer}/{index}"))
        return out

    out = [
        Difference(f"{pointer}/{index}", "only-in-projected", _brief(branch))
        for index, branch in enumerate(unmatched)
    ]
    out += [
        Difference(f"{pointer}/{index}", "only-in-golden", _brief(branch))
        for index, branch in enumerate(remaining_golden)
    ]
    return out


def _unordered(value: list[Any]) -> bool:
    return all(isinstance(item, str) for item in value)


def _brief(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 120 else text[:117] + "..."


#: JSON Schema keywords that describe a value rather than name or explain it. When a form
#: field that used to be spelled out inline becomes a reference to a bank question, these
#: are the keywords that move from the property into the `allOf` branch.
_CONSTRAINT_KEYWORDS = (
    "type",
    "enum",
    "const",
    "format",
    "pattern",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "minItems",
    "maxItems",
    "items",
    "allOf",
)


def composed(fields: dict[str, str]) -> dict[str, str]:
    """Allow-list entries for fields the bank now owns that the golden spelled out inline.

    One entry per field rather than per keyword: the decision is "this became a question",
    and its consequence is that the field's constraints moved into the reference. Returns
    the expanded pointer suffixes, so the test still fails on any difference that is not
    one of them -- a changed `maxLength`, say, rather than a relocated one.
    """
    out: dict[str, str] = {}
    for field, reason in fields.items():
        for keyword in (*_CONSTRAINT_KEYWORDS, "title", "description"):
            # The field itself, the reference it now goes through, and -- when it is a
            # list -- the entries, which compose the question one level down.
            for prefix in (
                f"*/properties/{field}",
                f"*/properties/{field}/allOf/0",
                f"*/properties/{field}/items",
                f"*/properties/{field}/items/allOf/0",
            ):
                out[f"{prefix}/{keyword}"] = reason
    return out


def _matches(pointer: str, pattern: str) -> bool:
    """Match a difference's pointer against one allow-list key.

    Three forms, so that an entry says exactly how much it means to cover:

    * `/properties/remarks/type` -- that pointer and nothing else.
    * `*/properties/phone/allOf/0/description` -- that suffix anywhere, for a question
      reached from more than one place in a form.
    * `/$defs/*` -- that subtree, for a wholesale relocation.

    Suffix matching is anchored to a segment boundary, so `/description` cannot quietly
    absorb every `.../allOf/0/description` in the form.
    """
    if pattern.startswith("*"):
        return pointer.endswith(pattern[1:])
    if pattern.endswith("/*"):
        return pointer == pattern[:-2] or pointer.startswith(pattern[:-1])
    return pointer == pattern


def unused(differences: list[Difference], allowed: dict[str, str]) -> list[str]:
    """Allow-list entries that explain a difference no longer present.

    An explanation for something that has stopped being true is worse than no explanation,
    so a hand-written entry going stale should fail the test that relies on it.
    """
    return sorted(
        pattern
        for pattern in allowed
        if not any(_matches(difference.pointer, pattern) for difference in differences)
    )


def unused_fields(differences: list[Difference], fields: dict[str, str]) -> list[str]:
    """Fields claimed as composed that no longer differ from the golden at all.

    The `composed` expansion covers many keywords per field on purpose, so most of its
    entries are unused for any given field. What must not go stale is the *field*: if it
    matches nothing, the claim that the bank absorbed it is no longer doing any work.
    """
    return sorted(
        field
        for field in fields
        if not any(f"/properties/{field}/" in d.pointer for d in differences)
    )


def unexplained(differences: list[Difference], allowed: dict[str, str]) -> list[Difference]:
    """Differences with no entry in the allow-list.

    An allow-list key is a pointer suffix, so one entry covers a definition wherever it
    is reached from -- a bank question composed twice is one decision, not two.
    """
    return [
        difference
        for difference in differences
        if not any(_matches(difference.pointer, pattern) for pattern in allowed)
    ]


# ---------------------------------------------------------------------------
# behavioural


def leaf_paths(schema: dict[str, Any], prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """Every scalar field in a resolved schema, as a path through the data."""
    out: list[tuple[str, ...]] = []
    for branch in schema.get("allOf", []):
        out.extend(leaf_paths(branch, prefix))
    properties = schema.get("properties")
    if properties:
        for name, sub in properties.items():
            out.extend(leaf_paths(sub, (*prefix, name)))
        return out
    items = schema.get("items")
    if isinstance(items, dict):
        return out + leaf_paths(items, (*prefix, "[]"))
    if prefix:
        out.append(prefix)
    return out


def _walk(data: Any, path: tuple[str, ...]) -> Any:
    for step in path:
        if data is None:
            return None
        data = data[0] if step == "[]" else data.get(step)
    return data


def _mutate(data: Any, path: tuple[str, ...], action: Any) -> Any:
    """A copy of `data` with `action` applied at `path`. `action` of `None` deletes."""
    out = copy.deepcopy(data)
    node = out
    for step in path[:-1]:
        if node is None:
            return out
        node = node[0] if step == "[]" else node.get(step)
    if node is None:
        return out
    last = path[-1]
    if last == "[]":
        return out
    if action is _DELETE:
        node.pop(last, None)
    else:
        node[last] = action
    return out


class _Delete:
    pass


_DELETE = _Delete()


def corpus(schema: dict[str, Any], seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Seed payloads plus one mutation per field, to exercise every branch of the schema.

    For each leaf: delete it (does requiredness agree?), overrun its `maxLength` and
    underrun its `minLength` (do the constraints agree?), and put a value of the wrong
    type in it (does the type agree?). Enumerated fields also get a value outside the
    enum, which is what catches a code list that drifted.
    """
    payloads = list(seeds)
    for seed in seeds:
        for path in leaf_paths(schema):
            if _walk(seed, path) is None:
                continue
            payloads.append(_mutate(seed, path, _DELETE))
            payloads.append(_mutate(seed, path, "x" * 200))
            payloads.append(_mutate(seed, path, ""))
            payloads.append(_mutate(seed, path, 17))
            payloads.append(_mutate(seed, path, "not-a-listed-value"))
    return payloads


def verdicts(schema: dict[str, Any], payload: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (issue.field, issue.type, issue.message)
        for issue in validate_json_schema(payload, schema)
    }


def behavioural_differences(
    projected: dict[str, Any],
    golden: dict[str, Any],
    payloads: list[dict[str, Any]],
    allowed: dict[tuple[str, str], str] | None = None,
) -> list[str]:
    """Payloads on which the two schemas disagree, with the disagreement spelled out.

    `allowed` names `(field, issue type)` pairs where a difference in verdict is a decision
    rather than a defect, each with a reason. Keep it empty if you can: a difference here
    is a difference an applicant can see.
    """
    permitted = set(allowed or {})
    out: list[str] = []
    for index, payload in enumerate(payloads):
        ours, theirs = verdicts(projected, payload), verdicts(golden, payload)
        surprising = {
            issue
            for issue in ours ^ theirs
            if (issue[0].removeprefix("$."), issue[1]) not in permitted
        }
        if not surprising:
            continue
        out.append(
            f"payload {index}: only ours {sorted(ours - theirs)}; "
            f"only golden {sorted(theirs - ours)}"
        )
    return out
