# Declarative authoring migration ledger

The six-form pilot began with form-specific Python migration scripts. Those scripts were useful
for reconciling pinned implementation oracles and proving the portable output contract, but they
also mixed mechanical compilation with semantic authoring decisions.

The canonical boundary is now JSON-first:

1. Exact source evidence and question descriptors live in `form-specs/catalog.json`.
2. Each form's question occurrences, roles, sidecars, and review boundary live in one hashed
   `form-specs/forms/*.form.json` declaration.
3. Standard JSON Schema `$ref` composition keeps reuse visible in the authored form schemas.
4. `scripts/compile_portable_form_bundle.py` mechanically assembles the runtime manifest.
5. The dependency-neutral kernel validates and analyzes that bundle; the thin Simpler adapter
   projects it into the existing runtime.

The removed migration scripts remain recoverable from Git history:

- `scripts/build_portable_budget_pilot.py`
- `scripts/build_portable_budget_composition.py`

Their generated declarations, source pins, runtime parity tests, analysis exports, and regression
oracles are preserved. This refactor changes the authority and review surface, not the six forms'
resolved behavior or analytical results.

Future form work should not add a form-specific compiler function. If a new form exposes a missing
capability, add a typed declarative construct and teach the generic compiler or adapter to process
that construct for every form.
