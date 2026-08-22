# Deferred designs

Layers deliberately out of scope for the active plan
([`architecture.md`](./architecture.md)), preserved so they can be resumed without
re-deriving them. Each section records the design reached, the evidence behind it, and the
constraints discovered while working through real forms.

**One piece is *not* deferred:** the canonical → SGG-legacy shape projection
([`architecture.md` §2.5](./architecture.md)), because nothing we emit runs inside SGG
without it. It is the easy slice of the mapping layer — pure renaming and re-nesting,
bijective over leaf paths. Everything below is the hard part.

---

## 1. CommonGrants mappings

### 1.1 The core idea, which survives

Map to **models**, not to path strings:

```typespec
@Question.meta("primary-org/legal-name")
model QuestionOrgLegalName {
  @Map.to(CommonGrants.Organization.name)
  name: string;
}
```

Rename or remove `Organization.name` and **every question that mapped to it is a compile
error, at the mapping site.** Impossible today with `field: "organizations.primary.name"` as
a string. The emitter walks the reference to produce the dotted path, so the *artifact*
stays a portable path string while *authoring* is type-checked.

**Feasibility: verified** in `@typespec/compiler@1.13.0`.
`extern dec overload(target: Operation, overloadbase: Operation)` proves a non-target
parameter can be a reflection type receiving a type reference;
`invisible(target: ModelProperty, visibilityClass: Enum)` proves the same for `Enum`;
`MemberExpressionNode { selector: "." | "::" }` is part of both `Expression` and
`ReferenceExpression`, so `A.b.c` is legal in any decorator argument; and augment decorators
already pass `Model.prop` into `string | ModelProperty` parameters (`@@format`). The `::`
meta-member operator (`Model.prop::type`) exists for comparing types across a mapping.

### 1.2 Reversibility, made explicit rather than assumed

Not every transformation inverts, so the build refuses to guess:

- **Auto-invertible** when the two properties' types are structurally compatible (compared
  via `::type`). The emitter derives both directions from one declaration — which is what
  kills the drift risk in the current CommonGrants bank, where
  `primary-org/org-address.tsp` hand-writes `x-mapping-from-cg` *and* `x-mapping-to-cg` as
  manual inverses across 6 fields each with nothing enforcing that they invert.
- **Not auto-invertible** → hard error unless the author declares the inverse
  (`@Map.from`) or marks `@Map.oneWay("reason")`. Rule: `require-inverse-or-oneway`.
- **Type mismatch** (mapping a `string` onto an `int32`) is a diagnostic via `::type`.

The artifact records `"invertible": false` with the reason, so a consumer building a
submit-side transform knows immediately which fields it cannot round-trip.

### 1.3 Enum crosswalks get exhaustiveness checking

```typespec
@Map.valueMap(CommonGrants.ApplicantType, #{
  StateGovernment:  SggApplicantType.A_StateGovernment,
  CountyGovernment: SggApplicantType.B_CountyGovernment,
})
applicantTypeCode1: SggApplicantType;
```

- `valuemap-exhaustive` — every source member mapped, or an explicit default. Reports
  unmapped members by name.
- `valuemap-injective` — flags a non-bijective map and requires a declared reverse default.

Today a crosswalk is an unchecked dict written twice. Adding a value to the CG enum
currently produces silence; here it produces a build failure naming the gap.

### 1.4 The five problems Key Contacts surfaces

Key Contacts is the best available stress test, because its repeatable section breaks a
property-to-property decorator outright.

SGG form data is an **ordered array**:

```json
{ "key_contacts": [
    { "project_role": "Project Director", "name": {…}, "phone": "555-111-2222", … },
    { "project_role": "Fiscal Contact",   "name": {…}, "phone": "555-333-4444", … } ] }
```

CommonGrants models it as a **promoted singleton plus a keyed record**
(`lib/core/lib/core/models/proposal.tsp`):

```typespec
model ProposalContacts {
  primary: PersonBase;                    // required, singular
  otherContacts?: Record<PersonBase>;     // keyed, unordered
}
```

1. **Collection pivot.** Array → keyed object, key derived from a *member field's value*
   (`project_role`). Needs a collection-level construct with a key selector.
2. **Key transformation.** `"Project Director"` → `projectDirector`. A lossy transform on
   the key; two roles differing only in punctuation collide. Needs an explicit collision
   policy, not silent last-write-wins.
3. **Promoted singleton.** CG requires exactly one `primary`; SGG has a flat array with no
   primary flag. Which element gets promoted is a **policy decision**, not a mechanical
   mapping, and must be declared and reviewable.
4. **Cardinality mismatch inside the element.** SGG `phone`/`fax`/`email` are scalars; CG
   `PersonBase` has `phones`/`emails`/`addresses` as keyed *collections*. So
   `phone → phones.primary` is a scalar→keyed-collection adapter — the most common case
   across the whole bank, and probably deserving dedicated sugar.
