# CommonGrants Key Contact compatibility canary

This package is a self-contained materialization of CommonGrants `KeyContact` at
revision `65a4de852c96d35e946e8dde9f7a9864f718d8bb`. It includes the complete pinned
TypeSpec/emitted-schema closure, content-addressed materializer inputs, exact question
bindings, composed mappings, and a deterministic Simpler UI projection.

It is intentionally a compatibility fixture, not a replacement for Simpler's current
Key Contacts form. CommonGrants currently models one primary contact; Simpler's legacy
form models one to four contacts, requires more fields per row, and emits Key Contacts
2.0 XML. `projection-report.json` preserves the exact translation dispositions.
