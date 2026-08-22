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


def _unordered(value: list[Any]) -> bool:
    return all(isinstance(item, str) for item in value)


def _brief(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 120 else text[:117] + "..."


def unexplained(differences: list[Difference], allowed: dict[str, str]) -> list[Difference]:
    """Differences with no entry in the allow-list.

    An allow-list key is a pointer suffix, so one entry covers a definition wherever it
    is reached from -- a bank question composed twice is one decision, not two.
    """
    return [
        difference
        for difference in differences
        if not any(difference.pointer.endswith(suffix) for suffix in allowed)
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
) -> list[str]:
    """Payloads on which the two schemas disagree, with the disagreement spelled out."""
    out: list[str] = []
    for index, payload in enumerate(payloads):
        ours, theirs = verdicts(projected, payload), verdicts(golden, payload)
        if ours == theirs:
            continue
        out.append(
            f"payload {index}: only ours {sorted(ours - theirs)}; "
            f"only golden {sorted(theirs - ours)}"
        )
    return out
