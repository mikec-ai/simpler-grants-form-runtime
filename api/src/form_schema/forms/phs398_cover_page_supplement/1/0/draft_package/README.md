# PHS 398 Cover Page Supplement draft package

This package projects the source-pinned Grants.gov 5.0 structure and the
resolved condition ledger into native Simpler JSON Schema, UI schema, rule
schema, attachment contracts, source-pinned XML transform, and field-level
analysis metadata.

The copied portable JSON Schema originally contained unqualified `Yes` and
`No` aliases in addition to the XSD values. This package deterministically
removes those aliases and retains only `Y: Yes` and `N: No`, exactly as pinned
by `GlobalLibrary-V2.0.xsd#YesNoDataType`. Runtime condition values are thereby
resolved to the actual wire values instead of creating invalid XML.

The six-section presentation order is pinned separately to the official
two-page PDF in `presentation-evidence.json`. That overlay changes grouping
and order only; the generated fields, conditions, attachments, and XML remain
source-resolved artifacts.

It is a draft implementation canary, not a production-readiness claim. The
semantic mappings and presentation review remain agent-proposed and
coverage-ineligible. Scalar-array authoring, cross-form Renewal applicability,
accessibility review, policy acceptance, and human acceptance remain explicit
gates.
