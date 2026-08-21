# PHS Fellowship Supplemental draft evidence package

This private-mirror package pins the output-neutral v8.0 schema snapshot and the
resolved runtime-rule AST used by the native Simpler canary. The builder verifies
the schema, runtime rules, and portable metadata before projecting 43 conditions,
two sums, and 17 attachment fields.

The portable manifest is projected into the versioned
`simpler-form-field-metadata/v1` schema extension. Every source record retains a
stable ID, runtime pointer where one exists, semantic mapping status, XML/XSD
identity, component context, behavior links, and an exclusive runtime
classification. Calculated outputs and attachments are not counted as applicant
questions.

The package is intentionally coverage-ineligible and not production-ready.
Semantic/runtime projection remains agent-proposed; XML, policy, accessibility,
and human acceptance are open gates. The scalar `CellLines` array is preserved in
JSON Schema but rendered read-only until Simpler has a reviewed primitive-string
list authoring control.
