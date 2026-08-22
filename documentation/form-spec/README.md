# Form spec: declarative question bank architecture

Specification for re-architecting Simpler Grants application forms as composable questions
drawn from a shared bank, where the reusable unit is a declarative schema fragment rather
than code.

| Document | Read it for |
|---|---|
| [`authoring-model.md`](./authoring-model.md) | **Start here.** Worked reference for the authoring model against real forms — what an author writes, what is emitted, what the build catches, and where it costs more than today. §11 covers canonical schema versus SGG's flat shape, §12 rules by example, §13 the block model. |
| [`architecture.md`](./architecture.md) | The specification: problem statement, design decisions, artifact contract, TypeSpec library, conditional logic, phased migration, verification. |
| [`../../form-spec/FINDINGS.md`](../../form-spec/FINDINGS.md) | Implementation findings: what the reference build validated, and the corrections it forced. |
| [`deferred-designs.md`](./deferred-designs.md) | Designs for the deferred layers — CommonGrants mappings, XML wire model, rule schema, routing — with the evidence and constraints behind each, so they can be resumed without re-deriving them. |

## Current scope

The dividing line is **intra-form versus cross-boundary logic.**

**In scope:** questions and forms as one recursive kind of *block*, each emitting its own JSON
Schema, UI schema, and catalogue entry; conditional logic and calculations; and the canonical →
SGG-legacy shape projection (required for anything to run inside SGG).

**Owned by the SGG adapter, not the library:** the canonical → legacy shape projection. A
projection is a property of the *(form, consumer)* pair — a second consumer of the same bank
wants a different reshaping of the same form — so holding projections in the library would scale
at forms × consumers. Target emitters and their opt-in vocabularies (`ui-schema-sgg`,
`rules-sgg`, `@Sgg.*`) only *add* per consumer, so those stay in the library.

**Deferred:** CommonGrants mappings, XML wire transform, and cross-form routing. XML passes
through byte-identical from frozen goldens; the package manifest records what is generated
versus passthrough.

**Scope:** 12–15 high-overlap forms, with the remaining 13 left untouched as a control group.
The three tables ship from the mining pass in Phase 1, marked provisional until each source form
is parity-proven.

## Summary

**The shipping architecture.** Reuse exists only at primitive granularity — `shared/` provides
real `$ref` reuse for `phone_number` and `person_name`, but nothing above it — so 13 of 28
forms contain zero `$ref` and the ISO country enum is inlined 12 times. The data model is the
XSD wire format leaked upward: SF-424 is 58 flat root properties with one entity distributed
across several under inconsistent naming. Conditional requiredness and conditional visibility
are expressed in two unrelated vocabularies with nothing relating them. Dependency order is a
hand-maintained integer. No question inventory exists, so the similarity, frequency, and
association tables are not derivable from any artifact.

**The in-flight component re-design.** `components/` is 2,830 lines of Python that *asserts* a
hand-built snapshot matches what a builder function would produce — deleting it changes no
shipped byte. There is no `$ref` composition (zero in `rr_sf424`'s 551 KB schema), and question
identity lives in 127 `x-authoring` annotations keyed by sha256 rather than in dereferenceable
schemas. The component index is keyed by form name (`Literal["key_contacts", …]`,
`organization-identity.sf424-profile`), so each additional form adds a variant instead of
reusing a question — inverting the stated objective.

**This specification.** Questions and forms become one recursive kind of *block*, each emitting
its own JSON Schema, UI schema, and catalogue entry, composed by `$ref` and authored through
typed TypeSpec decorators with diagnostics and linter rules. Question identity is the `$ref`
target, so the three tables fall out of a graph walk. Target-specific concerns — SGG's legacy
flat shape, its UI vocabulary, its rule names — are confined to separately deletable artifacts
and counted in CI.

It rests on one enabling property: `form_template_registry.py:61` already dereferences every
form's `$ref`s at registration through a pluggable URI loader. Publishing a `$ref`-composed
question bank is therefore a **registration change, not a runtime change** — the frontend,
validator, and XML generation continue to receive exactly the schema they receive today.
