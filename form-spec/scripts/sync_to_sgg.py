#!/usr/bin/env python3
"""Vendor the emitted artifacts into the SGG adapter, with a hash manifest.

The adapter reads JSON from a directory it owns rather than reaching into a sibling build
tree, so the API has no build-time dependency on the specification project. This script
is the only thing that crosses that line, and it records a digest per file so a drifted
copy is a test failure rather than a surprise.

Usage (from the repo root):
    python3 form-spec/scripts/sync_to_sgg.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
DIST = REPO / "form-spec" / "dist"
TARGET = REPO / "api" / "src" / "form_schema" / "form_spec" / "artifacts"

#: Files the adapter consumes. The staging directory and the canonical UI artifact are
#: not among them: the former is an implementation detail of the emitter, and the latter
#: is for consumers that render JSON Forms.
KEEP = ("schema.json", "manifest.json", "index.json", "ui-schema.json", "rule-schema.json")


def main() -> int:
    if not DIST.is_dir():
        print(f"no emitted artifacts at {DIST}; run `npm run emit` first", file=sys.stderr)
        return 1

    if TARGET.exists():
        shutil.rmtree(TARGET)

    digests: dict[str, str] = {}
    for source in sorted(DIST.rglob("*.json")):
        relative = source.relative_to(DIST)
        if relative.parts[0].startswith("."):
            continue
        if source.name not in KEEP:
            continue
        destination = TARGET / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = source.read_bytes()
        destination.write_bytes(payload)
        digests[str(relative)] = hashlib.sha256(payload).hexdigest()

    (TARGET / "checksums.json").write_text(json.dumps(digests, indent=2, sort_keys=True) + "\n")
    print(f"vendored {len(digests)} artifacts into {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
