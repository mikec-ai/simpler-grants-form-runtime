---
type: Context Note
title: 'Billy PR #44 architecture intake'
timestamp: '2026-08-22T13:30:00.000Z'
description: 'Source-pinned intake of PR #44 and the three attached architecture documents.'
tags:
  - architecture
  - pr44
superbee_updated_by: codex
---
# Summary

Billy Daly opened draft PR #44, `Declarative form authoring from a shared question bank (draft, for discussion)`, from `widal001/form-spec-question-bank` at commit `32a1f2d7610019a6d77de673c9a3a49be49659a1`. The PR is an additive architectural experiment against private `mirror-base`; it has not been merged and must not be treated as the selected design without reconciliation.

The PR authors four forms from a TypeSpec question bank: Key Contacts, SF-424, SF-424A, and SF-424 Short. It reports exact UI and rule parity, plus zero validation-behavior disagreements across 2,518 generated payload checks. It also reports a strong early reuse signal: SF-424 Short asks 23 named questions, adds none to the bank, and shares 91% of its questions with SF-424.

The strongest architectural contribution is the separation of a portable question/form graph from a thin Simpler adapter. The graph exposes reuse through standard JSON Schema references, uses typed declarative authoring, and derives analysis from emitted artifacts. TypeSpec is an authoring implementation, not the consumer contract.

The important unresolved boundaries are explicit in the PR: CommonGrants mappings and XML generation are deferred; conditional UI declarations are emitted but not yet exercised by the existing renderer integration; several SF-424 estimated-funding fields lack question identity; and the adapter tests do not yet run the complete production form-processing path.

The PR currently checks generated form and question artifacts into the runtime repository. Our working direction is different: canonical source declarations belong in source control, while large resolved oracles and analytical exports should be generated and published as build artifacts. That difference should be reconciled as an architecture decision rather than silently inherited.

## Attached source files

The versions received from Billy in Downloads on 2026-08-22 are preserved as editable Superbee documents:

- `architecture.md`: 84,180 bytes, SHA-256 `a4fefaeea879f50b2e1289a3254b49ded4549f8d3cf3b590ed89fdff1149984f`
- `authoring-model.md`: 60,537 bytes, SHA-256 `e044daa677d0a5ebb8dcc6f83c8f4a2dbdbac77975980377a7239cbea04d8de0`
- `deferred-designs.md`: 15,492 bytes, SHA-256 `dba39562f7e74f9faac186a520b89524f514e6ecff8f1dd22239bd4e58b63d64`

At PR commit `32a1f2d7`, the corresponding document hashes are `76069ad418a12f1784ba67a9eb69160986762ad953ce4860ea49b51f9fc6de7a`, `2dcd08bcbb28fc8b5dd0e846442da2e1fac431604bcb70f37c13239c19fe6f37`, and `dba39562f7e74f9faac186a520b89524f514e6ecff8f1dd22239bd4e58b63d64`. The deferred-design document is identical. The architecture and authoring-model attachments differ from the PR copies, so neither is silently declared newer or authoritative.

## Working interpretation

The durable target is a portable artifact contract with visible question reuse, declarative form composition, generic compilation, and consumer-specific adapters. TypeSpec can be a high-quality first authoring interface, but consumers must depend on emitted standards-based artifacts rather than TypeSpec. Our existing JSON-authored kernel and Billy's TypeSpec work are therefore inputs to one convergence exercise, not mutually exclusive products.

PR: https://github.com/mikec-ai/simpler-grants-form-runtime/pull/44

[records](../architecture/billy-proposed-form-architecture.md)

[records](../architecture/billy-proposed-authoring-model.md)

[records](../architecture/billy-deferred-designs.md)
