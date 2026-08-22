# Implementation findings

Validating the specification in `documentation/form-spec/` against three real forms, one
from each major category. TypeSpec compiler 1.15.0.

## Verdict

**The approach is valid; no pivot is needed.** Three forms are authored declaratively from
a shared question bank, and each one's emitted artifacts are proven against the
hand-written original two ways.

| | Key Contacts | SF-424 | SF-424A |
|---|---|---|---|
| Category | repeatable section | basic info, widest | budget, calculations |
| Authored | ~70 lines | ~440 lines | ~150 lines |
| SGG UI schema | identical | identical | identical |
| SGG rule schema | identical (absent) | identical, 16 entries | identical, 35 calculations |
| Resolved JSON Schema | 18 differences, all accounted for | 97, all accounted for | 112, all accounted for |
| Validation behavior | 237 payloads, 0 disagreements | 752, 0 | 767, 0 |

## How parity is proven

Two independent assertions per form, in `api/tests/src/form_schema/form_spec/`.

**Behavioral** is the load-bearing one. It resolves both schemas, derives a corpus from
the golden — every field deleted, overrun, emptied, mistyped, and given a value outside its
enum — and requires SGG's own validator to report identical issues for every payload. It is
indifferent to how the schemas compose and sensitive to everything an applicant could see.

**Structural** compares the resolved schemas leaf by leaf. Every remaining difference is
named in an allow-list with a reason, and a second test fails if an entry stops matching,
so a stale explanation cannot accumulate. Allow-list keys are exact by default, `*`-prefixed
for a suffix, `/*`-suffixed for a subtree, so an entry says how much it means to cover.

## How much is derived rather than declared

This is the part worth showing. SGG's `forms/README.md` says the auto-summation behavior
is *"only found by figuring out the behavior from the PDF."*

| Artifact | Declared | Derived from |
|---|---|---|
| Attachment validation (5 rules) | nothing | a property composing `generics/attachment` |
| Submit stamps (3 rules) | nothing | `generics/signature`, `generics/submitted-date` |
| SF-424's total | one `@Validation.computed` | — |
| SF-424A's 35 calculations | eight declarations | four intrinsic to budget questions, four `@Validation.totals` |
| Every calculation's `order` | nothing | the depth of its dependency chain |
| `fieldList` | nothing | an array of objects |
| Section grid layout | nothing | the collection the section's total totals |
| Pre-population (8 rules) | eight `@Sgg.prePopulate` | — |

Only the last row is genuinely a choice, and only it is written down.

## What the golden turned out to get wrong

Composing one question where a form had two copies surfaced four inconsistencies. Each is
recorded in the parity test rather than worked around.

1. **The same question is capped at two lengths on the same form.** SF-424 box 8f's email
   uses `common_shared_v1#/contact_email` (60 characters); box 21's is written out inline
   with no cap. One question cannot be two lengths, so this is the single place in 1,756
   payloads where the two schemas disagree: an AOR email over 60 characters. Which box is
   right is a decision for the form's owners.
2. **`date_received` and `date_signed` are the same question** — a date Grants.gov stamps on
   submission — shared in one place and inlined in the other. Composing one question for
   both is what makes both rules come out right without declaring either.
3. **Two of SF-424's six read-only fields carry `readOnly` in the schema**, all six being
   `null` in the UI schema. Nothing reads the keyword: not the renderer, not the API.
4. **`person_name` is titled "Name and Contact Information"** with an empty description,
   which describes neither.

## What the emitter does and does not own

`@typespec/json-schema` is **wrapped**, not replaced. Its `$onEmit` is exported, so ours
calls it into a staging directory, reads the result back, and composes. One emitter, one
command, no downstream merge script.

Everything derivable from the type graph comes from stock: types, constraints, enums,
arrays, `required`, `$ref` composition, and `extends` as `allOf`. Two decorators delegate
rather than duplicate — `@Question.meta` to `@JsonSchema.id` for `$id` and every `$ref`
target, `@UI.label` to `@summary` for `title`. Our only schema contribution is the
`if`/`then` conditional requiredness from `@Validation.requiredWhen`.

## Integration cost

One entry in one list: the question bank is registered in
`jsonschema_resolver._get_shared_schemas_map` alongside `common_shared_v1` and
`address_shared_v1`. It is the same kind of artifact — a document of named definitions
referenced by pointer, resolved offline — at the granularity of a semantic question rather
than a primitive. `form_template_registry` already dereferences every form at registration,
so the API, the renderer, the validator, and XML generation keep receiving the schema they
receive today. Nothing downstream of that function moves.

The projection is four legacy accommodations, all in the adapter and none in the
specification: snake-cased naming, `allOf`-wrapping references so `jsonref` cannot discard
their siblings, flattening object composition so the UI schema's flat pointers resolve, and
retargeting references into the bank. A fifth is smaller but visible to applicants: a field
pinned to one value is `const` in JSON Schema 2020-12 and a single-member `enum` here, and
the validator reports the keyword that failed.

