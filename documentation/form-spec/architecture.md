# Form specification

Specification for re-architecting Simpler Grants application forms as composable collections
of **questions** drawn from a shared bank, where the reusable unit is a declarative schema
fragment rather than code.

The bank must be a semantic superset across all forms, must become cheaper to draw on with
each form added, and must be queryable enough to emit pairwise form similarity, per-question
form counts, and a form↔question association table.

Companion documents: [`authoring-model.md`](./authoring-model.md) is a worked reference
walkthrough of the authoring model against real forms;
[`deferred-designs.md`](./deferred-designs.md) specifies the layers held out of scope.

## Overview

The current fork consists of about 28 forms developed over roughly 40 Codex-generated commits. It demonstrates that the overall approach is viable, but also exposes a number of architectural limitations that become increasingly difficult to address as more forms are added. This specification addresses those limitations by defining a form architecture around a small set of design principles:

- **Forms are defined declaratively.** Form behavior should be expressed as data rather than application code.
- **Forms are composed recursively from reusable building blocks.** Questions and forms follow the same composition model, allowing reuse at any level of the hierarchy.
- **The canonical model is independent of any delivery target.** Target-specific concerns belong in adapters and projections rather than the canonical representation.
- **Correctness is enforced as early as possible.** Compile-time checks, build-time validation, and generated artifacts are preferred over conventions and runtime assertions.
- **Reuse should be measurable.** The architecture should make it possible to quantify question reuse, form similarity, and adoption across the catalog.

The target architecture follows the layer model from the Investment Navigator architecture document:

| Layer | Standard | Status here |
|---|---|---|
| **Question bank** | JSON Schema | **In scope** |
| **Form definitions** | JSON Schema + UI schema | **In scope** |
| **Conditional logic** | Declarative predicates | **In scope** where it lands in JSON Schema / UI schema |
| **Calculations** | Declarative predicates + refs | **In scope** — see §4.4 |
| **Prefill and named validators** | Declarative JSON | **In scope**, in an `@Sgg.*` namespace — §4.5 |
| Mappings (CommonGrants) | Declarative JSON | Deferred |
| XML wire transform | Declarative JSON | Deferred — passthrough, over the projected shape |
| Routing | Declarative JSON | Deferred |
| Legacy shape projection | Declarative JSON | **SGG adapter**, not the library — §2.5 |

This specification focuses on the JSON Schema and UI schema layers. They are where composition and reuse are defined, where the analysis artifacts are derived, and where the current implementation differs most from the target architecture.

The boundary between what is in scope and what is deferred is determined by whether the behavior is intrinsic to the form or depends on an external system. A calculation such as "total equals the sum of these fields" is part of the form's definition regardless of renderer or implementation language, so it belongs in scope (§4.4). Prefill *intent* is likewise intrinsic — "this field holds the applicant organization's SAM UEI" is a property of the question — so it is expressed canonically, while the rule name a particular system uses to satisfy it is adapter configuration (§4.5).

One design decision underpins the rest of this specification: the canonical schema does **not** mirror SGG's legacy flat structure. That structure exists to satisfy a legacy interchange format rather than to model the data itself, and adopting it as the canonical representation would preserve the same limitations this work is intended to remove. Instead, a **projection** (§2.5) maps the canonical model to the legacy representation at the system boundary. The projection is owned by the SGG adapter and lives in the SGG repository, because it encodes per-form knowledge of one target and nothing else needs it. That placement costs some build-time validation — projection paths are strings resolved by the adapter rather than typed references resolved by the compiler — and buys a library that carries no legacy naming at all.

The following constraints guide every design decision in this document:

1. **The canonical model never bends to a target.** Declarative artifacts must move across
   languages and renderers, so every target-shaped concern lives with its target — the legacy
   projection and the prefill rule table in the SGG adapter, the XML transform alongside them.
   The test is mechanical: point at any decorator and ask "does this exist because of SGG?" If
   yes, it does not belong in the library. Same split as `api/src/services/common_grants/`. This is the constraint that
   killed flat mounting (§2.5), and the count of target-shaped artifacts is a health metric —
   if target concerns start appearing in the canonical layer instead, the boundary is leaking.
2. **Inherit CommonGrants' mechanisms; never inherit its absence of checking.** Its UI tree
   composition and `rescopeUi` are right (§2.7), and `CatalogItem` is the shape the consuming
   site already assumes. What is missing is decorators, diagnostics, a linter, and build-time
   path validation — the list in §2.2. The distinction is load-bearing: its composition
   default is correct and must be preserved, while its validation posture must not be.
3. **Checks belong as high up the ladder as they will reach**: type system > `$onValidate` >
   linter > nothing at load or runtime. D4 is the exemplar — making sections an enum *deleted*
   a linter rule. Where the type system genuinely cannot reach (`Record<T>` keys, override
   paths), a build-time check is acceptable; a load-time or runtime check is not.
4. **The build targets are the contract, not TypeSpec.** A form builder must be a first-class
   peer later, so every check must be expressible against the *artifact graph* rather than the
   TypeSpec AST, and no consumer may depend on how artifacts were produced (§2.1, §5).
5. **Zero runtime change in SGG.** The approach rests on `$ref` resolution already happening
   at registration (§1.4). Nothing in the frontend, the validator, or XML generation changes.
   This is what makes the pitch viable rather than a rewrite.
6. **Parity is proven per form, not assumed.** Every migration asserts byte-equality against a
   frozen golden through an explicit projection, and the projection must itself be a bijection
   over leaf paths (§7).
7. **Reuse must be measurable.** New questions added per form, in CI. Without that number the
   central claim of the architecture is unfalsifiable.

---

## Part 0 — Design decisions

The following decisions establish the architectural direction for the remainder of this specification. They are intended to eliminate recurring design questions so later sections can focus on implementation details rather than revisiting foundational choices.

| # | Decision | Rationale |
|---|---|---|
| D1 | **Decorators are namespaced** — `@Question.*`, `@UI.*`, `@Validation.*`, later `@Map.*` | Follows existing TypeSpec conventions, groups related concerns together, and avoids collisions as the library grows. |
| D2 | **Conditional effects are separated by artifact** — `@UI.visibleWhen` / `@UI.readOnlyWhen` vs `@Validation.requiredWhen` | Visibility, interaction, and validation are distinct behaviors and should remain independently expressible. |
| D3 | **Overrides are defined as a form-scoped table** rather than augments | Allows overrides at any depth without duplicating intermediate models. |
| D4 | **Sections are represented as an enum** | Allows section references to be validated by the type system instead of by custom lint rules. |
| D5 | **The canonical schema uses `camelCase`; `snake_case` exists only in the adapter's projection** | Keeps the canonical model idiomatic. The projection carries a default `camelCase → snake_case` rule, so only irregular names need explicit entries — SF-424 needs roughly seven rather than fifty-eight. |
| D6 | **Generated JSON Schema contains no custom keywords** | Standard JSON Schema remains portable. Analysis metadata is stored separately rather than embedded into runtime artifacts. |
| D7 | **Reference enums are initially generated from Python into TypeSpec** | Reuses existing authoritative sources while preventing drift through CI validation. |
| D8 | **`fieldList` is inferred from array-of-object structures** | Common cases require no additional authoring; decorators remain available only where inference is insufficient. |
| D9 | **A *block* is the unit of composition.** A question and a form are both blocks, distinguished only by `@Question.meta` vs `@Form.meta`. A block is a Model when it holds several values and a **Scalar** when it holds one | Every block emits its own schema, UI, and catalogue entry, so a bank question renders standalone. Composition is uniform at every level (§2.7). Sections are the single grouping mechanism, usable at any level. |
| D10 | **SGG's remaining rule names are declared in an `@Sgg.*` namespace** | Lets the library emit a *complete* SGG rule schema in one pass, so the artifact has one producer and no merge. The surface is 8 names behind one decorator, restricted to `specs/forms/` by lint and counted in CI. Attachment validation and submit stamps need no authoring surface at all — both are inferred (§4.5). |
| D11 | **Decorators marshal their arguments to plain data; state holds no compiler entities** | `valueof` arguments arrive as graph nodes with parent back-references and cannot be serialized. Normalizing on write keeps the state map a plain-data contract for every emitter, linter rule, and the future form-builder validation API (§3.5). |

Field constraints don't require custom decorators: `@maxLength`, `@pattern`,
`@minValue`, `@minItems` and `?` are TypeSpec built-ins, so roughly half of what
`address_shared.py` hand-writes is provided by the standard library.

---

## Part 1 — Problem statement

Two distinct sets of defects motivate this specification: those in the form architecture
currently shipping, and those in the in-flight component re-design intended to replace it.
Every item below is a measurement against the repository, not an assessment.

### 1.1 Defects in the shipping form architecture

Located in `api/src/form_schema/`, excluding `components/`.

1. **Reuse exists only at primitive granularity.** `shared/` provides genuine `$ref` reuse
   through `SharedSchema.field_ref()`, but only for primitives — `phone_number`,
   `person_name`, `sam_uei`. There is no semantic question layer above it. Consequence: 13 of
   28 forms contain zero `$ref`, and the 200+ member ISO country enum is inlined **12 times
   across 7 files**.

2. **The data model is the XSD wire format leaked upward.** SF-424 is 58 flat root
   properties, and one semantic entity is distributed across several with no consistent rule:
   `authorized_representative` (a name object) plus `authorized_representative_title`,
   `_phone_number`, `_fax`, `_email`, plus `aor_signature` and `date_signed`. The contact
   person prefixes `contact_person_title` but leaves `email`, `fax`, and `phone_number` bare.

3. **One concept expressed in two unrelated vocabularies.** Conditional requiredness lives in
   JSON Schema `allOf`/`if`/`then`; conditional visibility lives in the UI schema's
   `ConditionalUi`. Nothing relates them, so a field can be conditionally required *and*
   permanently hidden with no mechanism able to detect it.

4. **The rule taxonomy conflates derived values with external lookups.** `sum_monetary` and
   `uei` both file under `gg_pre_population` — a computation over sibling fields and an
   external profile lookup share one key.

5. **Dependency order is hand-maintained.** `sf424a/1/0/form_json.py` carries
   `"order": 2` with the comment *"This rule needs to run after we calculate the
   total_direct_charge_amount above"* — an implicit dependency asserted by an integer.

6. **Hand-maintained allowlists drift.**
   `component_definition.py:_SUPPORTED_PREPOPULATION_RULES` enumerates 6 prepopulation rule
   names; forms in the repository use 8.

