# Implementation findings

Validating the specification in `documentation/form-spec/` against the real Key Contacts
form. TypeSpec compiler 1.15.0.

## Verdict

**The approach is valid; no pivot is needed.** Key Contacts authors as ~60 lines of TypeSpec
composing seven bank questions, and the emitted artifacts reproduce the golden's structure —
including the exact 19-field order of the repeatable contact list and the address conditional
requiredness block.

## What the emitter does and does not own

`@typespec/json-schema` is **wrapped**, not replaced. Its `$onEmit` is exported, so ours calls
it into a staging directory, reads the result back, and composes. One emitter, one command, no
downstream merge script.

Everything derivable from the type graph comes from stock: types, constraints, enums, arrays,
`required`, `$ref` composition, and `extends` as `allOf`. Two decorators delegate rather than
duplicate:

| Ours | Delegates to | Yields |
|---|---|---|
| `@Question.meta` / `@Form.meta` | `@JsonSchema.id` | `$id` and every `$ref` target |
| `@UI.label` | `@summary` | `title` |

That leaves our schema contribution to exactly one thing stock cannot know: the `if`/`then`
conditional requiredness from `@Validation.requiredWhen`.

## Parity against the golden

| Artifact | Result |
|---|---|
| `generics/person-name` schema | Structural match: types, titles, descriptions, `maxLength`, `required` |
| `generics/address` conditionals | **Exact match**, including the merge of two `requiredWhen` declarations into one `if`/`then` and the `required: ["country"]` guard idiom |
| Key Contacts `sgg/ui-schema.json` | Section, `fieldList`, and the **exact 19-field order** including `project_role` first |
| Key Contacts `sgg/rule-schema.json` | `null` — matches the golden's `form_rule_schema=None` |
| `$defs` inlining | Form-local extensions land in `$defs` with a `#/$defs/key_contact_person` ref, as the golden does |

Byte-level parity is not yet assertable: it requires the canonical → legacy projection, which
is adapter-side and not built. The canonical artifacts are `camelCase` by design (D5).

## Corrections the implementation forced

### Design-level

1. **`model X is Y` copies decorators, including `@Question.meta`.** A form-local extension of
   a bank question silently inherits the question's identity, so two blocks claim one id and
   collide on the output path. **`extends` is the correct idiom** — it leaves identity alone and
   stock emits `allOf: [{$ref: base}]`, which is the composition wanted. The specification and
   `authoring-model.md` show `is` and must be corrected.

2. **The bank needs scalar questions.** `phone`, `email`, `organization-name`, `contact-title`
   are single values, not objects. `@Question.meta` was widened to `Model | Scalar`, and the
   emitters handle scalar blocks as leaf schemas and single Controls.

3. **No base URI is declared anywhere in the specs.** Hosting is a per-consumer decision, so
   `$id` and `$ref` are emitted relative and correct within the artifact tree; a consumer
   supplies `base-uri` at build time to make them absolute. A block's identity is its
   `@Question.meta.id`, never its URI, so the catalogue and the three tables are
   hosting-independent.

4. **Marshal at the decorator boundary, never in an emitter.** `valueof` arguments arrive as
   TypeSpec value objects with parent back-references; two separate `Converting circular
   structure to JSON` crashes came from carrying them into emission. Decorators now reduce every
   argument to plain data before storing it.

### Language-level

5. **`op` is a TypeSpec keyword.** A decorator parameter named `op` breaks the parser with a
   misleading `')' expected`. `@Validation.computed` takes `operator`.
6. **Reflection types need `using TypeSpec.Reflection;`.** `Model`, `ModelProperty`, `Enum`,
   `EnumMember` are not globally visible.
7. **Qualified references inside a nested namespace resolve relatively.** Inside
   `namespace SimplerForms.UI`, `SimplerForms.WidgetName` resolves to
   `SimplerForms.SimplerForms.WidgetName`. Reference parent-namespace types unqualified.
8. **`valueof {}` rejects a populated object literal.** The override table takes
   `valueof Record<unknown>`.
9. **Bare property names do not resolve in decorator arguments.** `@UI.order(prefix, firstName)`
   fails; it must be `@UI.order(Model.prefix, Model.firstName)`. Confirmed verbose, and the
   Key Contacts case genuinely needs it — the golden interleaves a form-local field between
   inherited ones, which is only expressible with an explicit order.
10. **`@UI.order` does accept inherited properties**, so a form-local extension can interleave
    its own fields with the question's. This was the untested spike; it passes.

## Confirmed from the original spikes

`ModelProperty` as a non-target decorator parameter via member expression; `valueof EnumMember`
arguments; enum-member references inside object literals; recursive `$ref` survival through
emission.

## Known gaps

- `@UI.helpText` is declared but not consumed, so a `fieldList` reuses the property's doc where
  the golden has a distinct description.
- Linter rules and diagnostics are declared but not implemented.
- No test suite yet; `createTester` scaffolding is not in place.
- The canonical → legacy projection and the SGG adapter are not built, so byte parity is
  unproven.
