# The form specification adapter

The declarative form specification lives in [`form-spec/`](../../../../form-spec). It
emits JSON artifacts — one schema per question, one per form, plus the UI and rule
schemas — and knows nothing about this codebase. This package is the boundary where
those artifacts are translated into the shapes the form runtime expects.

## What crosses the boundary

```
form-spec/dist/                                   canonical artifacts (camelCase, $ref)
  |
  |  scripts/sync_to_sgg.py                       vendored, with a digest per file
  v
form_spec/artifacts/
  |
  |  projection.py                                snake_case, allOf-wrapped, flattened
  v
form_spec/loader.py  ->  form_json_schema, form_ui_schema, form_rule_schema
```

`bank.py` assembles every question into one shared schema document and registers it with
`jsonschema_resolver`, so a form's `$ref` into the bank resolves offline exactly as
`common_shared_v1` already does. That registration is the only change this work makes to
existing runtime code, and it is one entry in one list.

## Why a projection exists at all

Four differences between the canonical artifacts and this codebase's contract, all of
them accommodations rather than design choices, and all of them documented in
`projection.py`: naming, `$ref` wrapping (the resolver discards a `$ref`'s siblings),
object composition flattened (the UI schema addresses fields by flat pointers that cannot
see through an `allOf` branch), and reference retargeting.

Keeping these here rather than in the specification is deliberate. A second consumer of
the same question bank — the CommonGrants question browser, a different renderer — will
want a different projection, and adding one should add a file here rather than change
anything upstream.

## Parity

`tests/src/form_schema/form_spec/` asserts two things about a projected form, and between
them they cover everything an applicant can perceive.

**What they read.** The UI schema's `definition` pointers enumerate what a form renders, so
each pointer is resolved in both schemas and the effective fields compared. Both steps the
renderer takes are taken first: the `jsonref` dereference that `form_template_registry` runs
at registration, then the `allOf` merge that `processFormSchema` runs before rendering.
Structural placement then stops mattering by construction -- where a `$defs` sits, whether a
reference is wrapped, which side of a reference a constraint lives on.

**What they may submit.** A corpus derived from the golden -- every field deleted, overrun,
emptied, mistyped, and given a value outside its enum -- validated against both schemas,
requiring identical issues.

There is deliberately no assertion about the *shape* of the JSON Schema. Asserting it
produced two hundred differences that all had to be explained, and a real regression once
hid among them: six fields lost their form-level description and the allow-list absorbed it.