7. **Correctness depends on remembered conventions.** `forms/README.md` instructs authors that
   every attachment field must carry a validation rule, and that every `if` needs a
   `required: ["<source>"]` guard. Both are prose with no enforcement.

8. **No question inventory exists.** `grep -rl 'question_bank|similarity|inventory'` over
   `api/src` returns nothing. The pairwise-similarity, question-frequency, and form↔question
   tables are not derivable from any artifact in the repository.

### 1.2 Defects in the in-flight component re-design

Located in `api/src/form_schema/components/` (11 modules, 2,830 LOC) and the resolved-package
loading path.

1. **Components assert rather than generate.** `forms/rr_sf424/1/0/form_json.py` loads a
   hash-verified `draft_package/json-schema.json` (551 KB), then raises if a component's output
   does not byte-match what the snapshot already contained:

   ```python
   if composed_schema != schema_node:
       raise ValueError(f"R&R SF-424 person-name component drift: {ui_base_definition}")
   ...
   schema_node.clear()
   schema_node.update(composed_schema)
   ```

   Deleting every file under `components/` changes no shipped byte.
   `components/README.md` states the position directly: *"Components are native resolved
   runtime definitions, not an independent semantic authority."*

2. **No JSON Schema composition.**

   | Measure | Value |
   |---|---|
   | `$ref` count in `rr_sf424` json-schema.json (551 KB) | **0** |
   | `x-authoring` annotations in that same file | **127** |
   | Total JSON under `forms/` | **8.4 MB** |

   Composition happens in Python at import time through `mount_root()` / `mount()` /
   `mount_wire()`, string-rebasing `/properties/<key>` pointers.
   `component_definition.py:mount_root` forbids nested mounts, array mounts, and arbitrary path
   rewriting — a hand-rolled and strictly weaker re-implementation of what `$ref`, `$defs`, and
   `allOf` provide portably in every language.

3. **Question identity is a hash annotation, not a reference.** Every leaf of `rr_sf424`'s
   schema carries `x-authoring` with `node_id: "question:sha256:…"`, `modules`, `roles`,
   `semantic_candidates`, `source_path`, and `review_statuses`, plus four `x-authoring-*` keys
   at the root. This cannot be dereferenced, rendered, diffed, or imported. Two forms asking
   for "AOR city" are relatable only by comparing sha256 strings.

4. **The component index is keyed by form name, so reuse decays.**

   ```python
   ContactProfile = Literal["key_contacts", "global_contact_person_v3",
                            "sf424_short_contact_person_v3"]
   component_id = "application.organization-identity.sf424-profile"
   PersonNameXmlProfile = Literal["full_global", "first_last_global",
                                  "first_last_defaulted_global"]
   ```

   `person_name.mount_wire()` further requires a total, exact 5-part alias map and an exact
   `ui_order` tuple — parameters tuned to reproduce one form's bytes. Adding form N+1 adds a
   `Literal` member and a config field rather than reusing a question, so cost per form is
   flat-to-rising. The requirement is the opposite: cost per form falling as the bank grows.

5. **The nascent question bank is unreachable.** 26 question slots across 5 components exist at
   `forms/sf424/1/0/resolved_package/sources/harness/authoring-model/core/{questions,components}.json`
   — 2.4 KB total, hash-pinned as build evidence inside a single form's provenance directory,
   unreferenced by the runtime.

### 1.3 What is retained

Four existing elements are sound and this specification builds on them rather than replacing
them.

1. **`templates/form_definition.py`** — the 5-field `FormDefinition` dataclass. Becomes the
   adapter's output type unchanged.
2. **`resolved_form_package.py` (573 LOC) and `resolved_form_package.md`** — a source-neutral,
   hash-verified, fail-closed build-time boundary returning a plain `Form`. This is the adapter
   seam, and its documentation already commits to the authoring-agnostic rule Part 5 depends
   on: *"The loader does not import TypeSpec, call a remote service, or understand a specific
   authoring repository."*
3. **`shared/` and `SharedSchema.field_ref()`** — real `$ref` reuse. The question bank is the
   same mechanism at semantic rather than primitive granularity.
4. **`gg_validation: {rule: "attachment"}`** — a *named* rule drawn from a small registry
   rather than an arbitrary expression. That shape is correct and is preserved (§4.5).

### 1.4 Enabling property: the runtime already resolves `$ref`

`registry/form_template_registry.py:61` dereferences every form's schema at registration,
before any consumer sees it:

```python
form.form_json_schema = resolve_jsonschema(form.form_json_schema)
```

`jsonschema_resolver.py` resolves by URI through a pluggable loader keyed on
`{schema_uri: SharedSchema}`.

**Publishing the question bank is therefore a registration change, not a runtime change.**
Registering the bank's schemas in that URI map causes every `$ref` into it to resolve offline,
and the API, frontend renderer, validator, and XML generation continue to receive the same
fully-inlined schema they receive today. This property is what makes constraint 5 achievable
and is load-bearing for the entire approach.

### 1.5 Render target: a custom renderer, not RJSF

`@rjsf/core` is absent from `frontend/package.json`; only `@rjsf/utils` `^5.24.8` is a
dependency, used for types and enum helpers. The renderer is
`components/apply-form/FormFields.tsx` plus `widgets/WidgetRenderers` and
`utils/applyForm/*` — including its own `evaluateConditionalUi.ts`, `getFieldConfig.ts`, and
`validateUiSchema.ts`.

Its UI vocabulary (`frontend/src/types/applyForm/types.ts`) is the emitter target:

```ts
type UiSchema = UiSchemaNode[]                                  // flat, ordered
UiSchemaSection   { type:"section", name, label, children, description?, conditional? }
UiSchemaBasicField{ type:"field"|"null", definition:"/properties/…", widget?, name?, schema?, conditional? }
UiSchemaFieldList { type:"fieldList", name, label, definition?, children, conditional?, … }
UiSchemaMultiField{ type:"multiField", widget?, definition:PropertyPath[], … }  // incl. widget:"Table"
WidgetTypes = "Attachment"|"AttachmentArray"|"Checkbox"|"EncodedCheckboxGroup"|"Text"
            | "TextArea"|"Radio"|"Select"|"MultiSelect"|"Print"|"PrintAttachment"
            | "Budget424aSectionA".."F"|"FieldList"|"Table"
ConditionalUi { when: predicate, then: state, otherwise?: state }
  predicate op ∈ equals|notEquals|in|present|all|any|not, ref { scope:"root"|"item", pointer, ancestor? }
```

Two properties of this vocabulary matter downstream. Its `scope: "root"|"item"` plus `ancestor`
handling of repeats is adopted directly into the predicate design (§4.3). And
`jsonSchemaPointerToPath` (`applyFormUtils.ts:527`) is a generic pointer-to-path conversion, so
the renderer is **depth-agnostic** — which is what permits §2.5's canonical nesting.

### 1.6 Resolution mapping

| Defect | Mechanism | Specified in |
|---|---|---|
| 1.1.1 reuse at primitive granularity only | semantic question bank, `$ref`-composed | §2.4, §2.7 |
| 1.1.2 wire format leaked into the data model | canonical nested schema + per-form projection | §2.5 |
| 1.1.3 two vocabularies for one concept | one predicate vocabulary, effects split by artifact | §4.2 |
| 1.1.4 derived values conflated with lookups | calculations canonical; lookups declared in `@Sgg.*` | §4.4, §4.5 |
| 1.1.5 hand-maintained `"order"` | ordering derived from the reference graph | §4.4 |
| 1.1.6 drifting allowlists | generated closed enums | §4.5, D7 |
| 1.1.7 conventions requiring memory | inference and linter rules | §3.4, §4.5 |
| 1.1.8 no question inventory | `$ref` graph over blocks; tables in Phase 1 | §6, Phase 1 |
| 1.2.1 components assert rather than generate | declarative artifacts are the source of truth | §2.1 |
| 1.2.2 no JSON Schema composition | `$ref` composition preserved to the runtime | §2.4 |
| 1.2.3 identity as hash annotation | the `$ref` target *is* the question identity | §2.4, D6 |
| 1.2.4 index keyed by form name | question identity is `entity × attribute`, linter-enforced | §2.3, §3.4 |
| 1.2.5 unreachable nascent bank | bank registered with the resolver, `$ref`-able | §1.4, §6 |

---

## Part 2 — The artifact contract

### 2.1 Contract first, authoring second

```
                  ┌─────────────────────────┐
   TypeSpec ──────►│                         │
   (path 1, now)   │   ARTIFACT CONTRACT     │──► SGG adapter ──► Form ──► runtime
                   │   form-spec/contract/v1 │
   Form builder ──►│   • meta-schemas        │──► analysis (the 3 tables)
   (path 2, later) │   • conformance suite   │
                   │   • golden fixtures     │──► docs site / question browser
   Hand JSON ─────►│                         │
   (always legal)  └─────────────────────────┘
```

`form-spec/contract/v1/` holds a JSON Schema **meta-schema per build target**:

| Meta-schema | Status |
|---|---|
| `question.schema.json` | In scope |
| `form.schema.json` | In scope |
| `ui-schema.schema.json` | In scope |
| `form-package.schema.json` | In scope — extends `resolved-form-package/v1`, records generated vs passthrough |
| `rules.schema.json` | Deferred |
| `mapping.schema.json` | Deferred |
| `routing.schema.json` | Deferred |

Validated **twice**: by every emitter before `emitFile` (ajv, TS), and by the adapter on
load (Python, via the existing `jsonschema_validator.py`). Double validation is what makes
a non-TypeSpec authoring path safe to add later.

**Artifacts contain no TypeSpec concepts.** Where authoring uses a typed reference, the
emitter resolves it to plain data. Compile-time safety upstream, portable data downstream.

### 2.2 What not to inherit from the CommonGrants question bank

1. **The library has no compile-time surface at all.** `lib/core/src/lib.ts` is
   `createTypeSpecLibrary({ name: "@common-grants/core", diagnostics: {/* We'll add
   diagnostics later if needed */} })` — no decorators, no diagnostics, no linter.
   Everything form-related rides on `@extension("x-…", #{…})`, opaque to the compiler. A
   malformed UI schema compiles clean.
2. **UI `scope` strings are unvalidated.** A typo yields a silently dead control.
3. **Override paths are stringly-typed and need backticks.**
   `` `contact.name.firstName`: #{ label: "…" } `` — checked only at *load* time by
   `overrides.ts` strict mode, i.e. a website build error rather than a spec compile error.
