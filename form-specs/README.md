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

The first cost-curve stress test adds R&R Budget and R&R Budget 10 from one declarative profile.
Both resolve the same 101 applicant-input question references, five repeating structures, shared
UI declaration, and shared graph of 30 exact source-resolved sums. The runtime profile changes only
the budget-period limit from five to ten. Fifty-six computed outputs remain separate from applicant
questions; 26 source calculation records remain explicitly blocked rather than inferred.

This also resolves an earlier analytical discrepancy that counted 97 questions in one budget form
and 107 in the other despite identical 157-leaf structures. The portable declarations consistently
classify 101 applicant inputs and 56 computed outputs in each form. That classification is still
agent-proposed, so the budget pair's 100% working overlap contributes zero accepted or published
coverage. R&R Budget 10 behavior evidence is inherited from the five-year form and does not establish
target-form DAT parity. Grants.gov XML projection is not available in the pinned implementation
oracle and is not claimed.

The composition wave adds two less-trivial forms without adding form-specific runtime Python:

- R&R Subaward Budget 30 embeds the exact 101-question R&R Budget payload inside a bounded
  30-instance subaward collection. Its 30 file slots are classified as content-capture mechanisms,
  not semantic questions, so they remain visible in the association export without inflating
  question overlap.
- R&R Multi-Project Budget maps all 101 applicant inputs to the same proposed semantic identities.
  Eighty-seven reuse the exact budget schema; fourteen have source validation-profile differences.
  Two of those differences reuse an existing catalog schema and twelve emit explicit variants.
  Ten calculations are projected, while 46 calculations and 55 conditions remain preserved in
  evidence rather than inferred.

Question identity and validation schema identity are intentionally separate. A proposed question
may have more than one schema variant when form-specific constraints differ. Organization legal
name and five person-name parts now use the same proposed identities across SF-424, Key Contacts,
and the budget forms; roles and occurrence context remain attached to each form binding.

TypeSpec and CommonGrants are optional compatibility inputs. Neither is required to author,
validate, analyze, or load this bundle.
