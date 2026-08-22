# Authoring model: worked reference

A concrete walkthrough of the authoring model specified in
[`architecture.md`](./architecture.md), against real forms. Key Contacts carries §§1–9;
SF-424 and SF-424A carry §§11–13, where the harder material lives.

**Why Key Contacts is the reference form.** It is the smallest SGG form with real cross-form overlap
(organization name, person name, address, phone, fax, email, contact title), it needs
no rule schema at all, and it exercises the one genuinely awkward feature — a
repeatable `fieldList` of 1–4 contacts. Everything below is derived from the actual
current implementation in `api/src/form_schema/forms/key_contacts/1/0/form_json.py`
(186 lines) plus `components/contact_profile.py` (254 lines), so the "after" is
directly comparable to the "before".

**Scope.** CommonGrants mappings and XML are deferred, so this covers the two layers
that matter most: **JSON Schema** and **UI schema** — emitted per *block*, where a block is a
question or a form (§13). The rule schema passes through
unchanged from the frozen golden artifacts (§8). The canonical schema is *not* shape-matched
to SGG's legacy flat schema — a per-form **projection** handles that (§11), which is also
what keeps the XML transform working.

## Contents

| | |
|---|---|
| [1. What you write](#1-what-you-write) | questions, composition, the form |
| [2. What comes out](#2-what-comes-out) | emitted bank / form / UI artifacts |
| [3. Before / after](#3-before--after) | line-count and mechanism comparison |
| [4. What the compiler catches](#4-what-the-compiler-catches) | the ergonomic payoff |
| [5. Where this costs more than today](#5-where-this-costs-more-than-today) | authoring overhead, seven items |
| [6. Out of scope](#6-out-of-scope) | deferred layers |
| [7. Validated assumptions](#7-validated-assumptions) | confirmed against TypeSpec 1.15.0 |
| [8. How parity is proven](#8-how-parity-is-proven) | golden oracles and passthrough |
| [9. Design decisions](#9-design-decisions) | D1–D11, with motivating examples |
| [10. Key Contacts and the mapping layer](#10-key-contacts-as-the-reference-case-for-the-deferred-mapping-layer) | why the repeat is hard |
| **[11. Structure: canonical schema vs SGG's flat shape](#11-structure-the-canonical-schema-is-well-formed-sggs-flat-shape-is-a-projection)** | **flat UI over nested data; the projection artifact** |
| [12. Rules, by example](#12-rules-by-example) | conditional logic, calculations, validators |
| **[13. Blocks: the unit of composition](#13-blocks-the-unit-of-composition-d9)** | **per-block UI artifacts; uniform composition** |

---

## 1. What you write

### 1.1 Directory shape

```
form-spec/specs/
├── question-bank/
│   ├── generics/
│   │   ├── person-name.tsp
│   │   ├── address.tsp
│   │   ├── phone.tsp
│   │   ├── email.tsp
│   │   ├── organization-name.tsp
│   │   └── contact-title.tsp
│   └── poc/
│       └── poc-details.tsp        # composes the generics into "a point of contact"
└── forms/
    └── key-contacts.tsp           # composes questions + form-specific deltas
```

### 1.2 A generic question

The whole point: **you never write a UI schema.** You declare properties and annotate
them. The emitter composes the UI artifact from the model graph.

```typespec
import "@simpler-grants/form-spec";

using SimplerForms;

namespace QuestionBank.Generics;

/** A person's name, in five parts. */
@Question.meta("generics/person-name")
@Catalog.tag(TagName.person, TagName.name)
@UI.order(prefix, firstName, middleName, lastName, suffix)
model QuestionPersonName {
  /** Enter the Prefix. */
  @UI.label("Prefix")
  @maxLength(10)
  prefix?: string;

  /** Enter the First Name. */
  @UI.label("First Name")
  @maxLength(35)
  firstName: string;

  /** Enter the Middle Name. */
  @UI.label("Middle Name")
  @maxLength(25)
  middleName?: string;

  /** Enter the Last Name. */
  @UI.label("Last Name")
  @maxLength(60)
  lastName: string;

  /** Enter the Suffix. */
  @UI.label("Suffix")
  @maxLength(10)
  suffix?: string;
}
```

Notes on ergonomics:

- **Requiredness comes from TypeSpec's own `?`**, not a separate `required: [...]` array
  you can forget to update. `firstName`/`lastName` required, the rest optional —
  matching `common_shared.py`'s `person_name` exactly.
- `@order` takes **property references**. Reorder freely; delete a property and the
  `@order` line fails to compile. Today the equivalent is a tuple of strings in
  `contact_profile.py`:
  `("prefix", "first_name", "middle_name", "last_name", "suffix")`.
- The doc comment becomes `description`; `@label` becomes `title`. One place each.

### 1.3 A generic question with conditional logic

The address is where real behavior lives. Today `address_shared.py` hand-writes a JSON
Schema `allOf`/`if`/`then` block, and the forms README has to *teach* authors the
"remember to add `required: ["country"]` inside the `if`" idiom.

```typespec
namespace QuestionBank.Generics;

/** Enter an address. */
@Question.meta("generics/address")
@Catalog.tag(TagName.address)
@UI.order(street1, street2, city, county, state, province, country, zipCode)
model QuestionAddress {
  /** Enter the first line of the Street Address. */
  @UI.label("Street 1") @maxLength(55)
  street1: string;

  /** Enter the second line of the Street Address. */
  @UI.label("Street 2") @maxLength(55)
  street2?: string;

  /** Enter the city. */
  @UI.label("City") @maxLength(35)
  city: string;

  /** Enter the County or Parish. */
  @UI.label("County/Parish") @maxLength(30)
  county?: string;

  /** Enter the state. */
  @UI.label("State")
  @Validation.requiredWhen(QuestionAddress.country, CountryCode.USA_UNITED_STATES)
  state?: StateCode;

  /** Enter the province. */
  @UI.label("Province") @maxLength(30)
  province?: string;

  /** Enter the country. */
  @UI.label("Country")
  country: CountryCode;

  /** Enter the nine-digit Postal Code (e.g., ZIP Code). */
  @UI.label("Zip / Postal Code") @maxLength(30)
  @Validation.requiredWhen(QuestionAddress.country, CountryCode.USA_UNITED_STATES)
  zipCode?: string;
}
```

`@requiredWhen` takes a **property reference plus an enum member**. Both halves are
compile-checked. The emitter generates the `if`/`then` block *and* the `required:
["country"]` guard automatically — the house idiom is encoded once in the emitter
instead of in every author's head.

### 1.4 An entity-scoped question composing generics

```typespec
import "../generics/person-name.tsp";
import "../generics/address.tsp";
import "../generics/phone.tsp";
import "../generics/email.tsp";
import "../generics/contact-title.tsp";

namespace QuestionBank.Poc;

/** A point of contact: name, title, address, and contact methods. */
@Question.meta("poc/details")
@Catalog.entity(EntityName.poc)
@Catalog.tag(TagName.person, TagName.details)
@UI.order(name, title, address, phone, fax, email)
model QuestionPocDetails {
  name: Generics.QuestionPersonName;
  title?: Generics.QuestionContactTitle;
  address: Generics.QuestionAddress;

  @UI.label("Telephone Number")
  phone: Generics.QuestionPhone;

  @UI.label("Fax Number")
  fax?: Generics.QuestionPhone;

  @UI.label("Email")
  email: Generics.QuestionEmail;
}
```

**This is the fix for the biggest CommonGrants-bank problem.** In the current bank,
`QuestionPrimaryOrgAddress extends QuestionAddress` re-spells all seven UI controls
verbatim — violating the forms README's own rule ("Override individual fields, do not
redeclare the whole tree"). Here there is no tree to redeclare: the composed question's
UI is derived from the composed models. Inheritance of presentation is automatic
because presentation is attached to properties, not stored as a blob.

### 1.5 The form

```typespec
import "@simpler-grants/form-spec";
import "../question-bank/generics/organization-name.tsp";
import "../question-bank/poc/poc-details.tsp";

using SimplerForms;

namespace Forms.KeyContacts;

/** Sections, in paper-form order. Member name -> `name`, value -> `label`, doc -> `description`. */
enum KeyContactsSection {
  /** Enter between 1 and 4 key contacts and their role on the project. */
  keyContacts: "Key Contacts",
}

/**
 * One key contact and their role on the project.
 *
 * `extends`, never `is`: `is` copies the base's decorators including `@Question.meta`,
 * so the extension would claim the bank question's identity. Every `@UI.order`
 * reference must be qualified — bare property names do not resolve in a decorator
 * argument. Both are costs recorded in §5.
 */
@UI.order(
  KeyContactPerson.projectRole,
  KeyContactPerson.name,
  KeyContactPerson.title,
  KeyContactPerson.organizationalAffiliation,
  KeyContactPerson.address,
  KeyContactPerson.phone,
  KeyContactPerson.fax,
  KeyContactPerson.email
)
model KeyContactPerson extends QuestionBank.Poc.QuestionPocDetails {
  /** Enter the individual's role on the project (e.g., project manager, fiscal contact). */
  @UI.label("Project Role")
  @minLength(1) @maxLength(45)
  projectRole: string;

  /** Enter the contact's organizational affiliation. */
  @UI.label("Organizational Affiliation")
  organizationalAffiliation?: QuestionBank.Generics.QuestionOrganizationName;
}

/**
 * KEY CONTACTS (Grants.gov FID 683, v2.0)
 */
@Form.meta(#{
  formId: "f140c7db-724d-4954-bebd-081c0527908c",
  legacyFormId: 683,
  formName: "KEY CONTACTS",
  shortFormName: "Key_Contacts",
  formVersion: "2.0",
  ombNumber: "4040-0010",
  formType: "KEY_CONTACTS",
})
@UI.sections(KeyContactsSection)
model KeyContacts {
  /** Enter the legal name of the applicant that will undertake the assistance activity. This field is required. */
  @UI.label("Applicant Organization Name")
  @UI.section(KeyContactsSection.keyContacts)
  applicantOrganizationName: QuestionBank.Generics.QuestionOrganizationName;

  /** Enter between 1 and 4 key contacts and their role on the project. */
  @UI.label("Key Contact")
  @UI.section(KeyContactsSection.keyContacts)
  @minItems(1)
  @maxItems(4)
  keyContacts: KeyContactPerson[];
}
```

That is the whole form: **~50 lines**, versus 186 lines of Python plus a form-named `Literal`
branch inside a 254-line shared component.

Four things doing quiet work here:

- **`@UI.overrides` reaches any depth.** `` `phone` `` here, but `` `address.state` `` would
  work identically — no model cloning (§5.4).
- **`@UI.sections(KeyContactsSection)`** declares section order once. Section *references*
  are enum members, so a typo is a compile error rather than a silently orphaned field.
- **`fieldList` is inferred** from `KeyContactPerson[]` being an array of objects; the label
  and description come from `@UI.label` and the doc comment. No `@UI.fieldList` needed for
  the common case.
- **`minItems`/`maxItems`/`minLength`/`maxLength` are TypeSpec standard library.** Nothing of
  ours involved.

## 2. What comes out

### 2.1 Bank question artifact — `dist/question-bank/v1/generics/person-name.json`

```json
{
  "$id": "https://files.simpler.grants.gov/schemas/question-bank/v1/generics/person-name.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Person Name",
  "description": "A person's name, in five parts.",
  "type": "object",
  "required": ["first_name", "last_name"],
  "properties": {
    "prefix":      { "type": "string", "title": "Prefix",      "description": "Enter the Prefix.",      "maxLength": 10 },
    "first_name":  { "type": "string", "title": "First Name",  "description": "Enter the First Name.",  "maxLength": 35 },
    "middle_name": { "type": "string", "title": "Middle Name", "description": "Enter the Middle Name.", "maxLength": 25 },
    "last_name":   { "type": "string", "title": "Last Name",   "description": "Enter the Last Name.",   "maxLength": 60 },
    "suffix":      { "type": "string", "title": "Suffix",      "description": "Enter the Suffix.",      "maxLength": 10 }
  },
  "x-question": { "id": "generics/person-name", "tags": ["person", "name"] }
}
```

Note: `x-question` here is **inert provenance for the browser and the three tables** —
no logic reads it, and question identity is still the `$id`/`$ref`. If we want zero
custom keywords, the analysis pass can key entirely off `$ref` targets and this block
can be dropped. Worth deciding early (§9).

### 2.2 Form JSON Schema — `$ref`s preserved

```json
{
  "type": "object",
  "required": ["applicant_organization_name", "key_contacts"],
  "properties": {
    "applicant_organization_name": {
      "allOf": [{ "$ref": ".../question-bank/v1/generics/organization-name.json" }],
      "title": "Applicant Organization Name",
      "description": "Enter the legal name of the applicant that will undertake the assistance activity. This field is required."
    },
    "key_contacts": {
      "type": "array",
      "title": "Key Contacts",
      "description": "Enter between 1 and 4 key contacts and their role on the project.",
      "minItems": 1,
      "maxItems": 4,
      "items": { "$ref": "#/$defs/key_contact_person" }
    }
  },
  "$defs": {
    "key_contact_person": {
      "type": "object",
      "required": ["project_role", "name", "address", "phone", "email"],
      "properties": {
        "project_role": { "type": "string", "title": "Project Role", "minLength": 1, "maxLength": 45, "description": "..." },
        "name":    { "allOf": [{ "$ref": ".../question-bank/v1/generics/person-name.json" }] },
        "title":   { "allOf": [{ "$ref": ".../question-bank/v1/generics/contact-title.json" }], "title": "Title" },
        "organizational_affiliation": {
          "allOf": [{ "$ref": ".../question-bank/v1/generics/organization-name.json" }],
          "title": "Organizational Affiliation",
          "description": "Enter the contact's organizational affiliation."
        },
        "address": { "allOf": [{ "$ref": ".../question-bank/v1/generics/address.json" }] },
        "phone":   { "allOf": [{ "$ref": ".../question-bank/v1/generics/phone.json" }], "title": "Telephone Number" },
        "fax":     { "allOf": [{ "$ref": ".../question-bank/v1/generics/phone.json" }], "title": "Fax Number" },
        "email":   { "allOf": [{ "$ref": ".../question-bank/v1/generics/email.json" }], "title": "Email" }
      }
    }
  }
}
```

Compare to the golden, which inlines the same content with no external `$ref`. Parity is
asserted **after** `resolve_jsonschema()`, which the registry already runs at
registration time — so `$ref`-vs-inline is invisible downstream and
`$defs`-vs-external-`$ref` doesn't matter either.

The `allOf` wrapper is the existing house idiom from `forms/README.md` (so a local
`title`/`description` isn't clobbered by the `$ref`), applied by the emitter rather
than remembered by the author.

### 2.3 Canonical UI artifact (JSON Forms profile)

Composed from `@order` + `@label` + `@fieldList` + `@section`. Abridged:

```json
{
  "type": "VerticalLayout",
  "elements": [
    { "type": "Group", "label": "Key Contacts",
      "elements": [
        { "type": "Control", "scope": "#/properties/applicant_organization_name",
          "label": "Applicant Organization Name" },
        { "type": "Control", "scope": "#/properties/key_contacts",
          "label": "Key Contact",
          "options": { "detail": { "type": "VerticalLayout", "elements": [
            { "type": "Control", "scope": "#/properties/project_role", "label": "Project Role" },
            { "type": "Control", "scope": "#/properties/name/properties/prefix", "label": "Prefix" },
            { "type": "Control", "scope": "#/properties/name/properties/first_name", "label": "First Name" },
            "…",
            { "type": "Control", "scope": "#/properties/address/properties/state", "label": "State" },
            { "type": "Control", "scope": "#/properties/address/properties/province", "label": "Province" },
            "…"
          ] } } }
      ] }
  ]
}
```

### 2.4 SGG UI artifact — byte-identical to the golden

```json
[
  {
    "type": "section",
    "label": "Key Contacts",
    "name": "key_contacts",
    "description": "Enter between 1 and 4 key contacts and their role on the project.",
    "children": [
      { "type": "field", "definition": "/properties/applicant_organization_name" },
      {
        "type": "fieldList",
        "name": "key_contacts",
        "label": "Key Contact",
        "description": "You may enter up to four (4) Key Contacts. At least 1 (one) contact person is required. Additional contacts are optional.",
        "children": [
          { "type": "field", "definition": "/properties/key_contacts/items/properties/project_role" },
          { "type": "field", "definition": "/properties/key_contacts/items/properties/name/properties/prefix" },
          { "type": "field", "definition": "/properties/key_contacts/items/properties/name/properties/first_name" },
          { "type": "field", "definition": "/properties/key_contacts/items/properties/name/properties/middle_name" },
          { "type": "field", "definition": "/properties/key_contacts/items/properties/name/properties/last_name" },
          { "type": "field", "definition": "/properties/key_contacts/items/properties/name/properties/suffix" },
          { "type": "field", "definition": "/properties/key_contacts/items/properties/title" },
          { "type": "field", "definition": "/properties/key_contacts/items/properties/organizational_affiliation" },
          { "type": "field", "definition": "/properties/key_contacts/items/properties/address/properties/street1" },
          "… county, state, province, country, zip_code …",
          { "type": "field", "definition": "/properties/key_contacts/items/properties/phone" },
          { "type": "field", "definition": "/properties/key_contacts/items/properties/fax" },
          { "type": "field", "definition": "/properties/key_contacts/items/properties/email" }
        ]
      }
    ]
  }
]
```

**Every one of those `definition` pointers is derived from the model graph.** Today they
are hand-assembled strings — `contact_profile.py` builds them from a `ui_suffixes` dict
of literal path fragments, and `key_contacts/form_json.py` splats them with
`*_CONTACT_PROFILE.ui_fields["address"]`. A renamed property currently produces a dead
pointer; here it produces a compile error.

---

## 3. Before / after

| | Today | Proposed |
|---|---|---|
| Form definition | 186 lines Python (`key_contacts/1/0/form_json.py`) | ~45 lines TypeSpec |
| Shared contact shape | `Literal["key_contacts", "global_contact_person_v3", "sf424_short_contact_person_v3"]` branch in 254-line `contact_profile.py` | one `poc/details` question + per-form overrides |
| UI pointers | hand-written strings, splatted from a `ui_suffixes` dict | derived from the model graph |
| Conditional requiredness | hand-written `allOf`/`if`/`then` + a documented idiom to remember | `@Validation.requiredWhen(prop, enumMember)` |
| Field order | tuple of strings | `@UI.order(prop, prop, …)` — property references |
| Adding SF-424 Short's contact | new `Literal` member + new config fields | overrides on a form-local clone |
| Renaming a shared field | silently dead UI pointer | compile error |

---

## 4. What the compiler catches

The ergonomic payoff. Each of these is an error at `tsp compile`, not a runtime surprise
or a silently dead control.

| You write | You get |
|---|---|
| `@UI.widget(WidgetName.Buget424aSectionA)` | TypeSpec: unknown enum member `Buget424aSectionA` |
| `@UI.order(prefix, frstName, lastName)` | TypeSpec: unknown identifier `frstName` |
| `@Validation.requiredWhen(QuestionAddress.contry, …)` | TypeSpec: `QuestionAddress` has no property `contry` |
| `@Validation.requiredWhen(QuestionAddress.country, "USA: UNITED STATE")` | `condition-value-not-in-enum`: not a member of `CountryCode`; did you mean `USA_UNITED_STATES`? |
| `@@UI.label(KeyContactPoc.street3, "…")` | TypeSpec: unknown property in augment target |
| `@Question.meta("key-contacts/contact-address")` | `no-form-scoped-question-id`: question ids are named for meaning, not forms |
| a question with no doc comment | `require-question-docs` (warning) — it becomes the browser description |
| a field `@Validation.requiredWhen(x)` that is also never visible when `x` | `$onValidate`: required-but-unreachable |
| `@order` omitting a property | `order-incomplete` — with a `defineCodeFix` that appends the missing names |

The last three are the interesting ones: they are **whole-program** checks that are
impossible in the current architecture because requiredness and visibility live in
different files in different languages.

---

## 5. Where this costs more than today

Authoring overhead introduced by this model, relative to the current implementation.

1. **A section enum per form.** ~5 extra lines for Key Contacts, ~26 for SF-424. It buys
   compile-checked section references (D4) and carries name + label + description in one
   declaration, but it is boilerplate that inline labels wouldn't need.
2. **One extra model per repeatable item.** `KeyContactPerson extends QuestionPocDetails { … }`
   exists to add `projectRole` and `organizationalAffiliation` to the shared contact. That's
   genuine composition rather than ceremony — but it is still a named type you wouldn't write
   if you were hand-authoring JSON.
3. **Casing indirection.** Canonical is `camelCase`, SGG is `snake_case` (D5), so what you
   read in the spec is never quite what you read in the emitted artifact. The projection's
   default rule keeps it mechanical, but it's one more hop when debugging a parity failure.
4. **Reaching a nested field costs one override entry — resolved, but worth understanding
   why.** The obvious TypeSpec idiom is an augment: `@@UI.label(Model.prop, "…")`. It gives
   true compile-time target resolution, but it cannot reach *into* a composed question.
   `Model.prop` yields a `ModelProperty`; reaching inside needs `Model.prop::type`, and that
   type *is* the shared bank question — so augmenting through it would mutate the bank for
   every form. Cloning the outer model doesn't help; you'd clone every model on the path:

   ```typespec
   model AorAddress extends Generics.QuestionAddress {}          // clone 1
   @@UI.widget(AorAddress.state, WidgetName.Select);

   model Sf424Aor extends QuestionBank.Aor.QuestionAorDetails {  // clone 2
     address: AorAddress;                                        // re-declare to use clone 1
   }
   ```

   Two extra models to relabel one field three levels down. Key Contacts barely notices;
   SF-424, with per-field labels like `"8d. Street1"`, would drown.

   **Decision (D3): the override table is the primary mechanism.**

   ```typespec
   @UI.overrides(#{
     `address.state`:   #{ widget: WidgetName.Select },
     `address.street1`: #{ label: "8d. Street1" },
   })
   aor: QuestionBank.Aor.QuestionAorDetails;
   ```

   This resembles the CommonGrants `x-overrides` block criticized earlier, and the difference
   matters: there, paths are checked at *website load* time and values are bare strings. Here,
   paths resolve against the model graph in `$onValidate` and values are enum members
   (`WidgetName.Select`) checked by the checker. Same shape, different guarantees. Augments
   stay available for direct properties of a form, where they read naturally.

5. **Qualified property references in `@UI.order`.** Bare names do not resolve in a decorator
   argument, so every entry reads `KeyContactPerson.projectRole` rather than `projectRole`.
   Eight properties become eight qualified references. Key Contacts genuinely needs the explicit
   order — the golden interleaves a form-local field between inherited ones — so this is not
   avoidable by falling back to declaration order.
6. **`extends` rather than the more obvious `is`.** `is` reads like the natural way to say "a
   contact plus two fields," and it compiles. It also copies `@Question.meta`, so the extension
   claims the bank question's identity and the two collide on one output path. The
   `duplicate-block-id` rule catches it, but the wrong idiom is the more attractive one.
7. **Enum members can't hold arbitrary strings as identifiers.** `"USA: UNITED STATES"`
   becomes `CountryCode.USA_UNITED_STATES` with a value of `"USA: UNITED STATES"`. Fine,
   but the identifier↔value mapping is one more thing to get right, and the ~200-member
   country enum and ~60-member state enum have to be generated rather than typed.

---

## 6. Out of scope

- **CommonGrants mappings** (`@Map.*`). Bank questions carry no CG bindings; adding them later
  is additive and touches only the bank.
- **XML** (`@Xml.*`, XSD-derived wire models). `json_to_xml_schema` passes through from the
  frozen golden artifact (§8), unchanged.
- **Routing.** No SGG counterpart exists, so there is no parity target.

Conditional logic and calculations *are* in scope (§12), as are SGG's remaining rule names in
a quarantined namespace (§12.5). Key Contacts exercises none of them — its
`form_rule_schema` is `None` — which is part of why it is the reference form; §12 uses SF-424
and SF-424A instead.

---

## 7. Validated assumptions

All resolved against TypeSpec 1.15.0. Full detail and the corrections each forced are in
[`form-spec/FINDINGS.md`](../../form-spec/FINDINGS.md).

| Assumption | Result |
|---|---|
| `ModelProperty` as a **non-target** decorator parameter, via a member expression | Works. `@Validation.requiredWhen(QuestionAddress.country, CountryCode.USA)` resolves and reaches the implementation as a `ModelProperty`. |
| `valueof EnumMember` as an argument | Works — `@UI.section(KeyContactsSection.keyContacts)`. |
| Enum-member reference **inside an object literal** | Works — `#{ section: Sf424Section.orgUnit }`. |
| `$ref` composition survives emission | Works, recursively, at every level. |
| `@UI.order` accepting properties inherited through `extends` | Works, and is what lets a form interleave its own fields with the question's to match the golden's field order. |
| A derived model isolating overrides from its base | Works with `extends`; **fails with `is`**, which copies the base's decorators including identity. |

## 8. How parity is proven

Because XML and rules are out of scope, the emitted package for a migrated form
**passes them through** from the frozen golden artifacts:

```
forms/key_contacts/1/0/
├── golden/                     # frozen, the parity oracle
│   ├── json-schema.json
│   ├── ui-schema.json
│   └── xml-transform.json
├── package/                    # emitted
│   ├── json-schema.json        # GENERATED from key-contacts.tsp
│   ├── ui-schema.json          # GENERATED
│   ├── xml-transform.json      # PASSTHROUGH from golden/, byte-identical
│   └── manifest.json           # records which artifacts are generated vs passthrough
```

The manifest marks each artifact `generated` or `passthrough`, so it is always explicit
which layers the new architecture actually owns. Parity assertions are unchanged:

```python
assert resolve_jsonschema(emitted.form_json_schema) == golden_json_schema
assert emitted.form_ui_schema     == golden_ui_schema
assert emitted.json_to_xml_schema == golden_xml_transform   # trivially true while passthrough
```

This is what makes the descope safe rather than a loss of rigor: we generate the two
layers we claim to own, and we prove we didn't disturb the rest.

---

## 9. Design decisions

Normative. Mirrors [`architecture.md` Part 0](./architecture.md), recorded here alongside the
worked examples that motivate each.

### Resolved

| # | Question | Decision |
|---|---|---|
| D1 | Decorator naming | **Namespaced**: `@Question.*`, `@UI.*`, `@Validation.*`, later `@Map.*`. First-party precedent in `@typespec/json-schema` (`@JsonSchema.id`) and already used in the current bank. Authors get both spellings — `using SimplerForms` → `@UI.label`, `using SimplerForms.UI` → bare `@label`. |
| D2 | Where conditional effects live | **Split by artifact.** `@UI.visibleWhen` / `@UI.readOnlyWhen` land in the UI schema; `@Validation.requiredWhen` lands in JSON Schema. The call site names the destination, which guards the §12.2 trap directly. |
| D3 | Overrides: augments or a table | **Table primary** (§5.4). Augments can't reach into a composed question without cloning every model on the path. |
| D4 | Section declaration | **An enum**, referenced by member — so `@UI.sections` and every `section:` key stay in sync at the *checker*, not via a linter rule. Mirrors `@invisible(…, visibilityClass: Enum)` + `@visibility(…, valueof EnumMember[])` in the standard library, and `enum Versions` in `@typespec/versioning`. One member yields all three fields SGG needs: name (snake_cased), label (member value), description (doc comment). |
| D5 | Casing | **Canonical is `camelCase`**; `snake_case` lives in the projection (§11.4), which has a default `camelCase → snake_case` rule so only irregularities need entries — SF-424 needs ~7, not 58. |
| D6 | Custom keywords in the bank artifact | **Zero.** Composites stay nested (§11.2), so a `$ref` scan recovers the three tables. Tags and entity move to a sidecar bank index the browser reads. The `x-question` block in §2.1's example should be dropped. |
| D7 | Generated code enums | **Python → TypeSpec** initially, from `shared_form_constants.py` into `question-bank/generics/codes.tsp`, with a CI drift check. Reverse later if the bank becomes authoritative. |
| D8 | `fieldList` | **Inferred** from "array of object", label and description from `@UI.label` and the doc comment. Explicit decorator only for what inference can't reach (`minItemsHeading`, `maxItemsHelperText`, nested-fieldList `definition`). |
| D9 | Unit of composition | **A *block*** (§13). Questions and forms are both blocks, distinguished only by `@Question.meta` vs `@Form.meta`. A block is a Model when it holds several values and a **Scalar** when it holds one — roughly half the bank is single-valued. Every block emits its own `schema.json`, `ui.json`, and `index.json`. Sections are the single grouping mechanism, usable at any block level. |
| D10 | SGG's remaining rule names | **Declared in an `@Sgg.*` namespace** (§12.5), so the library emits a *complete* SGG rule schema in one pass and the adapter merges nothing. 8 names, restricted to `specs/forms/` by lint, counted in CI. Attachment validation and submit stamps are inferred and need no authoring surface. |
| D11 | Decorator arguments | **Marshalled to plain data on write.** `valueof` arguments arrive as compiler graph nodes with parent back-references and cannot be serialized; state holds values so every emitter and linter rule reads plain JSON. |

Alongside D1: **field constraints need no namespace of this library's own.** `@maxLength`,
`@pattern`, `@minValue`, `@minItems` and `?` are TypeSpec built-ins, so roughly half of what
`address_shared.py` hand-writes is provided by the standard library.

### Open items

1. **Whether the projection's default casing rule should be opt-in per form.** A global
   `camelCase → snake_case` default is invisible until a form needs an exception, which is a
   small trap of exactly the kind D4 was chosen to avoid.
2. **Conditional sections.** SGG's `UiSchemaSection` accepts a `conditional`, but **no golden
   uses it** — zero across every form; conditions are on fields only. Should one be required,
   an augment on the enum member is the natural spelling
   (`@@UI.visibleWhen(Sf424Section.revision, SF424.applicationType, ApplicationType.Revision)`),
   since enum members are augmentable targets. Deferred until a form requires it.
3. **How deep `index.json` facets go.** The website's `CatalogItem` is
   `{ id, name, description, tags, rawSchema }`. Whether `entity`, source provenance, or the
   reuse count belong there or in a generated top-level catalogue is a browser-UX question,
   not a schema one.

## 10. Key Contacts as the reference case for the deferred mapping layer

Mapping is out of scope, but Key Contacts' repeatable section is the best available stress
test for that layer, so the constraints it imposes are recorded here rather than rediscovered
later. Full design: [`deferred-designs.md` §1](./deferred-designs.md).

### 10.1 The shape mismatch

SGG form data is an **ordered array**:

```json
{ "applicant_organization_name": "…",
  "key_contacts": [
    { "project_role": "Project Director", "name": {…}, "phone": "555-111-2222", … },
    { "project_role": "Fiscal Contact",   "name": {…}, "phone": "555-333-4444", … }
  ] }
```

CommonGrants models it as a **promoted singleton plus a keyed record**
(`lib/core/lib/core/models/proposal.tsp`):

```typespec
model ProposalContacts {
  primary: PersonBase;                    // required, singular
  otherContacts?: Record<PersonBase>;     // keyed, unordered
}
```

```json
{ "contacts": {
    "primary": { "name": {…}, "phones": { "primary": "…" } },
    "otherContacts": {
      "principalInvestigator":     { "name": {…} },
      "authorizedRepresentative":  { "name": {…} } } } }
```

### 10.2 Five distinct problems, all in one form

1. **Collection pivot.** Array → keyed object, where the key is derived from a *member
   field's value* (`project_role`). A property-to-property `@mapsTo` cannot express this;
   it needs a collection-level construct with a key selector.
2. **Key transformation.** `"Project Director"` → `projectDirector`. A value transform on
   the *key*, and a lossy one — two roles differing only in punctuation or case collide.
   Needs an explicit collision policy (`error` vs `suffix`), not a silent last-write-wins.
3. **Promoted singleton.** CG requires exactly one `primary`; SGG has a flat array with
   no primary flag. Which element becomes `primary` is a **policy decision**, not a
   mechanical mapping, and it has to be declared and reviewable.
4. **Cardinality mismatch inside the element.** SGG `phone`/`fax`/`email` are scalars;
   CG `PersonBase` has `phones`/`emails`/`addresses` as keyed *collections*. So
   `phone → phones.primary` is a scalar→keyed-collection adapter. This is the most common
   case across the whole bank and probably deserves dedicated sugar.
5. **Genuine non-invertibility.** Reversing needs an ordering that CG `Record` does not
   define, requires flattening `primary` + `otherContacts` back into one array, and must
   reconstruct `"Project Director"` from `projectDirector` — which is not reliably
   invertible. This is a concrete instance of the case that must fail the build unless
   explicitly declared, rather than being silently assumed.

### 10.3 A real limit on typed property references

`otherContacts?: Record<PersonBase>` has **no declared members**. Neither do `phones`,
`emails`, `addresses`, or `customFields` — CommonGrants uses `Record<T>` pervasively.

So `@Map.to(PersonBase.phones.primary)` **cannot** be a fully compile-checked property
reference: `primary` is a dynamic record key, not a declared property. The reference-based
design has a hard ceiling here.

The honest resolution is a hybrid — reference the `Record`-typed property (checked) and
supply the key separately (validated at emit, not at check):

```typespec
@Map.into(PersonBase.phones, #{ key: "primary" })
phone: Generics.QuestionPhone;
```

Still far better than today's fully stringly `field: "contacts.otherContacts.aor.name.firstName"`,
because the model-bound half breaks loudly when `PersonBase.phones` is renamed or
retyped. But it is a real caveat against the "everything is compile-checked" pitch, and
worth being upfront about.

### 10.4 What this implies for the deferred design

The mapping layer needs, at minimum:

| Construct | Purpose |
|---|---|
| `@Map.each(dest, #{ key: <member prop>, onCollision: "error" })` | array → keyed record with a derived key |
| `@Map.keyFormat(KeyCase.camel)` | declared, testable key normalization |
| `@Map.promote(dest, #{ select: … })` | the CG `primary` singleton, with an explicit selection rule |
| `@Map.into(recordProp, #{ key: "primary" })` | scalar → keyed collection (the common case) |
| `@Map.oneWay("reason")` + `require-inverse-or-oneway` | forces #5 to be declared, not assumed |

And it confirms two earlier decisions:

- Deriving both mapping directions from one declaration is only valid for the *simple*
  case. Collection pivots must be authored per-direction or explicitly marked one-way —
  which is why the build has to refuse to guess.
- Doing mappings **after** JSON Schema + UI is the right sequencing. Key Contacts proves
  the mapping layer is a genuinely harder design problem than the two layers we're
  generating now, and it deserves its own design pass rather than being bolted onto
  `@mapsTo`.

---

## 11. Structure: the canonical schema is well-formed; SGG's flat shape is a projection

Producing a flat UI over deeply-composed questions involves two independent axes. UI depth
and data depth are unrelated, and the second is a place where SGG's current design is
deliberately not inherited.

### 11.1 UI flatness: already free

Measured across every form with a UI-schema artifact:

```
sf424     ui-schema.json   max depth: 1   nested sections: 0
rr_sf424  ui-schema.json   max depth: 1   nested sections: 0
```

**SGG's UI is already deliberately flat: a section list, then fields. Zero nested sections
anywhere.** Even where numbering implies hierarchy — "8. Applicant Information",
"8e. Organizational Unit", "8f. Name and contact information…" — those are *siblings*.

This works because both UI targets address fields by **absolute pointer**: SGG's
`definition: "/properties/…"` and JSON Forms' `Control.scope: "#/properties/…"`. Neither
requires the UI tree to mirror the data tree. SF-424's section 21 draws 12 fields from
three different data depths into one flat section.

So the **SGG emitter** flattens the canonical UI tree into sections. This is a
target-specific projection, not a composition semantic — the canonical tree keeps its
structure so each block renders standalone (§13).

```typespec
@UI.section(Sf424Section.authorizedRepresentative)
aor: QuestionBank.Aor.QuestionAorDetails;      // its whole subtree lands flat in that section
```

Per-field section assignment — needed where SF-424 splits one question across sections 8,
8e, and 8f — is just another key in the override table from §5.4. There is no separate
separate grouping construct: a section *is* a named group, usable at any block level (D9).

And the renderer genuinely does not care about depth: `applyFormUtils.ts:527`'s
`jsonSchemaPointerToPath` is a generic pointer→path conversion that strips `.properties`,
so a nested schema with matching nested pointers renders identically to a flat one.

### 11.2 Data shape: do not reproduce SGG's flat schema

SF-424's golden schema is **58 root properties**. One semantic question is smeared across
several with no consistent rule:

| | |
|---|---|
| `authorized_representative` | a `person_name` object |
| `authorized_representative_title` / `_phone_number` / `_fax` / `_email` | prefixed root scalars |
| `aor_signature`, `date_signed` | root scalars, different naming entirely |
| contact person: `contact_person`, `contact_person_title` | prefixed… |
| …but `email`, `fax`, `phone_number` | **unprefixed** root scalars |

That is the XSD wire format leaking into the data model. Reproducing it in the authored schema
would make the legacy shape the published artifact, and every downstream consumer would inherit
it. The canonical schema therefore does not match it; a projection reconciles the two (§11.4).

**The canonical schema is semantically nested:**

```typespec
@UI.section("authorized_representative", "21. Authorized Representative")
aor: QuestionBank.Aor.QuestionAorDetails;   // { name: {...}, title, phone, fax, email, signature, dateSigned }
```

Reshaping data is a *mapping* concern, and it belongs in the mapping layer — exactly where
`mapsTo` / `mapsFrom` already live.

### 11.3 What the reshape actually costs

Being precise, because three things break and each needs an answer:

| Breaks | Answer |
|---|---|
| Byte-parity with the golden JSON Schema and UI schema | a **projection** (§11.4) |
| The passthrough XML transform, which maps from the flat shape | the same projection, applied before XML generation |
| Stored application answers, which are in the flat shape | SGG's existing form versioning — a reshaped form is a new **major** version, old applications stay pinned |

The third is worth dwelling on: `forms/<form>/<major>/<minor>/` and the `sgg_version` field
already exist, and `forms/README.md` documents that "the old version stays in place for any
competitions still pinned to it." So reshaping is a version bump using machinery that is
already there — not a migration.

### 11.4 The projection artifact

A per-form declarative map from canonical paths to legacy names, emitted as its own
artifact and read **only** by the SGG target:

```jsonc
// dist/forms/sf424/projection.sgg-legacy.json
{
  "target": "sgg-legacy-flat",
  "map": {
    "aor.name":       "authorized_representative",
    "aor.title":      "authorized_representative_title",
    "aor.phone":      "authorized_representative_phone_number",
    "aor.fax":        "authorized_representative_fax",
    "aor.email":      "authorized_representative_email",
    "aor.signature":  "aor_signature",
    "aor.dateSigned": "date_signed",
    "contact.name":   "contact_person",
    "contact.title":  "contact_person_title",
    "contact.phone":  "phone_number",
    "contact.fax":    "fax",
    "contact.email":  "email"
  }
}
```

Authored as override keys, alongside presentation — which is a satisfying convergence:
**one override table, some keys for presentation, some for projection.**

```typespec
@UI.overrides(#{
  `name`:       #{ legacy: "authorized_representative" },
  `title`:      #{ legacy: "authorized_representative_title" },
  `phone`:      #{ legacy: "authorized_representative_phone_number" },
  `signature`:  #{ legacy: "aor_signature" },
  `dateSigned`: #{ legacy: "date_signed" },
})
@UI.section("authorized_representative", "21. Authorized Representative")
aor: QuestionBank.Aor.QuestionAorDetails;
```

The collision and completeness checks from the deleted `@mount` design are not lost, just
relocated to where they belong:

| Rule | Catches |
|---|---|
| `projection-incomplete` | a canonical leaf with no legacy name |
| `projection-collision` | two canonical paths mapping to the same legacy name — a live risk, since SF-424's AOR prefixes `email` but its contact person does not |
| `projection-orphan` | a legacy name in the golden that nothing maps to — i.e. a field we dropped |

### 11.5 Why this is not `@UI.mount(flat)` with extra steps

The information is the same; the containment is not.

- `@UI.mount(flat)` deforms the **canonical** artifact. The legacy shape becomes what we
  author, publish, and hand to every consumer. Portability is lost at the source.
- A projection leaves the canonical artifact clean and confines the legacy shape to one
  clearly-labeled adapter artifact that only the SGG target reads. Delete SGG, delete the
  projection file, and the bank is untouched.

That is the same reasoning as `api/src/services/common_grants/` — a clean kernel plus a
translation layer — applied consistently. It also puts SGG's flat schema in its proper
place: **one build target among several**, exactly like RJSF-vs-JSON-Forms for the UI layer
and the grants.gov XSD for the wire layer. Not the data model.

### 11.6 Two consequences

**1. The deferred mapping layer is load-bearing, not garnish.** Without a projection we
cannot emit anything that runs inside SGG. But the *first* mapping to build is not
CommonGrants — it is canonical → SGG-legacy, which is far simpler: pure renaming and
re-nesting, no enum crosswalks, no `Record<T>` keying, no promoted singletons, and
trivially invertible because it is a bijection over leaf paths. So the hard mapping design
work (§10) stays deferred while the easy, load-bearing slice comes forward.

**2. `$ref` scanning is sufficient for the three tables.** Because composites remain nested,
a form's `$ref` targets recover the composite questions it uses directly. Recording provenance
in `manifest.json` is optional reinforcement rather than a requirement.

### 11.7 Sequencing impact: none for the canary

Key Contacts' golden schema is already well-formed — `applicant_organization_name` plus
`key_contacts[]` whose items nest `name` and `address` as objects. Its projection is close
to the identity function. So the Phase 0 canary is unchanged, and the projection machinery
lands with SF-424, which is already scheduled third precisely because it stresses this
material hardest.

---

## 12. Rules, by example

Key Contacts has no rules (`form_rule_schema=None`), so these examples come from SF-424,
whose real rule schema and conditional blocks are the reference below. Two of the five
kinds are **in scope**; three are **deferred and pass through** (§6, §8).

### 12.1 Conditional requiredness — IN SCOPE

The golden has six `if`/`then` blocks. Three representative ones:

```json
"allOf": [
  { "if":   { "properties": { "application_type": { "const": "Revision" } },
              "required": ["application_type"] },
    "then": { "required": ["revision_type", "federal_award_identifier"] } },

  { "if":   { "properties": { "revision_type": { "const": "E: Other (specify)" } },
              "required": ["revision_type"] },
    "then": { "required": ["revision_other_specify"] } },

  { "if":   { "properties": { "applicant_type_code": { "contains": { "const": "X: Other (specify)" } } },
              "required": ["applicant_type_code"] },
    "then": { "required": ["applicant_type_other_specify"] } }
]
```

Authored:

```typespec
/** Type of application */
@UI.label("Type of Application")
applicationType: ApplicationType;

/** Revision Type */
@UI.label("Revision Type")
@Validation.requiredWhen(SF424.applicationType, ApplicationType.Revision)
revisionType?: RevisionType;

/** Other Explanation */
@UI.label("Other Explanation")
@Validation.requiredWhen(SF424.revisionType, RevisionType.OtherSpecify)
revisionOtherSpecify?: string;

/** Federal Award Identifier */
@UI.label("Federal Award Identifier")
@Validation.requiredWhen(SF424.applicationType, ApplicationType.Revision)
@Validation.requiredWhen(SF424.applicationType, ApplicationType.Continuation)
federalAwardIdentifier?: string;

/** Type of Applicant */
@UI.label("Type of Applicant")
applicantTypeCode: ApplicantType[];

/** Other (specify) */
@Validation.requiredWhen(SF424.applicantTypeCode, ApplicantType.OtherSpecify)   // array → `contains`
applicantTypeOtherSpecify?: string;
```

Three things the emitter handles that authors currently have to remember:

1. **The `required: ["<source>"]` guard inside every `if`.** `forms/README.md` has to
   *teach* this ("Required here makes it so the rule only runs if `my_select_field` is
   set, which avoids some odd behavior otherwise"). Encoded once in the emitter.
2. **Array sources become `contains`, scalars become `const`.** Derived from the
   property's type, not from the author choosing the right JSON Schema keyword.
3. **Merging.** Two `@requiredWhen` on `federalAwardIdentifier` with different source
   values become two separate `allOf` entries; two fields sharing one condition
   (`revisionType` + `federalAwardIdentifier` both on `application_type == Revision`)
   merge into one entry with a two-element `then.required`. The golden does exactly this
   merge, and getting it wrong is a parity failure rather than a behavior change — which
   is precisely the kind of thing an emitter should own.

`RevisionType.OtherSpecify` is an enum member whose value is `"E: Other (specify)"`, so
the literal is checked. Today it's a bare string appearing in the JSON Schema, the UI
rule (as the regex `^E: Other`), and the enum list — three places, no cross-check.

### 12.2 Conditional visibility — IN SCOPE, and notably unused here

Worth flagging: **SF-424 has no `conditional` blocks in its UI schema at all.**
`revision_type` and `revision_other_specify` are always visible; only their
*requiredness* changes. So:

> The emitter must not infer visibility from requiredness. `@requiredWhen` emits JSON
> Schema only. Visibility is a separate, explicit `@visibleWhen`.

Conflating them is an easy and invisible mistake — it would render a form that looks
right and behaves differently from grants.gov. Where visibility *is* wanted (the R&R
address components use it), it's declared:

```typespec
@UI.label("Province")
@UI.visibleWhen(QuestionAddress.country, CountryCode.OutsideTheUS)
province?: string;
```

emitting to SGG's vocabulary:

```json
{ "type": "field", "definition": "/properties/address/properties/province",
  "conditional": {
    "when": { "op": "notEquals",
              "ref": { "scope": "root", "pointer": "/properties/address/properties/country" },
              "value": "USA: UNITED STATES" },
    "then": { "visible": true }, "otherwise": { "visible": false } } }
```

and to JSON Forms:

```json
{ "type": "Control", "scope": "#/properties/address/properties/province",
  "rule": { "effect": "SHOW",
            "condition": { "scope": "#/properties/address/properties/country",
                           "schema": { "not": { "const": "USA: UNITED STATES" } } } } }
```

One declaration, two renderer vocabularies, guaranteed consistent. This is the concrete
version of the portability claim.

### 12.3 Display-only fields — IN SCOPE

The golden marks system-populated fields `type: "null"` rather than `"field"`:

```json
{ "definition": "/properties/total_estimated_funding", "type": "null" }
{ "definition": "/properties/aor_signature",           "type": "null" }
{ "definition": "/properties/date_signed",             "type": "null" }
```

```typespec
@UI.readOnly
@UI.label("Total Estimated Funding")
totalEstimatedFunding?: MonetaryAmount;
```

`@readOnly` → `type: "null"` in SGG, `options.readonly` in JSON Forms. Note this is
*static* read-only; `@UI.readOnlyWhen(...)` is the conditional form, which maps to SGG's
`conditional.interaction: "readOnly"`.

### 12.4 Calculations — generated, with derived ordering

The rule schema records calculations like this:

```json
"total_estimated_funding": {
  "gg_pre_population": {
    "rule": "sum_monetary",
    "fields": ["federal_estimated_funding", "applicant_estimated_funding",
               "state_estimated_funding",   "local_estimated_funding",
               "other_estimated_funding",   "program_income_estimated_funding"]
  }
}
```

Authored with property references rather than a string array:

```typespec
@UI.readOnly
@Validation.computed(Op.Sum, #[
  SF424.federalEstimatedFunding, SF424.applicantEstimatedFunding,
  SF424.stateEstimatedFunding,   SF424.localEstimatedFunding,
  SF424.otherEstimatedFunding,   SF424.programIncomeEstimatedFunding,
])
totalEstimatedFunding?: MonetaryAmount;
```

Renaming a contributing field is then a compile error rather than a silently wrong total.

**Ordering is derived, never authored.** SF-424A carries this today:

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

That integer asserts a dependency the reference graph already describes. `@Validation.computed`
takes property references, so evaluation order is computed and cycles are detected (§4.3 of the
specification).

**Scale.** 63 calculation entries across 4 forms — `sum_monetary` 44, `subtract_monetary` 18,
`multiply_by_percentage` 1 — with SF-424A holding 35 of the sums. `Op` therefore needs `Sum`,
`Subtract`, and `PercentOf`.

**Two reference forms are required**, both already present in SGG's vocabulary:

| SGG spelling | Meaning | Ref form |
|---|---|---|
| `@THIS.personnel_amount` | sibling within the same array item | `scope: item`, `ancestor: 0` |
| `activity_line_items[*].budget_summary.federal_new_or_revised_amount` | aggregate down every array element | array projection |

Together these make SF-424A a two-dimensional spreadsheet: row totals across columns, column
totals down rows, and grand totals over other totals.

### 12.5 SGG's remaining rule names — quarantined

Three tiers, ordered by authoring surface. Full specification:
[`architecture.md` §4.5](./architecture.md).

**Tier 1 — inferred from the property's type.** `gg_validation: {rule: "attachment"}` is emitted
for every attachment-typed property (~34 entries, 1 rule name). `forms/README.md` currently
teaches this as a convention authors must remember; it becomes an emitter behavior instead.

**Tier 2 — inferred from question identity.** `current_date` and `signature` post-population
(~26 entries, 2 rule names). Both already exist as shared schema fields, so they become bank
questions and the emitter infers the stamp from which question a property uses.

**Tier 3 — declared.** Only external lookups (~15 entries, 8 rule names), all resolving to the
opportunity or the organization profile:

```typespec
@@Sgg.prePopulate(SF424, #{ `agencyName`: SggPrePop.agencyName })
agencyName?: string;
```

Contained by: its own namespace, its own artifact (`sgg/rule-schema.json` only), a generated
closed enum, a `no-sgg-in-bank` lint rule restricting it to `specs/forms/`, a documented
successor per member, a CI census, and separate versioning as `sgg-legacy/v1`.

The `rules-sgg` emitter produces all three tiers plus the calculations in one pass, so the rule
schema has a single producer and the adapter passes it through rather than merging into it.

### 12.6 Summary of rule coverage

| Kind | Example | Lands in | Authoring surface |
|---|---|---|---|
| Conditional requiredness | `application_type == Revision` → `revision_type` | JSON Schema `if/then` | `@Validation.requiredWhen` |
| Conditional visibility | `country != USA` → show `province` | UI `conditional` / JSON Forms `rule` | `@UI.visibleWhen` |
| Static read-only | `total_estimated_funding` | UI `type: "null"` | `@UI.readOnly` |
| Conditional read-only | — | UI `conditional.interaction` | `@UI.readOnlyWhen` |
| Calculation | `sum_monetary` over 6 fields | rule schema | `@Validation.computed` |
| Attachment validation | `attachment` | rule schema | none — inferred from type |
| Submit stamps | `current_date`, `signature` | rule schema | none — inferred from question |
| External lookups | `uei`, `agency_name` | rule schema | `@Sgg.prePopulate` |

The dividing line is **intrinsic versus target-specific**. A calculation is a property of the
form in any renderer and any language, so it is authored canonically. External lookups reach
outside the form — to an organization profile, an opportunity, or the clock — and carry the
target's assumptions, so they sit in a separate namespace with a lint boundary and a census.
Both are emitted by the same pass, so the rule schema has one producer.

---

## 13. Blocks: the unit of composition (D9)

A bank question emits its own UI schema, because the CommonGrants browser renders each question
standalone. Questions and forms therefore have identical artifact requirements, and both are
modelled as one thing.

### 13.1 The model

A **block** is a JSON Schema + a UI schema + its conditional logic. That is all a question
is, and all a form is. One decorator decides which:

```typespec
@Question.meta("poc/details")                        // → the bank, $ref-able, question catalogue
@Form.meta(#{ formId: "f140c7db-…", legacyFormId: 683, … })   // → a deliverable form
```

Everything else — `@UI.*`, `@Validation.*`, `@Catalog.*`, later `@Map.*` — applies identically
to both.

This isn't a new idea being imposed on the consuming site; it's a shape the site already
assumes. `website/src/lib/catalog/types.ts` defines one `CatalogItem`
(`{ id, name, description, tags, rawSchema }`) that both question-bank and form items extend,
and `website/src/lib/question-bank/loader.ts` already reads `uiSchema` per question.

### 13.2 A block is a Model or a Scalar

A question holding several values is a Model (`generics/address`, `poc/details`); a question
holding one is a Scalar (`generics/phone`, `generics/email`, `generics/organization-name`,
`generics/contact-title`) — roughly half the bank:

```typespec
/** Enter the legal name of the organization. */
@Question.meta(#{ id: "generics/organization-name" })
@Catalog.tag(TagName.organization, TagName.name)
@UI.label("Organization Name")
scalar OrganizationName extends string;
```

A scalar block emits a leaf `schema.json` and a single Control rather than an object and a
Group. A property composing one still emits a `$ref`, which is what keeps `generics/phone` one
shared definition across every form asking for a phone number.

**Extending a block inside a form uses `extends`.** `is` copies the base's decorators including
`@Question.meta`, so the extension would claim the bank question's identity and the two would
collide on one output path. `extends` leaves identity alone, emits `allOf: [{ $ref: <base> }]`
plus the extension's own properties, and — carrying no `@Question.meta` — is inlined into the
referencing form's `$defs`, matching the golden's
`items: { $ref: "#/$defs/key_contact_person" }`.

### 13.3 Every block emits the same three artifacts

```
dist/question-bank/v1/generics/person-name/{schema,ui,index}.json
dist/question-bank/v1/poc/details/{schema,ui,index}.json
dist/forms/key-contacts/{schema,ui,index}.json
                        + projection.sgg-legacy.json   ← form-only
                        + sgg/{json-schema,ui-schema}.json
                        + manifest.json
```

The first three are identical in kind at every level.

### 13.4 Scopes are relative to the block's own root

`generics/person-name/ui.json` — renders standalone in the browser:

```json
{
  "$id": ".../question-bank/v1/generics/person-name/ui.json",
  "type": "Group",
  "label": "Person Name",
  "elements": [
    { "type": "Control", "scope": "#/properties/prefix",     "label": "Prefix" },
    { "type": "Control", "scope": "#/properties/firstName",  "label": "First Name" },
    { "type": "Control", "scope": "#/properties/middleName", "label": "Middle Name" },
    { "type": "Control", "scope": "#/properties/lastName",   "label": "Last Name" },
    { "type": "Control", "scope": "#/properties/suffix",     "label": "Suffix" }
  ]
}
```

`poc/details/ui.json` — the same operation one level up. Each child's tree is embedded and
its scopes re-prefixed:

```json
{
  "$id": ".../question-bank/v1/poc/details/ui.json",
  "type": "Group",
  "label": "Point of Contact",
  "elements": [
    { "type": "Group", "label": "Person Name",
      "elements": [
        { "type": "Control", "scope": "#/properties/name/properties/prefix",    "label": "Prefix" },
        { "type": "Control", "scope": "#/properties/name/properties/firstName", "label": "First Name" },
        "… middleName, lastName, suffix …"
      ] },
    { "type": "Control", "scope": "#/properties/title", "label": "Title" },
    { "type": "Group", "label": "Address",
      "elements": [
        { "type": "Control", "scope": "#/properties/address/properties/street1", "label": "Street 1" },
        "… street2, city, county, state, province, country, zipCode …"
      ] },
    { "type": "Control", "scope": "#/properties/phone", "label": "Telephone Number" },
    { "type": "Control", "scope": "#/properties/fax",   "label": "Fax Number" },
    { "type": "Control", "scope": "#/properties/email", "label": "Email" }
  ]
}
```

`forms/key-contacts/ui.json` applies the identical operation again, wrapping
`KeyContactPerson` (which wrapped `poc/details`, which wrapped `generics/person-name`). Four
levels, one operation.

**That operation is `rescopeUi` in `website/src/lib/forms/compose.ts`** — about 15 lines,
already written, already correct. Earlier I proposed porting it as an incidental helper; under
D9 it is the core of the UI emitter.

### 13.5 The SGG target flattens all of it

The canonical tree above is 3 levels deep. SGG's vocabulary is max depth 1, so
`sgg/ui-schema.json` flattens it:

```json
[{ "type": "section", "name": "key_contacts", "label": "Key Contacts",
   "children": [
     { "type": "field", "definition": "/properties/applicant_organization_name" },
     { "type": "fieldList", "name": "key_contacts", "label": "Key Contact",
       "children": [
         { "type": "field", "definition": "/properties/key_contacts/items/properties/project_role" },
         { "type": "field", "definition": "/properties/key_contacts/items/properties/name/properties/prefix" },
         "… every leaf, flat …"
       ] }
   ] }]
```

**Composition is a tree; flattening is a target concern.** The canonical UI composes as a
tree, because a block must render standalone — this is also the CommonGrants form library's
default, and it is correct. Flattening is what the SGG emitter does, for the same reason the
projection exists: a target's limitations are the target's business, not the model's.

### 13.6 What actually differs

| | Question | Form |
|---|---|---|
| identity | `@Question.meta` | `@Form.meta` |
| runtime metadata (UUID, `legacyFormId`, `ombNumber`, `formType`, version) | — | yes |
| `schema.json` / `ui.json` / `index.json` | yes | yes |
| `$ref`-able from another block | yes | yes |
| SGG projection + `sgg/` artifacts | — | yes |
| becomes a `Form` row in SGG | — | yes |
| catalogue | question bank | forms |

**A form is a question with runtime metadata and a delivery target.** Which is exactly why
"forms are configurable collections of questions" works — a form embedding a question is the
same operation as a question embedding a question.

### 13.7 Consequences

1. **A form can be `$ref`'d into another form.** This is how form *families* are expressed —
   SF-424 and SF-424 Short sharing a core, the four SF-424 assurance variants — and how
   multi-form flows compose.
2. **The association table is a transitive closure** over `$ref` edges, so "directly composes"
   and "ultimately contains" come from one graph and similarity can be computed at either
   granularity. Direct overlap measures how alike two forms look to an author; transitive
   overlap measures how much underlying data they share.
3. **A single granularity throughout.** Blocks compose blocks at every level, so no separate
   notion of primitive versus composite is required in the artifacts or the analysis graph.