## Corrections the implementation forced

### Design-level

1. **`model X is Y` copies decorators, including `@Question.meta`.** A form-local extension
   silently inherits the question's identity, so two blocks claim one id. **`extends` is the
   correct idiom**: it leaves identity alone and stock emits `allOf: [{$ref: base}]`.
2. **The bank needs scalar questions.** Roughly half of it is single-valued.
   `@Question.meta` takes `Model | Scalar`.
3. **No base URI is declared in the specs.** Hosting is per-consumer; a block's identity is
   its `@Question.meta.id`, never its URI.
4. **Marshal at the decorator boundary, never in an emitter.** `valueof` arguments arrive as
   TypeSpec value objects with parent back-references.
5. **A doc comment is applicant-facing.** It becomes the question's `description`, which
   people read. Rationale belongs in `//` comments, which no artifact carries.
6. **`generics/attachment` is a file reference, not a file.** A form's schema validates what
   an applicant submits, and an applicant does not author a file's name, size, or MIME type.
   What the reference resolves to is `CommonGrants.Fields.File`; the mapping between them is
   a lookup, so it is one-way.
7. **A layout that restates the arithmetic is the wrong abstraction.** `@Sgg.multiField`
   began by listing the properties each budget section receives. They are the section's own
   properties, and the collection three sections grid over is the one their totals total —
   both already known. It now takes only the section and the widget.
8. **Section names are wire identifiers, not field names.** SGG's forms do not agree on a
   convention: most are snake-cased, SF-424A's are `SectionA`. A lowerCamel member name is
   projected; a member written in another convention is left alone.

### Language-level

9. **`op` is a TypeSpec keyword.** A parameter named `op` breaks the parser with a
   misleading `')' expected`. `@Validation.computed` takes `operator`.
10. **Reflection types need `using TypeSpec.Reflection;`.**
11. **Qualified references inside a nested namespace resolve relatively.** Inside
    `namespace SimplerForms.UI`, `SimplerForms.WidgetName` resolves to
    `SimplerForms.SimplerForms.WidgetName`.
12. **`valueof {}` rejects a populated object literal.** The override table takes
    `valueof Record<unknown>`.
13. **Bare property names do not resolve in decorator arguments.** `@UI.order(prefix)` fails;
    it must be `@UI.order(Model.prefix)`.
14. **`@UI.order` does accept inherited properties**, so a form-local extension can
    interleave its own fields with the question's.
15. **There is no `uuid` scalar.** An attachment is `@format("uuid") scalar ... extends string`,
    and the attachment rule is therefore inferred from the question's identity rather than
    from its type.
16. **Every `lib/*.tsp` must import the JS implementing its `extern dec` declarations.**
    Only `main.tsp` did, so the library type-checked when reached through that entry point
    and reported unimplemented declarations when a file was opened on its own. CI compiles
    every file standalone.

## Bugs in this implementation that only a real form exposed

* `@UI.helpText` wrote to the label's state key, silently overwriting labels.
* `@Sgg.prePopulate` stored `"[object Object]"`: an enum member's value needs the recursive
  literal reduction, not `String()`.
* `@Validation.computed` was ignored on any property typed as a scalar question, which is
  every monetary field.
* `@UI.overrides` was declared but unconsumed until SF-424 box 8d needed an address without
  a county.
* State and country enums were four- and two-member stubs. No structural review catches
  that; the first payload containing `"WY: Wyoming"` does. They are generated from
  `shared_form_constants.py` now, so the code lists have one authority.

## The reuse curve

Four forms in, migrated in this order:

| Form | Questions asked | New to the bank | Already there |
|---|---|---|---|
| Key Contacts | 8 | 8 | 0 |
| SF-424 | 25 | 19 | 6 |
| SF-424A | 6 | 5 | 1 |
| **SF-424-Short** | **23** | **0** | **23** |

SF-424-Short introduced nothing. It asks twenty-three questions and the bank already held
every one, including `poc/details` composed twice -- boxes 7 and 8, the project director and
the primary contact -- where the golden does it with a `$defs` plus two Python helpers that
parameterise the UI children and the XML target by base path. It shares 91% of its questions
with SF-424.

That is the number the architecture is for, and it took four forms to get one honest reading
of it.

### Two things that made it honest

**A field composing a generic is not a named question.** `authorizedRepresentativeTitle:
ContactTitle` looks like reuse and is not: `generics/contact-title` is a *shape*, and both
forms were declaring the same question against it independently. §2.3 says identity is
`entity x attribute`, and nine fields were ignoring it. They are `aor/title`, `aor/email`,
`aor/phone`, `aor/fax`, `aor/name`, `aor/signature`, `aor/date-signed`,
`primary-org/legal-name`, `primary-org/address` and `application/date-received` now, each
extending its shape so the constraints still live in one place.

`scripts/analyze.py` reports both numbers, because only the second one means anything: how
many field names a form declares itself, and how many of those another form also declares.
The second is at zero and should stay there.

