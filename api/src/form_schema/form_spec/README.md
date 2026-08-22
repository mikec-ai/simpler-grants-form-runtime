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

`tests/src/form_schema/form_spec/` asserts that a projected form matches its hand-written
original two ways: structurally, against an allow-list where every remaining difference is
named with a reason, and behaviourally, by validating a generated corpus of payloads
against both schemas and requiring identical verdicts. The second is the one that matters;
the first is what stops an accidental divergence from hiding inside it.
