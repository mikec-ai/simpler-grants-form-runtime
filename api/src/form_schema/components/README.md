# Application components

Application components capture exact question-level structure and behavior that
is reused across otherwise different forms. Unlike form templates, a component
may contribute only part of a form and may span JSON Schema, UI, rule, and XML
artifacts.

Components are native resolved runtime definitions, not an independent semantic
authority. Each component contributes one or more atomic root fields through a
validated, immutable contract. A restricted mount can rename root keys and
mechanically rebase their UI pointers; nested mounts, array mounts, collisions,
and arbitrary path rewriting fail closed. Section placement, required-field
ordering, complex XML grouping, conditional behavior, and repeated containers
remain form-owned.

This boundary is compatible with a future canonical question source such as
CommonGrants: a build-time compiler can resolve canonical questions into these
component contributions or directly into a resolved form package. Simpler does
not need to import an external authoring system at runtime.

The first components cover organization name and SAM UEI. SF-424 and SF-424
Short compose both into an organization-identity profile while preserving their
exact descriptions and editable/read-only UI differences. Project Abstract
Summary mounts the same organization-name contribution as `applicant_name`,
proving that a form-specific field name and label need not duplicate its schema,
UI pointer, or direct XML mapping.

SF-424 and SF-424 Short also share an opportunity-identity component covering
agency name, Assistance Listing number/title, and funding opportunity
number/title. Its configuration is limited to the three observed title deltas
and the shared editable/read-only interaction; schemas, prepopulation rules, and
direct XML targets remain fixed by the component contract.

Optional source-question bindings are build provenance only. They do not assert
semantic equivalence or make a component eligible for published coverage.
