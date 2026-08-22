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
    actual = {
        path: hashlib.sha256((ARTIFACTS / path).read_bytes()).hexdigest() for path in digests
    }
    assert actual == digests


def test_no_artifact_is_missing_from_the_manifest():
    recorded = set(json.loads((ARTIFACTS / "checksums.json").read_text()))
    present = {
        str(path.relative_to(ARTIFACTS))
        for path in ARTIFACTS.rglob("*.json")
        if path.name != "checksums.json"
    }
    assert present == recorded