5. **Genuine non-invertibility.** Reversing needs an ordering CG `Record` does not define,
   must flatten `primary` + `otherContacts` back into one array, and must reconstruct
   `"Project Director"` from `projectDirector`. Must fail the build unless declared.

### 1.5 A real ceiling on typed references

`otherContacts?: Record<PersonBase>` has **no declared members.** Neither do `phones`,
`emails`, `addresses`, or `customFields` — CommonGrants uses `Record<T>` pervasively.

So `@Map.to(PersonBase.phones.primary)` **cannot** be fully compile-checked: `primary` is a
dynamic record key, not a declared property. The honest resolution is a hybrid — reference
the `Record`-typed property (checked) and supply the key separately (validated at emit):

```typespec
@Map.into(PersonBase.phones, #{ key: "primary" })
phone: Generics.QuestionPhone;
```

Still far better than today's fully stringly
`field: "contacts.otherContacts.aor.name.firstName"`, because the model-bound half breaks
loudly when `PersonBase.phones` is renamed or retyped. But it is a real caveat against an
unqualified "everything is compile-checked" pitch.

### 1.6 Minimum construct set

| Construct | Purpose |
|---|---|
| `@Map.to(dest)` / `@Map.from(source)` | simple property-to-property |
| `@Map.each(dest, #{ key: <member prop>, onCollision: "error" })` | array → keyed record with a derived key |
| `@Map.keyFormat(KeyCase.camel)` | declared, testable key normalization |
| `@Map.promote(dest, #{ select: … })` | the CG `primary` singleton, explicit selection rule |
| `@Map.into(recordProp, #{ key: "primary" })` | scalar → keyed collection (the common case) |
| `@Map.valueMap(dest, table)` | enum crosswalk, exhaustiveness-checked |
| `@Map.oneWay("reason")` | forces §1.2 to be declared, not assumed |

**Sequencing conclusion.** Doing mappings *after* JSON Schema + UI is right. Key Contacts
proves the mapping layer is a harder design problem than the two layers being generated
now, and it deserves its own design pass rather than being bolted onto `@Map.to`.

---

## 2. XML wire transform

### 2.1 What `@typespec/xml` actually is

First-party and documented, but **metadata only** — five decorators (`@name`, `@attribute`,
`@ns`, `@nsDeclarations`, `@unwrapped`), consumed by other emitters such as OpenAPI3. There
is **no XSD or XML emitter**. It is also not currently in the protocol repo's dependency set
(only compiler, http, json-schema, openapi, openapi3, rest, versioning, asset-emitter), so
it is an addition.

So: adopt its decorators as the standard vocabulary for XML *shape*, and write our own
`xml-transform` emitter reading them off the real model graph.

### 2.2 The strong version: generate the wire model from the XSD

1. `scripts/import-xsd.ts` converts a grants.gov XSD into `specs/targets/wire/<form>.tsp` —
   a TypeSpec model of the wire shape with `@Xml.name` / `@Xml.ns` already applied.
2. Form properties map onto it with the same mechanism as §1:
   `@Map.to(Wire.RRSF424.AORInfo.Address.City)`.
3. **Refresh the XSD → regenerate → every affected mapping is an enumerated compile error.**
   Today the same upstream change silently mis-targets the string `target: "City"`.
4. The emitter derives `json_to_xml_schema` from the mapping graph plus `@Xml.*` metadata,
   replacing hand-written `{"xml_transform": {"target": "OrganizationName"}}`. Namespaces
   come from `@Xml.ns` instead of the string `"globLib"` repeated per field.

Because `@Map.to` is the same decorator family used for CommonGrants, the XML target model
is just another target — no separate XML mapping concept.

### 2.3 Caveats

- The XSD importer is the main cost. grants.gov leans heavily on GlobalLibrary cross-schema
  type reuse — good for us (shared types become shared TypeSpec models, reinforcing the
  bank) but the importer must resolve cross-schema references.
- `@Xml.*` covers shape, not value-level behavior. SGG encodes things it has no vocabulary
  for — `null_handling: "default_value"`, `default_value: "John"` in `person_name.py`.
  Those need our own decorators (`@Xml.defaultValue`, `@Xml.omitIfEmpty`).
- Sequence order matters in XSD and is a live hazard here — commit
  `43c5bb25 Preserve source-pinned XML sequence order`. The generated wire model carries
  declaration order, but it needs an explicit test.
- Until a form's XSD is imported it keeps hand-written transforms. Mixed state is expected.
- **Interaction with the projection.** While XML is passthrough, the transform operates on
  the *projected* legacy shape. A generated XML transform would instead operate on the
  canonical shape, which means adopting it retires that form's projection dependency for
  XML. Worth sequencing deliberately rather than half-migrating.

---

## 3. Rules: prepopulation, named validators, calculations

