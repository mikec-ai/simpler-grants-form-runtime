# SF-424D source package

This package preserves the exact SF-424D 1.1 XSD closure and the deterministic
XML plan derived from it. `runtime-profile.json` binds the canonical XML paths
to the existing Simpler runtime field names. Those four bindings and two
legacy-only namespace declarations are reviewed against the retained Nava XML
tests; the XSD plan itself remains coverage-ineligible.

The original native JSON Schema, UI schema, and rule schema remain embedded as
the compatibility oracle in `form_json.py`. Shared component contributions must
compare equal to that oracle before the module can load. XML equivalence is
proved structurally and with offline XSD validation rather than by comparing
implementation dictionaries.
