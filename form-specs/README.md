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

Every canonical question descriptor directly references one or more exact source records in the
manifest source catalog. Each record pins repository, full revision, repository-relative path,
SHA-256 digest, and source version. Loading fails when a question has no provenance, a reference is
dangling, or any source record is incomplete or has a malformed revision or digest.

The adapter resolves the referenced schema and compiles it through the same immutable
`ResolvedFormPackage` seam used by the native runtime. It does not construct a parallel native
`Form` path.

The pilot contains complete portable declarations for Key Contacts and SF-424. Key Contacts
binds 20 question occurrences, including its one-to-four repeated contact group. SF-424 binds
73 occurrences covering all 75 countable source paths, including role-distinct contacts,
conditions, a calculation, static content, and Grants.gov XML declarations. Nineteen of the 20
Key Contacts questions are reused by SF-424 through the same referenced question schemas; the
forms retain separate occurrence roles, cardinality, context, and source-wire mappings.

The portable declarations preserve two different verification boundaries. Runtime parity checks
compare generated Simpler artifacts with the existing native implementations. Source-accounting
checks compare the declarations with pinned XSD, behavior, and rendered-source evidence. A native
implementation can omit source fields, so passing the first check never silently implies passing
the second. All semantic mappings in this pilot remain agent-proposed, with zero reviewed mappings
contributing to published coverage.

The analytical projection reports three separate views. Proposed overlap is working evidence and
includes non-rejected occurrence bindings. Accepted overlap includes only occurrence bindings with
an `accepted` mapping status. Published overlap is additionally gated on each form's semantic
review state being `accepted` and its explicit published-coverage flag. The current 19 shared
questions and 95% Key Contacts coverage are therefore proposed findings; accepted and published
overlap are both zero.

TypeSpec and CommonGrants are optional compatibility inputs. Neither is required to author,
validate, analyze, or load this bundle.
