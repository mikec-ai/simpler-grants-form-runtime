"""The vendored artifacts must be exactly what the specification emitted.

Two halves to that guarantee, and only the first belongs here: this asserts the checked-in
files match their recorded digests, which catches a hand-edit. Whether the digests match
what the *current* specification emits needs the TypeSpec toolchain, so it is checked by
`.github/workflows/ci-form-spec.yml`, which re-emits and fails on any diff.
"""

import hashlib
import json

from src.form_schema.form_spec.bank import ARTIFACTS


def test_every_artifact_matches_its_digest():
    digests = json.loads((ARTIFACTS / "checksums.json").read_text())
    actual = {path: hashlib.sha256((ARTIFACTS / path).read_bytes()).hexdigest() for path in digests}
    assert actual == digests


def test_no_artifact_is_missing_from_the_manifest():
    recorded = set(json.loads((ARTIFACTS / "checksums.json").read_text()))
    present = {
        str(path.relative_to(ARTIFACTS))
        for path in ARTIFACTS.rglob("*.json")
        if path.name != "checksums.json"
    }
    assert present == recorded


def _reachable(schema: dict, pointer: str) -> bool:
    """Whether a UI pointer addresses something in this schema.

    A reference counts as reachable: the artifacts keep their `$ref`s, and what is behind one
    is resolved at registration. The point of the check is that the *names* agree.
    """
    node: dict | None = schema
    steps = [step for step in pointer.strip("/").split("/") if step]
    index = 0
    while index < len(steps):
        if node is None:
            return False
        if "$ref" in node:
            return True
        step = steps[index]
        if step == "properties":
            index += 1
            if index >= len(steps):
                return False
            node = (node.get("properties") or {}).get(steps[index])
        elif step == "items":
            node = node.get("items")
        else:
            return False
        index += 1
    return node is not None


def _pointers(ui_schema: object) -> list[str]:
    out: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        definition = node.get("definition")
        for pointer in definition if isinstance(definition, list) else [definition]:
            if isinstance(pointer, str):
                out.append(pointer)
        for child in node.get("children") or []:
            walk(child)

    walk(ui_schema)
    return out


def test_every_ui_pointer_addresses_the_schema_beside_it():
    """The artifacts have to agree about what a field is called.

    Everything the emitter writes uses the specification's own names, so a `definition`
    pointer can be checked against the `schema.json` in the same directory just by reading it.
    Spelling those names the way this codebase spells them is the projection's job, and it
    renames the schema, the pointers, and the rule keys from one map -- so this check failing
    means the emitter has grown a second opinion about naming.
    """
    forms = sorted((ARTIFACTS / "forms").iterdir())
    assert forms, "no vendored forms to check"
    for form in forms:
        schema = json.loads((form / "schema.json").read_text())
        ui_schema = json.loads((form / "sgg" / "ui-schema.json").read_text())
        pointers = _pointers(ui_schema)
        assert pointers, f"{form.name} renders no fields"
        unreachable = [p for p in pointers if not _reachable(schema, p)]
        assert unreachable == [], f"{form.name}: {unreachable}"
