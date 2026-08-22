# Portable form specifications

This directory is a dependency-neutral canary for reusable grants-form declarations.

The portable contract is referenced JSON Schema Draft 2020-12 plus JSON Forms UI schemas,
optional target-specific mapping sidecars, exact external source-evidence descriptors, and
review boundaries. The dependency-neutral loader and analytical projector live in
`api/src/form_schema/portable_form_kernel.py` and can be copied with this directory without a
Simpler checkout. Simpler consumes the verified kernel through the thin adapter in
`api/src/form_schema/portable_form_bundle.py`; the specifications do not import or execute
Simpler code.

Question identity and question occurrence are separate. A stable `question_id` represents the
reusable semantic question. Every use within a form has its own `binding_id`, role, form pointer,
cardinality, context, mapping references, and review state. Validation fails unless every bundled
question `$ref` occurrence is bound exactly once. This preserves repeated and role-distinct uses
without inflating the unique-question analysis.

The adapter resolves the referenced schema and compiles it through the same immutable
`ResolvedFormPackage` seam used by the native runtime. It does not construct a parallel native
`Form` path.

The first canary intentionally models only the applicant organization legal-name question in
two forms. It proves shared semantic identity and different source-wire bindings without
claiming either form is complete or that its agent-proposed mapping has been accepted.

TypeSpec and CommonGrants are optional compatibility inputs. Neither is required to author,
validate, analyze, or load this bundle.
