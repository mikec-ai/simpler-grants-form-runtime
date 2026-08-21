# CommonGrants Key Contact compatibility canary

This package is a self-contained snapshot of CommonGrants `KeyContact`, produced by
local materializer revision `0fb92b128f7a492b0bf408f7226427e8c8cb04ba` based on HHS
revision `65a4de852c96d35e946e8dde9f7a9864f718d8bb`. It hashes the captured local
TypeSpec/emitted-schema inputs and materializer inputs, exact question bindings,
composed mappings, and deterministic Simpler UI projection. The manifest deliberately
labels the closure `partial_evidence` and compiler verification `manual_canary` because
external package closure and host-revision authentication are not yet proved.

It is intentionally a compatibility fixture, not a replacement for Simpler's current
Key Contacts form. CommonGrants currently models one primary contact; Simpler's legacy
form models one to four contacts, requires more fields per row, and emits Key Contacts
2.0 XML. `projection-report.json` preserves the exact translation dispositions.