The dividing line is **intra-form versus cross-boundary logic**, not which artifact a rule
lands in. Conditional logic and calculations are properties of the form itself and are **in
scope** (`@Validation.requiredWhen`, `@UI.visibleWhen`, `@UI.readOnlyWhen`,
`@Validation.computed`). Prepopulation and named validators reach *outside* the form — to an
org profile, an opportunity, the clock, or SGG's attachment storage — and carry SGG's
assumptions with them. Those stay deferred:

### 3.1 Prepopulation is a mapping, not a rule (successor to the quarantined tier)

Prefill is authorable today via the `@Sgg.prePopulate` tier
([`architecture.md` §4.5](./architecture.md)), because passthrough cannot serve a *new* form.
This section describes what replaces it.

`@Sgg.prePopulate(SggPrePop.uei)` becomes `@Map.from(Sources.OrgProfile.samUei)`, moving from
the form — where it sits behind a lint boundary — to the question, where it semantically
belongs. All 8 names resolve to two source models, the opportunity (7) and the organization
profile (1), so the migration is mechanical and the CI census counts exactly how much remains.
Consequences when it lands:

- The closed six-name allowlist in
  `component_definition.py:_SUPPORTED_PREPOPULATION_RULES` disappears.
- Cross-form population — which `forms/README.md` notes grants.gov has and SGG does not
  support — becomes expressible as a mapping from a prior-application source model rather
  than a new rule type.

### 3.2 Named function registry (successor to the inferred tiers)

For `attachmentPresent`, `dateBefore`, and friends: a small **versioned registry**. SGG's
`gg_validation: {rule: "attachment"}` is already exactly this, and that instinct was right.
Portability comes from reimplementation per language against a **shared cross-language
conformance suite**, so the Python validator and the TypeScript renderer provably agree.

Note that the two largest rule groups are already handled without waiting for this: attachment
validation is **inferred from the property's type** and the `current_date` / `signature` stamps
are **inferred from question identity** (§4.5, Tiers 1–2). So the registry's arrival changes what
the emitter emits, not what any author writes — which is the cheapest possible successor.

### 3.3 Calculations — in scope, specified elsewhere

Not deferred. A calculation is intra-form logic — a pure function of other fields in the
same form — so it is portable and belongs in the canonical model. See
[`architecture.md` §4.4](./architecture.md).

The deciding evidence is SGG's own SF-424A, which carries a hand-maintained `"order": 2`
integer asserting a dependency between two sums. That is precisely what a reference graph
computes for free. 45 calculations exist across 4 forms (SF-424A 35, SF-424C 5, NEH 2,
SF-424 1), and their `fields` arrays are already spelled out in the goldens — so the standing
objection that auto-summation "can really only be found by figuring out the behavior from the
PDF" applies to *discovering* undocumented sums, not to the ones already recorded.

### 3.4 Expression languages: CEL, deliberately declined for runtime

CEL is the strongest general option — a formal spec, a Google-maintained Python
implementation (`cel-expr-python`, open-sourced March 2026, wrapping the official C++
runtime), and a community TypeScript implementation (`@gresb/cel-javascript`, ANTLR4-based).

Declined for runtime because form validity is evaluated in **both** Python (API) and
TypeScript (renderer), and two independent expression-language implementations deciding
whether a submission is valid is a correctness risk — plus the official Python binding adds
a native dependency. Keep CEL for authoring-time analysis and as an explicitly-marked
server-only escape hatch. Revisit only if the closed vocabulary plus the named-function
registry prove insufficient.

---

## 4. Routing

A **guarded-edge graph**, not a statechart:

```
nodes: forms (plus start / end)
edges: { from, to, when: <predicate over data collected so far>, priority }
```

Deliberately excluded: parallel states, entry/exit actions, side effects, history states.
Those are what make full statecharts (SCXML/XState) powerful and also unanalyzable. What we
keep is guarded transitions and determinism.

Static checks: every node reachable; no node whose guards can all be false (an `else` edge
is required); no cycles unless explicitly marked; deterministic ordering via `priority`.

**DMN decision tables** are the right tool for *eligibility determination* — a many-input →
outcome decision, a different job from routing. Add as a separate artifact type if
eligibility scoring appears (likely for the Navigator) rather than bending routing into it.

SGG has no cross-form routing today, so this layer has no SGG emitter and would be consumed
by our own preview tooling first. That makes it the layer where our implementation can be
visibly better than theirs without touching their code.

---

Sources: [TypeSpec XML library reference](https://typespec.io/docs/libraries/xml/reference/),
[FHIR Questionnaire](https://www.hl7.org/fhir/questionnaire.html), [CEL](https://cel.dev/),
[cel-expr-python announcement](https://opensource.googleblog.com/2026/03/announcing-cel-expr-python-the-common-expression-language-in-python-now-open-source.html),
[@gresb/cel-javascript](https://github.com/GRESB/cel-javascript),
[DMN decision tables](https://documentation.flowable.com/latest/model/dmn/example/part1-decision-table).