**Naming a question must not stop the inference its shape implied.** The submit stamps and
the attachment rule were keyed on an exact question id, so `aor/signature` -- which extends
`generics/signature` -- silently lost its `gg_post_population` rule. Inference walks a
question's ancestry now. The same gap made the orphan check miss composition through a
scalar's base.

## The three tables

`npm run analyze` produces them from the emitted artifacts, never from the specs — so the
same script would work against artifacts from a form builder, and it is the read model a
question browser would use. Current state, with three forms in:

* 27 questions in the bank.
* **86% of Key Contacts' questions are also asked by SF-424.** That number is the reuse
  claim, computed rather than asserted.
* Key Contacts composes 2 questions directly and reaches 5 more through them, which is what
  `poc/details` is for.
* SF-424 introduced 15 new questions and reused 6; SF-424A introduced 5 and reused 1.

Three forms is too few to show a curve. What it does show is that the count is measurable
and that the second and third forms both drew on the first.

## Do the forms disagree with each other, or with grants.gov?

`scripts/scan_shape_agreement.py` compares each form's JSON shape against its own XML
transform, which stands in for the XSD: a field mapped with `type: "nested_object"` is a
complex type on the wire, and a field mapped without it is a simple element. The point is to
separate shape differences that are **upstream reality** from ones SGG introduced, because
only the second kind should be fixed in the form rather than absorbed by an adapter.

**SGG diverges from its own wire format in two places across fifteen forms.**
`sf424a.forecasted_cash_needs` groups three columns that the wire keeps flat, and
`sflll.reporting_entity.tier` is flat where the wire nests. Everything else is faithful.

So where two forms shape the same property differently, the wire says why:

| Property | Members | Wire element | Asked by |
|---|---|---|---|
| `contact_person` | the five name parts | `ContactPerson` | sf424 |
| `contact_person` | the five name parts | `ContactName` | cd511 |
| `contact_person` | name, title, address, phone, fax, email | `ContactPersonGroup` | sf424_short |
| `authorized_representative` | the five name parts | `AuthorizedRepresentative` | sf424, sf424_short |
| `authorized_representative` | name, title, address, phone, fax, email | `AuthorizedRepresentative` | epa_key_contacts |

`ContactPerson` and `ContactPersonGroup` are different XSD types. A form that asks for a name
element with a title element beside it is not a badly shaped version of a form that asks for
a contact group -- it is asking a different thing, and the wire format proves it.

### What that means for the bank

**Two granularities, because the domain has two.** `generics/person-name` for the forms whose
wire has a name element, `poc/details` for the four sites whose wire has a group type:
`sf424_short.contact_person`, `sf424_short.project_director`,
`epa_key_contacts.authorized_representative`, and `key_contacts[]`. That is fidelity, not
duplication.

**Flattening was solving a self-inflicted problem.** SF-424's wire format is a name element
plus a title element plus a phone element, so composing `generics/person-name` alongside
`generics/contact-title` and `generics/phone` *is* the faithful model -- which is what the
form already did before `poc/details` was forced onto it. `@Sgg.flatten` existed only to make
that forcing work. It is deleted, and the scan is why it is not coming back.

**The `address` case needs no shape mechanism at all.** Three memberships across thirteen
forms -- five, six and eight parts -- all mapping to a wire element named `Address`, because
GlobalLibrary has three address types. Every member beyond the first five is optional, so one
eight-member `generics/address` question with per-form `@UI.overrides` omission is
behaviorally identical to three questions. Omission is presentation, and SF-424's box 8d
already demonstrates it by dropping `county`.

### What remains an accommodation

Two, both in the adapter, both attributable, and neither about shape:

| Accommodation | Cause | Exit condition |
|---|---|---|
| `camelCase` to `snake_case` | `Budget424aSectionC/D/F.tsx` hardcode field names in frontend source; stored `application_response` and every `json_to_xml_schema` path are keyed by them | the widgets stop hardcoding, and stored responses are migrated |
| `const` to single-member `enum` | the validator reports the keyword that failed, so the message an applicant reads differs | never; both spellings are correct and this is the one in use |

Plus the fourteen rendered-field differences itemised in each form's parity test, each naming
one field and one reason, with a test that fails when an entry goes stale.

## Known gaps

* Linter rules and diagnostics are declared but not implemented.
* No TypeSpec-side test suite; `createTester` scaffolding is not in place. The parity tests
  are Python and test the artifacts.
* The XML transform and the CommonGrants mappings are out of scope, so
  `json_to_xml_schema` has no producer yet.
* `@UI.visibleWhen` and `@UI.readOnlyWhen` are declared and stored but no emitter consumes
  them; none of these three forms needs conditional visibility.
* Nothing checks that a declared property has somewhere to go on the wire. A property with no
  XML mapping and no `@UI.omit` is a field an applicant can fill in and the submission will
  drop -- a good candidate for the next validate-time error, and the scan already computes
  both halves of it.