4. **Entity questions re-declare the base's whole UI tree.**
   `QuestionPrimaryOrgAddress extends QuestionAddress` re-spells all 7 controls verbatim —
   violating the forms README's own rule: *"Override individual fields, do not redeclare
   the whole tree."* The bank breaks its own guidance because there is no mechanism to
   inherit-and-patch presentation.
5. **Form-level `x-overrides` becomes a flat label dumping ground.** `forms/sf424.tsp`
   carries ~30 label entries in one model-level block.

(The hand-written bidirectional mapping problem is also on this list, but belongs to the
deferred layer — see §8.)

Every one is a consequence of expressing presentation as data the compiler cannot see
into. Part 3 fixes that.

### 2.3 Question identity: the rule that fixes reuse decay

> **A question is named for what it means, never for the form it appeared in.** Form
> deltas — labels, help text, requiredness, read-only, widget, section placement — are
> *overrides on the form*. They never create a new question or variant.

Identity is `entity × attribute`: `poc/details`, `primary-org/legal-name`, `generics/address`.

| Today | Becomes |
|---|---|
| `ContactProfile = Literal["key_contacts", "global_contact_person_v3", "sf424_short_contact_person_v3"]` | one `poc/details` question + three per-form override sets |
| `component_id="application.organization-identity.sf424-profile"` | `primary-org/legal-name` + `primary-org/uei`, no profile |

Mechanically enforced by `no-form-scoped-question-id` (§3.4).

### 2.4 `$ref` survives to the runtime; nothing downstream changes

Emitted form schemas keep their `$ref`s — they are **not** dereferenced at emit time.
Registration inlines them exactly as today (§1.4). Consequences:

- **No custom `x-` keyword in the JSON Schema.** `x-authoring` and its 127-node smear are
  deleted. Because composites stay nested (§2.5), the `$ref` target *is* the question ID and
  a `$ref` scan recovers the three tables directly. If extra provenance is wanted, it belongs
  in the package `manifest.json`, never in the schema.
- **No frontend, validator, or XML change.** They see inlined schemas, as now.
- **Overrides are authoring-time only** — resolved by the emitter, never shipped.
- `x-simpler-form-package` provenance stays: runtime metadata, not semantics.

### 2.5 The canonical schema is well-formed; the legacy shape is the adapter's problem

SF-424's golden schema is **58 root properties** in which one semantic question is distributed
across several under inconsistent naming: `authorized_representative` (a `person_name` object)
plus `authorized_representative_title` / `_phone_number` / `_fax` / `_email`, plus
`aor_signature` and `date_signed`; while the contact person prefixes `contact_person_title`
but leaves `email`, `fax`, and `phone_number` bare.

That is the XSD wire format leaking into the data model, and it is not a shape to preserve.
Reproducing it in the authored schema would make the legacy shape the published artifact, and
every downstream consumer would inherit it — the failure mode constraint 1 exists to prevent.

So the canonical schema is semantically nested (`aor: { name, title, phone, fax, email,
signature, dateSigned }`), and reconciling it with the legacy shape is a **reshaping** step
that belongs to whoever needs the legacy shape.

**The form library does not know about the legacy shape.** It emits canonical artifacts only.
Reshaping is owned by the SGG adapter, in the SGG repository, alongside the golden fixtures and
parity tests that already live there:

```
api/src/form_schema/
├── legacy_projection.py                  # applies a projection to a schema and a UI schema
└── forms/<form>/1/0/
    ├── projection.json                   # per-form canonical leaf path -> legacy name
    ├── golden/                            # frozen parity oracle
    └── package/                           # vendored canonical artifacts from form-spec
```

```jsonc
// api/src/form_schema/forms/sf424/1/0/projection.json
{ "canonical": "question-bank/v1", "target": "sgg-legacy-flat",
  "defaultCasing": "snake_case",
  "map": { "aor.title":     "authorized_representative_title",
           "aor.signature": "aor_signature",
           "contact.email": "email" } }
```

Only irregular names need entries; the `defaultCasing` rule covers the rest, so SF-424 needs
roughly seven rather than fifty-eight.

**Where the boundary falls.** A projection is a property of the *(form, consumer)* pair, not of
the form. A second consumer of the same bank — another grants system, a different renderer, a
future CommonGrants-native service — wants a *different* reshaping of the same form, so holding
projections in the library would require the library to enumerate its consumers and store one
projection per consumer per form.

The general test is whether adding a second consumer **adds** to the library or **multiplies**
what it holds. A target emitter adds: the SGG UI vocabulary transform is one mechanical,
form-independent function, and a second target is a second function beside it. A projection
multiplies: forms × consumers. Additive concerns may live in the library; multiplicative ones
live with the consumer. This is also why the `@Sgg.*` rule vocabulary (§4.5) may stay in the
library while `projection.json` may not.

**The cost, accepted deliberately.** Projection paths are strings resolved by the adapter rather
than typed references resolved by the compiler, so a canonical rename surfaces as a failing
parity test in the SGG repository instead of a build error in the form library. That is a later
failure, not a missed one, and it buys three things: the form library becomes independently
publishable without carrying legacy naming, "delete the SGG target and the bank is untouched"
becomes true at the repository level rather than only the artifact level, and every future
consumer writes its own adapter rather than inheriting SGG's.

**What the reshape costs, and the answer to each:**

| Breaks | Answer |
|---|---|
| Byte-parity with the golden JSON Schema and UI schema | parity moves to the *projected* artifact (§7) |
| The passthrough XML transform, which maps from the flat shape | the same projection, applied before XML generation |
| Stored application answers, in the flat shape | SGG's existing form versioning — a reshaped form is a new **major** version |

The third needs no new machinery: `forms/<form>/<major>/<minor>/` and `sgg_version` already
exist, and `forms/README.md` documents that "the old version stays in place for any
competitions still pinned to it."

**Consequence — the deferred mapping layer is load-bearing, not garnish.** Without a
projection, no emitted artifact runs inside SGG. But the *first* mapping to build is not
CommonGrants; it is canonical → SGG-legacy, which is far simpler: pure renaming and
re-nesting, no enum crosswalks, no `Record<T>` keying, no promoted singletons, and trivially
invertible because it is a bijection over leaf paths. The hard mapping design (§8.1) stays
deferred while the easy, load-bearing slice comes forward.

Worked example: [`authoring-model.md` §11](./authoring-model.md#11-structure-the-canonical-schema-is-well-formed-sggs-flat-shape-is-a-projection).


### 2.6 UI structure is declared independently of data structure

Measured across every form with a UI-schema artifact: **max UI depth 1, zero nested
sections.** SGG's UI is deliberately a flat section list, and section 21 of SF-424 draws 12
fields from three different data depths into one flat section.

Both UI targets address fields by **absolute pointer** — SGG's `definition: "/properties/…"`
and JSON Forms' `Control.scope: "#/properties/…"` — so neither requires the UI tree to mirror
the data tree.

**The SGG emitter flattens the canonical UI tree** into sections, because SGG's vocabulary has
max depth 1. This is a target-specific projection, not a composition semantic (§2.7).
`@UI.section(...)` assigns a whole subtree's fields to one flat section regardless of depth;
per-field section assignment — needed where SF-424 splits one question across sections 8, 8e,
and 8f — is another key in the override table (§3.3). There is no separate grouping construct:
a section *is* a named group, usable at any block level.

**Sections are an enum (D4).** Declared once per form, in paper-form order, and referenced by
member — so `@UI.sections`, `@UI.section`, and any `section:` key in an override table stay in
sync *at the checker* rather than through a linter rule:

```typespec
enum Sf424Section {
  /** Enter the applicant's legal identity and address. */
  applicantInformation: "8. Applicant Information",
  organizationalUnit:   "8e. Organizational Unit",
  contactPerson:        "8f. Name and contact information of person to be contacted…",
  authorizedRepresentative: "21. Authorized Representative",
}

@UI.sections(Sf424Section)
model SF424 {
  @UI.section(Sf424Section.applicantInformation)
  organizationName: QuestionBank.PrimaryOrg.QuestionOrgName;
}
```

This mirrors the standard library's own visibility system —
`@invisible(target, visibilityClass: Enum)` takes an enum, `@visibility(target, ...valueof
EnumMember[])` takes members — and matches `@typespec/versioning`'s `enum Versions { v0_1:
"0.1.0", … }` with `@added(Versions.v0_2)`. Enum-member references inside object literals
already work in the current bank (`state: USState.CA`), so the override-table form
`#{ section: Sf424Section.organizationalUnit }` is checked too.

One member carries all three fields SGG's `UiSchemaSection` needs:

| Enum feature | SGG field |
|---|---|
| member name, snake_cased (`organizationalUnit`) | `name: "organizational_unit"` |
| member value | `label: "8e. Organizational Unit"` |
| doc comment | `description` |

Member declaration order gives section order, as it does for `Versions`. The `@UI.sections`
declaration is technically redundant — the enum is discoverable from usage — but stating it
pins the order and enables the `section-unused` check (§3.4).

