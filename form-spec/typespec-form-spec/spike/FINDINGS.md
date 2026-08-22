# Phase 0 spike results

Run against `@typespec/compiler` 1.15.0. Spec `spike/spike.tsp`, compiles clean.

## Confirmed

| # | Question | Result |
|---|---|---|
| 1 | `ModelProperty` as a **non-target** decorator parameter, via a member expression | **Works.** `@UI.visibleWhen(QuestionAddress.country, CountryCode.outsideUs)` and `@Validation.requiredWhen(...)` both resolve and reach the JS implementation as a `ModelProperty`. |
| 2 | `valueof EnumMember` as a decorator argument | **Works.** `@UI.section(SpikeSection.contacts)`. |
| 3 | Enum-member reference **inside an object literal** | **Works.** `#{ section: SpikeSection.orgUnit, widget: WidgetName.Text }` in the override table. |
| 4 | `$ref` composition survives emission | **Works, recursively.** A composed model property emits `$ref` to the child block's own schema file, at every level. |

Spike 4 output:

```yaml
# SpikeForm.yaml
properties:
  contact: { $ref: QuestionPocDetails.yaml }
# QuestionPocDetails.yaml
properties:
  name:    { $ref: QuestionPersonName.yaml }
  address: { $ref: QuestionAddress.yaml }
```

## Corrections the spike forced

1. **`op` is a TypeSpec keyword.** A decorator parameter named `op` breaks the *parser*, with a
   misleading `')' expected` error. `@Validation.computed` takes `operator` instead.
2. **Reflection types need `using TypeSpec.Reflection;`.** `Model`, `ModelProperty`, `Enum`, and
   `EnumMember` are not globally visible.
3. **Qualified references inside a nested namespace resolve relatively.** Inside
   `namespace SimplerForms.UI`, writing `SimplerForms.WidgetName` resolves to
   `SimplerForms.SimplerForms.WidgetName`. Reference parent-namespace types unqualified.
4. **`valueof {}` rejects a populated object literal.** The override table's parameter must be
   `valueof Record<unknown>`.
5. **Bare property names are not resolvable in decorator arguments.** `@UI.order(prefix,
   firstName)` fails with `Unknown identifier`; it must be
   `@UI.order(QuestionPersonName.prefix, QuestionPersonName.firstName)`.

Item 5 is the only one with design weight: `@UI.order` is materially more verbose than the
specification showed. Options are to accept the qualified form, to derive order from declaration
position and reserve `@UI.order` for exceptions, or to take `valueof string[]` and resolve names
in `$onValidate`. Deferred until the Key Contacts comparison shows how often order is overridden
at all.