Worked examples: [`authoring-model.md` §11](./authoring-model.md#11-structure-the-canonical-schema-is-well-formed-sggs-flat-shape-is-a-projection).

### 2.7 Blocks: the unit of composition (D9)

A **block** is a JSON Schema, a UI schema, and the conditional logic over them. Questions and
forms are both blocks; one decorator distinguishes them:

```typespec
@Question.meta(#{ id: "poc/details" })                    // the bank, $ref-able, question catalogue
@Form.meta(#{ id: "sf424", formId: "…", legacyFormId: 713, … })   // a deliverable form
```

Everything else — `@UI.*`, `@Validation.*`, `@Catalog.*`, and later `@Map.*` — applies
identically to both.

**Requirement.** A bank question must emit its own UI schema, because the CommonGrants browser
renders each question standalone — its loader already reads a `uiSchema` per question
(`website/src/lib/question-bank/loader.ts`). The consuming site also already defines a shared
`CatalogItem` abstraction — `{ id, name, description, tags, rawSchema }` in
`website/src/lib/catalog/types.ts` — covering question-bank *and* form items. The block model
specified here is the shape that site already assumes.

**Every block emits the same three artifacts.** Nothing target-shaped appears here:

```
dist/question-bank/v1/poc/details/
├── schema.json      # JSON Schema, $ref-ing generics
├── ui.json          # JSON Forms layout, scopes relative to THIS block's root
└── index.json       # catalogue facets: id, name, description, tags, entity

dist/forms/key-contacts/
├── schema.json      # same kind of artifact
├── ui.json          # same kind of artifact
├── index.json       # same kind of artifact
├── sgg/ui-schema.json   # mechanical vocabulary transform, no per-form knowledge (§2.5)
└── manifest.json
```

The first three are identical in kind at every level.

**Composition is UI-subtree incorporation.** A parent block's `ui.json` embeds each child
block's `ui.json`, re-scoped under the property name. This is `rescopeUi` in
`website/src/lib/forms/compose.ts` — already written, already correct, and central to the UI
emitter rather than incidental to it.

**Composition is a tree; flattening is a target concern.** The canonical UI composes as a
tree, because every block must render standalone. The SGG emitter then flattens that tree,
because SGG's UI vocabulary has max depth 1 and zero nested sections. Flattening is therefore
a target-specific projection and never a composition semantic — the same containment rule as
§2.5.

**What actually differs:**

| | Question | Form |
|---|---|---|
| identity | `@Question.meta` | `@Form.meta` |
| runtime metadata (UUID, `legacyFormId`, `ombNumber`, `formType`, version) | — | yes |
| `schema.json` / `ui.json` / `index.json` | yes | yes |
| `$ref`-able from another block | yes | yes |
| SGG target artifacts and adapter projection | — | yes |
| becomes a `Form` row in SGG | — | yes |
| catalogue | question bank | forms |

A form is a question with runtime metadata and a delivery target, which is why "forms are
configurable collections of questions" holds: a form embedding a question is the same
operation as a question embedding a question.

**Consequences.**

1. **A form can be `$ref`'d into another form.** This is how form *families* are expressed —
   SF-424 and SF-424 Short sharing a core, the four SF-424 assurance variants — and how
   multi-form flows compose.
2. **The association table is a transitive closure** over `$ref` edges, so "directly
   composes" and "ultimately contains" come from one graph, and similarity can be computed at
   either granularity.
3. **A single granularity throughout.** Blocks compose blocks at every level, so no separate
   notion of primitive versus composite is required in the artifacts or the analysis graph.

**Blocks are Models or Scalars.** A question holding several values is a Model
(`generics/address`, `poc/details`); a question holding one is a **Scalar**
(`generics/phone`, `generics/email`, `generics/organization-name`, `generics/contact-title`).
Roughly half the bank is single-valued, so this is the common case rather than an edge:

```typespec
/** Enter the legal name of the organization. */
@Question.meta(#{ id: "generics/organization-name" })
@Catalog.tag(TagName.organization, TagName.name)
@UI.label("Organization Name")
scalar OrganizationName extends string;
```

A scalar block emits a leaf `schema.json` rather than an object, and a single Control rather
than a Group. Every other rule applies unchanged, and a property composing one still emits a
`$ref` — which is what keeps `generics/phone` one shared definition across every form asking
for a phone number.

**Extending a block inside a form uses `extends`, never `is`.** A form frequently needs a bank
question plus a field or two of its own: Key Contacts needs `poc/details` plus `projectRole`
and `organizationalAffiliation`. `is` is the wrong tool, because it **copies the base's
decorators** — including `@Question.meta`. The extension silently claims the question's
identity, two blocks declare the same id, and their artifacts collide on one output path.

```typespec
// Identity stays with the bank question.
model KeyContactPerson extends QuestionBank.Poc.QuestionPocDetails {
  @UI.label("Project Role")
  projectRole: string;
}
```

`extends` also produces the right composition without further work: the derived model emits
`allOf: [{ $ref: <base> }]` plus its own properties. And because it carries no
`@Question.meta` it is not a published block, so the schema emitter inlines it into the
referencing form's `$defs` — exactly the shape the golden artifacts use
(`items: { $ref: "#/$defs/key_contact_person" }`).

**Two linter rules follow.** A block carries at most one of `@Question.meta` / `@Form.meta`; a
model with neither is a plain nested helper, inlined into its parent rather than published. And
no two blocks may declare the same id — `duplicate-block-id` — which is the rule that catches
the `is` mistake mechanically rather than by review.

---

## Part 3 — Authoring path 1: the TypeSpec library

A library with typed decorators, named diagnostics, linter rules, and one emitter per build
target — not a directory of `.tsp` files leaning on `@extension`.
`simpler-grants-protocol/lib/changelog-emitter` is a complete working precedent for the
scaffolding (`$onEmit`, `createTypeSpecLibrary`, `EmitContext`/`emitFile`, and `createTester`
from `@typespec/compiler/testing` driving vitest).

All APIs verified present in `@typespec/compiler@1.13.0`: `createTypeSpecLibrary` (with
`state` → `$lib.stateKeys`), `defineLinter`, `createRule` (alias of `createLinterRule`),
`defineCodeFix`, `paramMessage`, `$decorators`, and `TypeSpec.Reflection` (`Model`,
`ModelProperty`, `Enum`, `EnumMember`, …).

### 3.1 Layout

```
simpler-grants-form-runtime/
├── form-spec/                              # standalone pnpm workspace, own CI
│   ├── contract/v1/*.schema.json
│   ├── lib/typespec-form-spec/
│   │   ├── lib/{block,catalog,ui,validation}.tsp   # extern dec signatures + enums
│   │   ├── src/lib.ts                      # createTypeSpecLibrary: diagnostics + state keys
│   │   ├── src/decorators.ts               # implementations → program.stateMap
│   │   ├── src/linter.ts                   # defineLinter + rules + code fixes
│   │   ├── src/validate.ts                 # $onValidate: whole-program graph checks
│   │   ├── src/emitters/{block-schema,block-ui,block-index,ui-schema-sgg,package}.ts
│   │   ├── src/emitters/ui-schema/from-sgg.ts   # migration codec + round-trip test
│   │   ├── src/index.ts                    # $lib, $decorators, $linter, $onValidate, $onEmit
│   │   └── test/                           # createTester + vitest, per decorator and emitter
│   ├── specs/
│   │   ├── question-bank/{generics,primary-org,aor,pi,poc,fiscal-sponsor,project,budget,opportunity}/
│   │   └── forms/*.tsp
│   ├── scripts/{mine-questions,analyze}.ts
│   └── dist/                               # emitted, contract-validated, hash-stamped
│
└── api/src/form_schema/                    # the SGG adapter
    ├── question_bank/v1/**.json            # vendored from dist, hash-verified
    ├── question_bank/__init__.py           # registers bank URIs with the resolver
    ├── legacy_projection.py                # applies a projection to a schema and a UI schema
    └── forms/<form>/1/0/
        ├── package/                        # vendored canonical artifacts
        ├── projection.json                 # per-form canonical leaf path → legacy name
        └── golden/                         # frozen parity oracle
```

The fork has no root `package.json`, so `form-spec/` brings its own pnpm workspace and a
`ci-form-spec.yml` alongside the existing `.github/workflows/ci-*.yml`. Being self-contained
is what makes it liftable into its own repository — or upstreamed to
`simpler-grants-protocol` — without touching a consumer. Nothing under `form-spec/` names a
legacy field or an SGG rule.

### 3.2 Decorator surface

One namespace per concern, one `.tsp` file each (D1). This follows
`@typespec/json-schema/lib/main.tsp`: `namespace TypeSpec.JsonSchema;` then bare `extern dec`
declarations, consumed as `@JsonSchema.id(...)`.

```typespec
// lib/block.tsp — a block is a question or a form; these two decide which (D9)
namespace SimplerForms.Question;
extern dec meta(target: Model | Scalar, meta: valueof QuestionMeta);  // { id, version?, status? }

namespace SimplerForms.Form;
extern dec meta(target: Model, meta: valueof FormMeta);       // { id, formId, legacyFormId, … }

// lib/catalog.tsp — facets shared by questions and forms, mirroring CatalogItem
namespace SimplerForms.Catalog;
extern dec tag(target: Model | Scalar, ...tags: valueof TagName[]);
extern dec entity(target: Model | Scalar, entity: valueof EntityName);

// lib/ui.tsp
namespace SimplerForms.UI;
extern dec sections(target: Model, sections: Enum);                       // D4
extern dec section(target: ModelProperty, section: valueof EnumMember);
extern dec overrides(target: Model | ModelProperty, patch: valueof {});   // D3
extern dec label(target: Model | Scalar | ModelProperty, text: valueof string);
extern dec helpText(target: ModelProperty, text: valueof string);
extern dec widget(target: ModelProperty, widget: valueof WidgetName);
extern dec order(target: Model, ...props: ModelProperty[]);
extern dec omit(target: ModelProperty);
extern dec readOnly(target: ModelProperty);
extern dec visibleWhen(target: ModelProperty, source: ModelProperty, equals: valueof unknown);
extern dec visibleWhenIn(target: ModelProperty, source: ModelProperty, values: valueof unknown[]);
extern dec readOnlyWhen(target: ModelProperty, source: ModelProperty, equals: valueof unknown);

// lib/validation.tsp
namespace SimplerForms.Validation;
extern dec requiredWhen(target: ModelProperty, source: ModelProperty, equals: valueof unknown);
extern dec computed(target: ModelProperty, operator: valueof Op, ...refs: ModelProperty[]);
extern dec totals(target: ModelProperty, ...sources: ModelProperty[]);

// lib/sgg.tsp — the SGG target's own vocabulary. Expected to be retired (§4.5).
namespace SimplerForms.Sgg;
extern dec prePopulate(target: Model, rules: valueof Record<SggPrePop>);
extern dec multiField(target: Model, section: valueof EnumMember, widget: valueof WidgetName);
```

`@Validation.totals` says that a block totals the same block found in each of `sources` --
either a repeatable list, whose entries each contribute, or peer properties holding the same
block. One declaration stands for a sum per member, which is what makes a twelve-row budget
column one statement. SF-424A's thirty-five calculations come from eight declarations, and
their evaluation order is derived from how deep each calculation's dependencies go rather
than numbered by hand (§4.4).

`@Sgg.prePopulate` is a table on the form keyed by the path an answer takes, not a decorator
per property. Two reasons: a composed question's members live in the bank, where `@Sgg.*` may
not go, so there is nowhere to hang a per-property decorator; and everything the runtime
pre-fills then reads as one list, which is what a reviewer wants. Every path is checked
against the form (§3.4).

Registration is keyed by namespace string — the compiler's own doc example is
`$decorators = { "Azure.Core": {...} }`:

```ts
export const $decorators = {
  "SimplerForms.Question":   { meta: $questionMeta },
  "SimplerForms.Form":       { meta: $formMeta },
  "SimplerForms.Catalog":    { tag: $tag, entity: $entity },
  "SimplerForms.UI":         { sections: $sections, section: $section, label: $label, ... },
  "SimplerForms.Validation": { requiredWhen: $requiredWhen, computed: $computed, totals: $totals },
  "SimplerForms.Sgg":        { prePopulate: $prePopulate, multiField: $multiField },
}
```

`WidgetName` mirrors the frontend's `WidgetTypes` union, so an unsupported widget fails to
compile. `@UI.order` takes property references, so reordering cannot silently drop a field.
Requiredness comes from TypeSpec's own `?`, not a parallel `required: [...]` array. Field
constraints (`@maxLength`, `@pattern`, `@minValue`) come from the standard library.

See [`authoring-model.md`](./authoring-model.md) for these in use on real forms.

### 3.3 Overrides: a form-scoped table (D3)

```typespec
@UI.overrides(#{
  `title`:           #{ label: "AOR Title" },
  `address.state`:   #{ widget: WidgetName.Select },
  `address.street1`: #{ label: "8d. Street1" },
  `departmentName`:  #{ section: Sf424Section.organizationalUnit },
})
@UI.section(Sf424Section.authorizedRepresentative)
aor: QuestionBank.Aor.QuestionAorDetails;
```

One block, any depth. Paths resolve against the resolved model graph in `$onValidate`, so a
bad path is a build error naming the property. Patch values are typed: `WidgetName.Select`
and `Sf424Section.organizationalUnit` are enum members, checked by the checker.

This resembles the CommonGrants `x-overrides` block criticized in §2.2, and the difference is
worth stating: there, paths are checked at *website load* time and values are bare strings.
Here, paths are checked at build time against the model graph and values are enum members.

**Why not augments.** `@@UI.label(Clone.prop, …)` gives true compile-time target resolution
but cannot reach into a composed question. `Model.prop` yields a `ModelProperty`; reaching
inside needs `Model.prop::type`, and that type *is* the shared bank question, so augmenting
through it would mutate the bank for every form. Cloning the outer model does not help:

```typespec
model AorAddress extends Generics.QuestionAddress {}          // clone 1
@@UI.widget(AorAddress.state, WidgetName.Select);

model Sf424Aor extends QuestionBank.Aor.QuestionAorDetails {  // clone 2
  address: AorAddress;                                        // re-declare to use clone 1
}
```

Two extra models to reach one nested field. SF-424, with per-field labels like
`"8d. Street1"`, would require this constantly. Augments remain available for direct
properties of a form, where they read naturally; the table is the primary mechanism.

**Override keys are presentational only:** `label`, `helpText`, `widget`, `section`, `order`,
`omit`, `readOnly`. Legacy field names are *not* an override key — they are adapter
configuration and live in the SGG repository (§2.5).

### 3.4 Diagnostics and linter rules

**A TypeSpec linter rule may only be a warning.** `LinterRuleDefinition.severity` is typed
as the literal `"warning"`, so the severity of a check is not a free choice, and it decides
where the check lives:

* A check whose failure means the **emitted artifact is wrong** is a named diagnostic
  reported from `$onValidate`, at `severity: "error"`. It stops the emit.
* A check that describes a **specification worth tidying** is a linter rule, at warning
  level, enabled through the `recommended` rule set.

`src/lib.ts` declares the diagnostics and the state keys. Decorators write to
`program.stateMap($lib.stateKeys.…)` — typed state, not string blobs.

#### Errors, in `src/validate.ts`

| Diagnostic | Catches |
|---|---|
| `form-scoped-question-id` | `sf424-profile`, `key_contacts` in a bank id — §2.3 enforced mechanically |
| `duplicate-block-id` | two blocks claiming one id, so one output path takes both. The usual cause is `model X is Y`, which copies the base's decorators including its identity, where `extends` would not (§2.7) |
| `condition-value-not-in-enum` | a comparison against a value the source enum does not have, so the condition can never hold. Catches `"Outside the U.S."` against `"Outside the US"` |
| `calculation-cycle` | a calculated value that depends on itself, which has no evaluation order |
| `required-but-unreachable` | a field that is always required but only sometimes visible. **Impossible to detect in the shipping architecture**, where requiredness lives in the JSON Schema and visibility in the UI schema, in different languages |
| `section-orphan` | a field in no section, which renders nowhere. The classic form bug, and nothing detects it today |
| `override-path-unresolved` | an override path, or a widget declaration naming a section, that does not resolve in the composed model (§3.3) |
| `sgg-outside-forms` | an `@Sgg.*` decorator on a bank question, which would export one consumer's choices to every form composing it (§4.5) |

#### Warnings, in `src/linter.ts`

| Rule | Catches |
|---|---|
| `no-orphan-question` | a question nothing composes. Reachability, not property references: composing through a property, through `extends`, through a list, and through a model that is not itself a question all count |
| `require-question-docs` | a question with no doc comment, which is its description in the browser and on the form |
| `require-question-tags` | a question with no `@Catalog.tag`, so it appears under no heading |
| `section-unused` | a declared section no field references — usually a dropped field |
| `order-incomplete` | `@UI.order` omitting a property, with a `defineCodeFix` that appends it |
| `no-redeclared-property` | a derived block re-declaring a property it already inherits, which makes a second copy to keep in step by hand (§2.2 #4). TypeSpec permits this, so it needs a rule |

Every rule and diagnostic has a fixture that must fire and one that must not, in
`typespec-form-spec/test/`, driven by `createTester` and `createLinterRuleTester`. A check
that cannot fire reads as coverage and provides none.

#### Checks that are absent, and why

* **`section-unknown`** — D4 makes a section reference an enum member, so the checker
  rejects an unknown one before the linter runs. Moving a check into the type system is the
  preferred direction whenever it is available.
* **`unsupported-widget`** — same reason: `WidgetName` is an enum.
* **`attachment-needs-validation`** — `rules-sgg` derives the attachment rule from the
  question's identity, so a property composing `generics/attachment` always has it. There
  is nothing left to forget. Inference is a better answer than a rule.
* **`no-redeclared-ui`** as originally specified — the CommonGrants defect it described is
  re-spelling a base's whole *UI tree*, which cannot happen here because presentation is
  decorators rather than a data literal. What remains possible is re-declaring the
  *properties*, which `no-redeclared-property` covers.
* **Projection rules** — projection integrity is checked in the SGG repository, where the
  projection lives (§2.5, §7).

### 3.5 Decorators marshal; emitters never do

**Rule: a decorator implementation reduces every argument to plain JSON data before writing it
to state. State holds values, never compiler entities. No emitter and no linter rule calls
`serializeValueAsJson`.**

This is not a style preference. A `valueof` argument does not arrive as a JS value — it arrives
as a node in the compiler's graph. `@Form.meta(#{ id: "key-contacts", legacyFormId: 683 })`
hands the implementation an `ObjectValue` whose `.type` points at the `FormMeta` model, whose
namespace's model map points back at `FormMeta`. `JSON.stringify` on it throws
`Converting circular structure to JSON`. Enum members do the same by a different route:
`CountryCode.USA` arrives as an `EnumValue` wrapping an `EnumMember` whose `.enum` contains the
member again.

Three reasons the boundary is the decorator rather than the emitter, in increasing order of
weight:

1. **One producer, many consumers.** State is read by every emitter, every linter rule,
   `$onValidate`, and eventually the form builder's validation API (§5). Normalizing on write
   makes the state map a plain-data contract instead of something each reader must know how to
   unwrap — and unwrap identically.

2. **Name versus value must be decided where the type is known.** `WidgetName.Select` needs the
   member *name*, because SGG's widget strings are the member names. `CountryCode.USA` needs the
   member *value*, because that literal lands in the emitted schema. `SggPrePop.agencyName`
   needs the value. Choosing wrong produces a schema that compiles, validates, and silently
   never matches — the worst available failure mode. Three helpers keep the choice explicit:
   `plain()` for object literals, `enumName()` for names, `literal()` for values.

3. **It is how governing principle 2 is actually enforced.** That principle requires checks to
   be expressible against the artifact graph rather than the TypeSpec AST, so a second authoring
   path can reproduce them. If state holds compiler entities, every check is structurally
   coupled to the compiler and the principle is false in the implementation whatever this
   document says.

The conditional-logic decorators show the shape. Nothing downstream ever sees a `ModelProperty`:

```ts
function condition(source: ModelProperty, equals: unknown) {
  return {
    sourceName: source.name,
    sourceIsArray: source.type.kind === "Model" && !!source.type.indexer,  // decided once
    value: literal(equals),
  };
}
```

Resolving `sourceIsArray` here rather than in each emitter is what stops the JSON Schema
emitter (`contains` versus `const`) and the UI emitter from disagreeing about the same
condition.

### 3.6 Emitters

Each validates its output against the §2.1 meta-schema before `emitFile`:

| Emitter | Output |
|---|---|
| `block-schema` | one JSON Schema per block — question or form — `$ref`-linked, `$id` = published URI, plus `if`/`then` from conditional effects (D9) |
| `block-ui` | one canonical UI artifact per block (JSON Forms profile), scopes relative to that block's own root, children incorporated via `rescopeUi` |
| `block-index` | one catalogue entry per block, mirroring the website's `CatalogItem` — where D6's sidecar facets live |
| `ui-schema-sgg` | SGG `UiSchemaNode[]` — sections, `definition` pointers, widgets, `ConditionalUi`. A mechanical vocabulary transform with no per-form knowledge (§2.5) |
| `rules-sgg` | the **complete** SGG rule schema: calculations from `@Validation.computed`, attachment validation and submit stamps inferred, external lookups from `@Sgg.prePopulate`. One producer, so the adapter passes it through rather than merging into it (§4.5) |
| `package` | `resolved-form-package/v1` manifest, marking each artifact generated or passthrough |

Plus `ui-schema/from-sgg.ts` — a migration codec used to mine the existing UI schemas
(Phase 1) and to drive the round-trip test (§7).

Reuse from the protocol repository: `lib/forms/compose.ts`'s scope-rebasing logic
(`rescopeUi`) and `overrides.ts`'s strict-failure principle. Their override data model is not
carried forward; §3.3 replaces it.

---

## Part 4 — Conditional logic and calculations

### 4.1 Why the current split is the thing to fix

Conditional logic currently lives in three unrelated places with three vocabularies:

- **JSON Schema** `allOf`/`if`/`then` → conditional *requiredness*
- **UI schema** `ConditionalUi` → conditional *visibility and interaction*
- **Rule schema** → prepopulation, named validators, and auto-summation that
  `forms/README.md` says is *"only found by figuring out the behavior from the PDF"*

So "required when X" and "visible when X" are expressed twice, in different languages, with
nothing relating them. A field can be conditionally required *and* permanently hidden, and
nothing detects it.

### 4.2 One vocabulary, effects separated by destination artifact

Borrowing the XForms Model Item Property decomposition — one predicate vocabulary, distinct
effects:

| Effect | XForms name | Emits to | Status |
|---|---|---|---|
| `visible` | relevant | JSON Forms `rule` SHOW/HIDE; SGG `conditional.visible` | **In scope** |
| `required` | required | JSON Schema `if/then/required` + UI | **In scope** |
| `readOnly` | readonly | SGG `conditional.interaction: readOnly` | **In scope** |
| `value` | calculate | rule schema (calculation entries) | **In scope** — §4.4 |
| `valid` | constraint | rule schema | Deferred |

Predicate vocabulary: refs are **property references** (compile-checked); ops
`eq, ne, in, nin, exists, empty, gt, gte, lt, lte, matches, all, any, not`. Scope follows
SGG's prior art for repeats — `root | item` with an `ancestor` depth, so a predicate inside a
`fieldList` row can reference its own row or walk up.

Declared with the namespace carrying the destination artifact (D2):

```typespec
@UI.visibleWhen(QuestionAddress.country, CountryCode.OutsideTheUS)
province?: string;                 // -> UI conditional / JSON Forms rule

@Validation.requiredWhen(SF424.applicationType, ApplicationType.Revision)
revisionType?: RevisionType;       // -> JSON Schema if/then
```

Two emitter rules follow from the golden artifacts:

- **Never infer visibility from requiredness.** This is why the two sit in different
  namespaces. SF-424 has six conditional `if`/`then` blocks in its JSON Schema and **zero
  `conditional` blocks in its UI schema** — `revision_type` is always visible, only its
  requiredness changes. Conflating the two would render a form that looks correct and behaves
  differently from grants.gov, and no parity test on the JSON Schema alone would catch it.
- **Derive the JSON Schema keyword from the property's type.** An array source emits
  `contains`, a scalar emits `const`. Plus the `required: ["<source>"]` guard inside every
  `if`, which `forms/README.md` currently has to teach authors to remember.

**Precedent.** FHIR Questionnaire independently converged on the same shape: a deliberately
simple structured `enableWhen` (`{question, operator ∈ exists|=|!=|>|<|>=|<=, answer[x]}` with
`enableBehavior: all|any`) plus a documented escalation path — *"If different behavior is
desired (all must match, at least 2 must match, etc.), consider using the
enableWhenExpression extension."* It also separates hiding from disabling via
`disabledDisplay: hidden|protected`, exactly the `visible` versus `readOnly` split above.

Worked examples of every rule kind against the real SF-424 rule schema:
[`authoring-model.md` §12](./authoring-model.md#12-rules-by-example).

### 4.3 Analyzability is the point

A closed vocabulary provides what an expression string cannot:

- a **static dependency graph**, and therefore cycle detection
- **dead-rule detection** — catches `"Outside the U.S."` versus `"Outside the US"`, which
  today produces a permanently dead rule no test notices
- **required-but-never-visible detection** — impossible today
- **multi-target emission** — one source emits JSON Forms `rule`, SGG `ConditionalUi`, *and*
  JSON Schema `if/then`, guaranteed consistent

The emitter also encodes house idioms once rather than per author — for example the
`required: ["country"]` guard inside every `if`.

Expression-language escape hatches (named function registries, CEL) belong to the deferred
rules layer; see §8.3.

### 4.4 Calculations, with derived ordering

A calculation is intra-form logic — a pure function of other fields in the same form — so it
is portable and belongs in the canonical model. The deciding evidence is what SGG does today,
in `sf424a/1/0/form_json.py`:

```python
"total_amount": {
  "gg_pre_population": {
    "rule": "sum_monetary",
    "fields": ["@THIS.total_direct_charge_amount", "@THIS.total_indirect_charge_amount"],
    # This rule needs to run after we calculate the total_direct_charge_amount above
    "order": 2,
  }
}
```

That `"order": 2` is a hand-maintained integer asserting a dependency the system already
describes implicitly — precisely what a dependency graph computes, and precisely what breaks
silently when a third level is added. Authored instead as:

```typespec
@UI.readOnly
@Validation.computed(Op.Sum, #[
  SF424A.budgetCategories.totalDirectChargeAmount,
  SF424A.budgetCategories.totalIndirectChargeAmount,
])
totalAmount?: MonetaryAmount;
```

**Ordering is derived from the reference graph, never authored.** The emitted `order` becomes
a computed output, and cycle detection (§4.3) gains its first real consumer.

**Scale and shape.** A full census of `gg_pre_population` finds **63 calculation entries** —
`sum_monetary` 44, `subtract_monetary` 18, `multiply_by_percentage` 1 — concentrated in the
budget forms, with SF-424A alone holding 35 of the sums. A handful are single-level sums; the
bulk is SF-424A's two-dimensional spreadsheet, with row totals across columns, column totals
down rows, and grand totals over other totals. Two reference forms are therefore mandatory,
both already present in SGG's vocabulary and in §4.2's predicate design:

| SGG spelling | Meaning | Ref form |
|---|---|---|
| `@THIS.personnel_amount` | sibling within the same array item | `scope: item`, `ancestor: 0` |
| `activity_line_items[*].budget_summary.federal_new_or_revised_amount` | aggregate down every array element | array projection |

**Operations.** The engine supports `sum_monetary`, `subtract_monetary`, and
`multiply_by_percentage`, so `Op` needs `Sum`, `Subtract`, and `PercentOf`.

**Why this is affordable.** The standing objection is that `forms/README.md` says
auto-summation *"can really only be found by figuring out the behavior from the PDF."* That
applies to *discovering* undocumented sums, not to the 63 already recorded in the goldens with
their `fields` arrays spelled out. For migrated forms the inputs exist, so calculations are
mined exactly like questions. And because SGG's rule engine already executes these rules,
generating the entries is sufficient — constraint 5 holds.

**Sequencing.** Land `computed` on the single-level sums first (SF-424, SF-424C, NEH), and
treat SF-424A as the stress test validating item-relative refs, array projections, and derived
ordering together. This matches the budget family going last in Phase 2.

### 4.5 SGG's remaining rule names

Passthrough alone is insufficient because of the third objective — configuring *new* forms from
the bank. **A new form has no golden to pass through.** Any new form with an attachment needs
the attachment validation rule, and any new SF-424-like form needs the opportunity fields
prefilled. These behaviors must be authorable.

A census of every rule in every form:

| Group | Entries | Distinct names | Disposition |
|---|---|---|---|
| `gg_pre_population` — calculations | 63 | 3 | `@Validation.computed` (§4.4) |
| `gg_pre_population` — external lookups | ~15 | **8** | `@Sgg.prePopulate`, Tier 3 |
| `gg_post_population` | ~26 | **2** (`current_date`, `signature`) | inferred, Tier 2 |
| `gg_validation` | ~34 | **1** (`attachment`) | inferred, Tier 1 |

The non-calculation surface is 11 distinct rule names, and only 8 require any authoring
surface. The `rules-sgg` emitter (§3.6) produces all four groups in one pass, so the rule
schema has a single producer and the adapter passes it through without merging.

**Tier 1 — inferred from the property's type.** `gg_validation: {rule: "attachment"}` is emitted
for every attachment-typed property (~34 entries, 1 rule name). What `forms/README.md` teaches
as a convention authors must remember becomes an emitter behavior they cannot omit.

**Tier 2 — inferred from question identity.** `current_date` and `signature` (~26 entries, 2
rule names). Both already exist as shared schema fields (`common_shared.py` defines `signature`
and `submitted_date`), so they become bank questions and the emitter infers the stamp from which
question a property uses. No decorator.

**Tier 3 — declared.** Only external lookups. All 8 resolve to two sources — the opportunity
(`agency_name`, `opportunity_number`, `opportunity_title`, `assistance_listing_number`,
`assistance_listing_program_title`, `public_competition_id`, `competition_title`) and the
organization profile (`uei`):

```typespec
// lib/sgg.tsp
namespace SimplerForms.Sgg;
extern dec prePopulate(target: Model, rules: valueof Record<SggPrePop>);
```

```typespec
@Sgg.prePopulate(#{
  `agencyName`: SggPrePop.agencyName,   // successor: @Map.from(Sources.Opportunity.agencyName)
  `samUei`: SggPrePop.uei,              // successor: @Map.from(Sources.OrgProfile.samUei)
})
model SF424 { ... }
```

Seven properties make this retirable rather than merely separate:

1. **Its own namespace.** `@Sgg.*` — the namespace is the label. Not `@Validation.*`, not
   `@Question.*`.
2. **Its own artifact.** Contributes only to `sgg/rule-schema.json`, never to `schema.json` or
   `ui.json`, so removing it cannot change the canonical model.
3. **A closed, generated enum.** `SggPrePop` is derived from the engine's rule list, so the
   surface is bounded and countable. The hand-maintained allowlist in
   `component_definition.py:_SUPPORTED_PREPOPULATION_RULES` covers only 6 of the 8 names forms
   actually use — the drift a generated enum prevents.
4. **Forms only, never questions.** Linter rule `no-sgg-in-bank` permits `@Sgg.*` in
   `specs/forms/` and nowhere else. This is the load-bearing rule: a bank question carrying
   `@Sgg.prePopulate` would push the target assumption into every form composing that question.
5. **A declared successor.** Each enum member's doc comment names its replacement, so migration
   is mechanical and the documentation cannot drift from the code.
6. **A CI census.** The count of `@Sgg.*` call sites is printed each build beside the reuse
   curve, and is expected to trend to zero.
7. **Separately versioned.** `sgg-legacy/v1` is its own contract version, so retiring the tier
   is a version bump rather than a schema change.

**Why this vocabulary may live in the library while the projection may not (§2.5).** Adding a
second consumer *adds* an emitter and optionally a namespace — the SGG target's surface is one
`lib/sgg.tsp` and one emitter, and a form opts in by using the decorator. Adding a second
consumer *multiplies* projections, because each consumer wants a different reshaping of the same
form, and the library would have to enumerate consumers to hold them. Additive belongs in the
library; multiplicative belongs with the consumer.

**One acknowledged compromise.** Prepopulation is *semantically* a property of the question —
`primary-org/uei` always holds the organization's SAM UEI — so the eventual `@Map.from(...)` will
live on the question rather than the form. Declaring `@Sgg.prePopulate` on the form is therefore
deliberately the less natural placement: it keeps the bank target-neutral until the
semantically-correct form can live in the right place. The assumption is contained rather than
distributed.

---

## Part 5 — Authoring path 2: the interactive form builder

Not built now, but the contract is designed so it slots in without renegotiation:

1. **Both paths emit contract-conformant artifacts**, validated by the same meta-schemas in
   the same CI job. Neither path is privileged.
2. **One shared conformance suite.** Golden fixtures and parity tests (§7) belong to the
   contract, not to the TypeSpec library.
3. **Round-trip identity for the builder.** `artifacts → builder model → artifacts` must be
   the identity function, which is why the canonical UI format must be fully serializable
   (JSON Forms) rather than renderer-specific.
4. **No consumer references TypeSpec.** The Python adapter already commits to this in
   `resolved_form_package.md`. TypeSpec appears nowhere in `api/`, the frontend, or the
   analysis scripts.

Explicit non-goal: the builder must **not** generate TypeSpec source. Codegen into an
authoring language is brittle and would make the contract subordinate to TypeSpec.

**Where the build-time checks go in a builder world.** The §3.4 and §4.3 checks are
authoring-time, not TypeSpec-specific. Each is implemented as a function over the *artifact
graph* and exposed two ways: as a TypeSpec diagnostic (path 1) and as a validation API the
builder calls on save (path 2). Same rule, same message, two front ends — which keeps the
guarantee true for non-technical authors, and is the reason to write checks against the
emitted graph rather than the TypeSpec AST wherever possible.

Practical consequence now: the bank browser and the three tables read `dist/`, never `.tsp`.
They become the builder's read model.

---

## Part 6 — Implementation phases

### Phase 0 — Contract, library, spikes, one form end to end

1. Scaffold `form-spec/` (pnpm workspace, `ci-form-spec.yml`), copying the
   `lib/changelog-emitter` package shape.
2. Write `contract/v1/*.schema.json` (§2.1) and the ajv validator every emitter calls.
3. **Run three spikes before building on them.** Each has a named fallback, so a negative
   result costs ergonomics rather than the architecture:
   - Augment isolation across a derived model (§3.3). *Fallback:* `@override` taking a property
     reference.
   - `ModelProperty` as a **non-target** decorator parameter receiving `A.b.c`, needed by
     `@Validation.requiredWhen`, `@Validation.computed`, and `@UI.order`. Verified possible in
     principle — `extern dec overload(target: Operation, overloadbase: Operation)` proves
     reflection types work as non-target parameters, and augment decorators already pass
     `Model.prop` into `string | ModelProperty` parameters (`@@format`). *Fallback:*
     `valueof string` paths resolved in `$onValidate`.
   - Whether `@UI.order` accepts property references inherited via `is`.
4. Implement the decorator surface (§3.2), diagnostics and state keys, `$onValidate` graph
   checks, and the linter rules — each with a `createTester` test asserting the diagnostic
   fires.
5. Implement the `block-schema`, `block-ui`, `block-index`, `ui-schema-sgg`, `rules-sgg`, and
   `package` emitters.
6. Register bank URIs with `jsonschema_resolver._loader` via a new
   `api/src/form_schema/question_bank/__init__.py`, mirroring
   `shared/__init__.py:get_shared_schemas`. `shared/` keeps working; the bank sits above it and
   may `$ref` into it.
7. Build the adapter side: `legacy_projection.py` and the per-form `projection.json` format
   (§2.5). Key Contacts' projection is close to the identity function
   — its golden already nests `name` and `address` — so the machinery starts minimal and grows
   when SF-424 lands.
8. Extend `resolved_form_package.py` with the `question_bank` artifact set, `$ref`-target
   validation, and contract validation on load. Extend `test_resolved_form_package.py`.
9. Migrate **`key_contacts`** as the canary — see [`authoring-model.md`](./authoring-model.md)
   for the full worked example.

**Done when:** `resolve_jsonschema(projected) == golden` for `key_contacts`, byte-exact, for
JSON Schema and UI schema, with XML passing through and every emitter output contract-valid.

### Phase 1 — Mine the bank from the golden artifacts

Forms are not re-derived from `.dat`/`.xsd`/PDF. The parity work exists; it is mined.

1. `git mv` each form's current artifacts to `forms/<form>/1/0/golden/` and freeze. For forms
   with no package, emit their in-Python `FORM_JSON_SCHEMA` to `golden/json-schema.json` once.
2. `scripts/mine-questions.ts`: group leaves across all golden schemas by normalized shape and
   semantic path, seeded by the existing `x-authoring.modules`/`roles` and the 26-slot
   `authoring-model/core/{questions,components}.json`. Emit a proposed bank plus a per-form
   question↔property map for review.
3. Land the bank as TypeSpec under `specs/question-bank/`, seeded from the protocol
   repository's ~45 questions re-expressed through decorators, so the vocabularies agree
   semantically without inheriting the `@extension` style.
4. Generate the ~200-member country and ~60-member state enums into
   `specs/question-bank/generics/codes.tsp` from `shared_form_constants.py`, with a CI drift
   check.
5. **Emit the three tables from the mining output, marked provisional.** No form needs to be
   migrated first — the mining pass already produces everything `analyze.ts` requires. Each row
   carries `status: "provisional"` until the form it came from is parity-proven, then flips to
   `"proven"`.

   Producing the tables here rather than after migration inverts the risk profile: the primary
   deliverable exists early, and migration becomes what *validates* it rather than what
   produces it. The provisional/proven split keeps that sound — a figure no parity check has
   confirmed is never presented as though it were.
6. Mine the 63 existing calculations the same way (§4.4); their `fields` arrays are already
   spelled out in the goldens.
7. Derive each form's `projection.json` by matching canonical leaf paths against golden leaf
   paths on type, order, and XML target, leaving a human to review (§2.5).

### Phase 2 — Migrate 12–15 forms, one PR each, in overlap order

Scoped to the slice that maximises question overlap and stresses the hard cases. The brief
called for 10–20 forms; extending to all 28 is a separate decision once the reuse curve is
visible.

```
key-contacts → epa-key-contacts → sf424 → sf424-short → rr-sf424
→ sflll → cd511 → epa-4700-4 → sf424b/c/d
→ narrative attachments (×3) → sf424a (the calculation stress test, last)
```

**Left as an untouched control group** (13 forms): the rest of the budget family
(`rr-budget`, `rr-budget10`, `rr-mp-budget`, `rr-mp-subaward-budget`,
`rr-subaward-budget30`, `rr-subaward-budget10-30`), `phs-fellowship-supplemental`,
`supplementary-neh-cover-sheet`, `project-abstract`, `project-abstract-summary`,
`project-performance-site-location`, `attachment-form`, `gg-lobbying-form`.

Keeping them untouched is useful rather than merely cheaper: they remain on the current
architecture as a side-by-side comparison, and each one migrated later is a fresh test of
whether the bank has made form N+1 cheaper.

Per form: author `specs/forms/<form>.tsp` composing bank questions plus an override table →
emit → vendor to `forms/<form>/1/0/package/` → author `projection.json` → assert
`resolve_jsonschema(projected) == golden` → delete that form's Python component calls and
`draft_package`/`resolved_package`.

**The reuse curve is the headline metric:** new questions added per form should fall toward
zero. That number is the evidence the architecture works.

**SF-424 goes early** (position 3) despite its size: with ~18 numbered sections and 58
irregularly-named flat root properties it stresses both `@UI.section` placement and the legacy
projection hardest, and getting either vocabulary wrong is expensive to unwind. The budget
family goes last — `budget_family.py` (569 LOC), the `Budget424aSectionA..F` and `Table`
widgets, and the two-dimensional calculation graph.

### Phase 3 — Retire the superseded code path

- `api/src/form_schema/components/` (11 modules, 2,830 LOC)
- `templates/narrative_attachment.py` → three form specs composing one attachment question
- each `forms/<form>/1/0/form_json.py` shrinks to a package load

Retained: `form_definition.py`, `resolved_form_package.py`, `shared/`,
`jsonschema_resolver.py`, `rule_processing/`, `xml_plan.py`, every golden fixture, and
`behaviors.py`, which feeds the deferred rules layer.

### Phase 4 — The question browser

The tables ship in Phase 1; this phase is the browsable surface over them.

`analyze.ts` (~100 lines) makes one pass over `dist/**/schema.json`, building the `$ref` graph
across all blocks. Because composition is uniform (D9), the association table is the transitive
closure over `$ref` edges, so both "directly composes" and "ultimately contains" come from one
graph:

- **Question inventory** — `question_id, entity, attribute, tags, form_count, form_ids`
- **Form ↔ question association** — `form_id, question_id` (the filter table)
- **Pairwise similarity** — per unordered pair: `|Qa∩Qb| / |Qa∪Qb|` (Jaccard), `|Qa∩Qb|`,
  `|Qa∩Qb|/|Qa|`, `|Qa∩Qb|/|Qb|`

Surfaced as a browsable page driven by the same emitted artifacts, so browsing the common
questions is a page rather than a spreadsheet — and so the form builder inherits a ready-made
read model (§5).

---

## Part 7 — Verification

**Two artifact sets, and the adapter between them.** Per migrated form:

```
form-spec/dist/forms/sf424/          # canonical, target-neutral
├── schema.json                      # GENERATED — semantically nested (§2.5)
├── ui.json                          # GENERATED — JSON Forms, canonical scopes
├── index.json                       # GENERATED — catalogue facets
└── sgg/ui-schema.json               # GENERATED — mechanical vocabulary transform

api/src/form_schema/forms/sf424/1/0/  # the SGG adapter
├── package/                          # vendored from dist
├── projection.json                   # canonical leaf path → legacy name
├── golden/                           # frozen parity oracle (legacy flat shape)
└── manifest.json                     # per artifact: generated | projected | passthrough
```

The manifest labelling each artifact `generated`, `projected`, or `passthrough` is what makes
the reduced scope sound rather than a loss of rigor: the specification generates what it claims
to own, states exactly where the legacy shape is reintroduced, and proves the rest is
undisturbed.

**Parity is asserted after projection.** Because the canonical schema deliberately does not
match the legacy flat shape (§2.5), byte-equality is asserted on the projected result. This is
a stronger test than it sounds: it proves the canonical schema plus a declarative projection
carry exactly the information the golden did, with nothing added or lost.

**Contract conformance gates every emit.** Every artifact validates against its `contract/v1`
meta-schema in the emitter, and again in the Python adapter on load.

**Build-time checks.** Per-decorator and per-rule tests using `createTester`, following
`lib/changelog-emitter/test/tester.ts`. These must *fail*: a condition value outside the source
enum, a required-but-never-visible field, a calculation cycle, an `@UI.order` omitting a
property, a form-scoped question id.

**Parity, the primary gate.** Per form, in `tests/src/form_schema/forms/test_<form>.py`:

```python
# projected artifacts must byte-match the frozen golden
assert resolve_jsonschema(projected.form_json_schema) == golden_json_schema
assert projected.form_ui_schema     == golden_ui_schema
assert projected.form_rule_schema   == golden_rule_schema      # emitted whole by rules-sgg
assert projected.json_to_xml_schema == golden_xml_transform    # passthrough

# the projection is a bijection over leaf paths — nothing dropped, nothing merged
assert set(leaf_paths(canonical)) == set(projection.map)
assert len(set(projection.map.values())) == len(projection.map)   # no collisions
assert set(projection.map.values()) == set(leaf_paths(golden))    # no orphans

# derived ordering reproduces the hand-written integers
assert derived_order(canonical) == {f: r["order"] for f, r in golden_calcs.items() if "order" in r}
```

The ordering assertion is worth writing first: it proves the dependency graph independently
rediscovers SF-424A's hand-maintained `"order": 2`, which is the argument for bringing
calculations into scope. The three projection assertions come next — they are what stop the
projection from becoming a place to quietly absorb a modelling mistake.

`tests/src/form_schema/forms/conftest.py` already resolves schemas this way, so the harness
exists. `test_form_version_checksums.py` and `test_form_structure.py` must stay green
unmodified — independent evidence that nothing observable moved.

**UI round-trip.** `to_sgg(from_sgg(x)) == x` over every golden UI schema. Failures are exactly
the vocabulary gaps to close, and their list is the honest scope of the portability claim.

**Bank hygiene (CI, fails the build).**

- Every bank `$ref` in every form resolves within the pinned bank.
- No bank `$id` or file path contains a form name.
- No emitted runtime artifact contains `x-authoring*` or any override block.
- No `@extension("x-…")` anywhere in `specs/` — everything goes through decorators.
- No legacy field name and no SGG rule name appears anywhere under `form-spec/`.

**Reuse curve.** `analyze.ts` runs in CI and prints new-questions-added per form. A migration
PR that adds an unexpected number of new questions is a design signal, not a pass.

**Retirement census.** The same script prints two bounded counts: `@Sgg.*` call sites (§4.5)
and total projection entries (§2.5). Both should shrink as the CommonGrants mapping layer lands.
A PR that grows either needs a stated reason. Together with the reuse curve, that is three
numbers in CI, all falsifiable: reuse should rise, and both retirement counts should fall.

**End to end.** Run the API and render a migrated form in the frontend
(`workspace/applications/[applicationId]/form/[appFormId]`) and its print view. Then run the
deployment path in `api/src/task/forms/` against a local environment for `key_contacts` and
`sf424`, and generate XML for a submitted application to confirm `json_to_xml_schema` parity
holds through `services/xml_generation`.

---

## Part 8 — Deferred scope

Full designs, evidence, and the constraints discovered while working through real forms are in
[`deferred-designs.md`](./deferred-designs.md). Summary of what is out and why.

### 8.1 CommonGrants mappings

The core idea: `@Map.to(CommonGrants.Organization.name)` with the target typed as
`ModelProperty`, so renaming the target is a compile error at every mapping site. Verified
feasible (Phase 0 spike 2). Unlike the legacy projection, a CommonGrants binding is *semantic*
rather than target-specific, so it belongs in the library when it lands.

Key Contacts demonstrates that a property-to-property decorator is not sufficient. Five
problems arise in that one form: a **collection pivot** (SGG's ordered `key_contacts[]` array
to CG's `otherContacts: Record<PersonBase>` keyed object, keyed on a member field); a lossy
**key transformation** needing an explicit collision policy; a **promoted singleton**, since CG
requires exactly one `primary` and SGG has no primary flag, making the choice a policy
decision; a **cardinality mismatch** inside the element, where SGG's scalar
`phone`/`fax`/`email` meet CG's keyed collections; and **genuine non-invertibility**, since CG
`Record` is unordered and `projectDirector` → `"Project Director"` is not reliably
reconstructible.

There is also a hard limit on typed references: `Record<T>` has no declared members, and CG
uses it pervasively (`otherContacts`, `phones`, `emails`, `addresses`, `customFields`). So
`@Map.to(PersonBase.phones.primary)` cannot be fully compile-checked. The resolution is a
hybrid — reference the `Record`-typed property (checked) plus a key supplied separately
(validated at emit): `@Map.into(PersonBase.phones, #{ key: "primary" })`.

Implication: deriving both directions from one declaration is valid only for the simple case.
Collection pivots must be authored per direction or explicitly marked one-way, which is why the
build must refuse to guess.

### 8.2 XML wire transform

`@typespec/xml` is first-party and documented but **metadata only** — five decorators
(`@name`, `@attribute`, `@ns`, `@nsDeclarations`, `@unwrapped`), no XSD or XML emitter, and not
currently in the protocol repository's dependency set.

The strong version generates the wire model from the XSD into `specs/targets/wire/*.tsp` and
maps form properties onto it, so refreshing the XSD turns every affected mapping into an
enumerated compile error rather than a silent mis-target of the string `target: "City"`.

Caveats: the XSD importer is the main cost, since grants.gov leans heavily on GlobalLibrary
cross-schema type reuse; `@Xml.*` has no vocabulary for SGG's value-level behavior
(`null_handling: "default_value"`, `default_value: "John"` in `person_name.py`); and element
order needs its own test, as commit `43c5bb25 Preserve source-pinned XML sequence order`
shows.

While XML remains passthrough, the transform operates on the *projected* shape, so adopting a
generated transform for a form retires that form's XML dependency on the projection. Worth
sequencing deliberately rather than half-migrating.

### 8.3 Rules: named validators and expression languages

**A named function registry, not arbitrary expressions.** For `attachmentPresent`,
`dateBefore`, and similar: a small versioned registry. SGG's
`gg_validation: {rule: "attachment"}` is already exactly this. Portability comes from
reimplementation per language against a shared cross-language conformance suite, so the Python
validator and the TypeScript renderer provably agree. Note that the two largest rule groups are
already handled without it — attachment validation is inferred from the property's type and the
submit stamps from question identity (§4.5) — so the registry's arrival changes what the emitter
emits, not what any author writes.

**CEL is deliberately declined for runtime.** It is the strongest general option: a formal
spec, a Google-maintained Python implementation (`cel-expr-python`, open-sourced March 2026,
wrapping the official C++ runtime), and a community TypeScript implementation
(`@gresb/cel-javascript`). But form validity is evaluated in *both* Python and TypeScript, and
two independent expression-language implementations deciding whether a submission is valid is a
correctness risk — and the official Python binding adds a native dependency. CEL is retained
for authoring-time analysis and as an explicitly-marked server-only escape hatch.

**Open question.** Whether the `value`/calculate effect needs an evaluation-order guarantee
stronger than "acyclic" for the budget forms. XForms specifies full recalculate ordering.

### 8.4 Routing

A **guarded-edge graph**, not a statechart: `nodes: forms`, `edges: {from, to, when,
priority}`. Parallel states, entry/exit actions, side effects, and history states are
deliberately excluded — they are what make full statecharts (SCXML/XState) unanalyzable. What
is kept is guarded transitions and determinism, plus static checks: every node reachable, no
node whose guards can all be false (an `else` edge is required), and no unmarked cycles.

DMN decision tables are the right tool for *eligibility determination* — a many-input to
outcome decision, a different job from routing. If eligibility scoring appears, it is added as a
separate artifact type rather than by bending routing into it.

SGG has no cross-form routing, so this layer has no SGG emitter and would be consumed by
dedicated preview tooling first.

---

## Part 9 — Governing principles

Seven rules that decide any case this specification does not cover explicitly.

1. **The declarative artifact is the source of truth, never a snapshot of it.** If removing the
   generating code changes no output byte, that code is a test rather than an architecture.
2. **The build targets are the contract; the authoring tool is replaceable.** No consumer may
   depend on TypeSpec, so a second authoring path can be added without renegotiation.
3. **Compose with `$ref`, never with pointer-rebasing code.** Dereferencing already happens at
   registration (`form_template_registry.py:61`), so `$ref` composition is free upstream and
   invisible downstream.
4. **Presentation, conditions, and calculations belong in typed decorators.** Not
   `@extension("x-…")`, not dotted-path strings. Errors originate from the build, never from a
   consumer at load time.
5. **Questions are named for meaning, never for the form they appeared in.** Enforced by
   `no-form-scoped-question-id` rather than by review habit.
6. **Whether a target concern may live in the library depends on how it scales.** Adding a
   second consumer must *add* to the library, never *multiply* what it holds. A target emitter
   and its opt-in vocabulary add — `ui-schema-sgg`, `rules-sgg`, `@Sgg.*`. A projection
   multiplies, at forms × consumers, so it lives with the consumer (§2.5).
7. **Every headline claim is measured in CI.** Reuse per form must rise; the `@Sgg.*` census
   and the projection size must fall. An unmeasured claim is an unfalsifiable one.

**Adoption sequence.** The shared kernel lands inside the existing architecture first —
compatible with the large majority of it, zero runtime change (§1.4) — establishing the reuse
curve and the three tables before any proposal to simplify the form engine itself. The two are
kept separate so the first can be evaluated on its own evidence.

---

Sources consulted for §4 and §8: [TypeSpec XML library reference](https://typespec.io/docs/libraries/xml/reference/),
[FHIR Questionnaire](https://www.hl7.org/fhir/questionnaire.html), [CEL](https://cel.dev/),
[cel-expr-python announcement](https://opensource.googleblog.com/2026/03/announcing-cel-expr-python-the-common-expression-language-in-python-now-open-source.html),
[@gresb/cel-javascript](https://github.com/GRESB/cel-javascript),
[DMN decision tables](https://documentation.flowable.com/latest/model/dmn/example/part1-decision-table).
