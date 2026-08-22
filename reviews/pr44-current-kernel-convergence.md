---
type: Architecture Review
title: 'PR #44 and current kernel convergence review'
description: >-
  Working comparison and acceptance gates for converging the two declarative
  approaches.
tags:
  - architecture
  - review
  - convergence
superbee_updated_by: codex
---
# Architecture comparison and convergence criteria

This review compares the current `mirror-base` declarative kernel with Billy Daly's draft PR #44 and the three attached design documents. It is a working review, not a decision that one branch supersedes the other.

## Where the approaches agree

- Questions and forms are declarative, portable sources rather than form-specific Python builders.
- Standard JSON Schema `$ref` composition makes reuse visible and machine-queryable.
- UI, validation/behavior, mappings, metadata, and provenance remain separable concerns.
- Simpler consumes the portable definition through a generic adapter at an existing hardened boundary.
- Analysis is derived from canonical identities and occurrence bindings, not maintained separately.
- Existing runtime behavior and parity evidence are preserved during incremental migration.
- Similar wording or structure does not by itself prove semantic equivalence.

## What PR #44 adds

- A typed TypeSpec authoring library with compile-time diagnostics, linter rules, and generated artifacts.
- Recursive “block” composition in which both questions and forms emit schema, UI, and catalog artifacts.
- A canonical nested model with a consumer-owned projection into Simpler's legacy flat shape.
- Generic derivation of UI, requiredness, calculations, ordering, attachment validation, and submit stamps.
- A four-form proof spanning contacts, a wide application form, a budget/calculation form, and a near-neighbor form.
- An early reuse curve that reaches zero new questions for SF-424 Short.

## What the current kernel adds

- A language-neutral JSON authoring option that does not make TypeSpec mandatory.
- Exact occurrence bindings with roles, cardinality/context, review lifecycle, and direct source provenance.
- A neutral loader and analysis projector that can operate outside Simpler.
- A single immutable resolved-package seam into the existing runtime.
- Separation of proposed, accepted, and publishable overlap metrics.
- A policy that large resolved oracles and analysis exports are build artifacts rather than permanent runtime-repository source.

## Reconciliation questions for the architecture, not named people

1. What exact versioned artifact contract can both JSON and TypeSpec authoring compile to?
2. Which semantics must be visible through standard `$ref`, and which belong in occurrence sidecars?
3. How does the canonical block graph preserve role-qualified semantic identity without confusing shared validation shape with shared meaning?
4. Which target artifacts are generated mechanically, and which target-specific declarations belong only in the Simpler adapter?
5. How will the canonical-to-Simpler projection remain bijective, source-pinned, and independently testable?
6. Which authored sources stay in Git, and which large resolved/parity/analysis outputs are CI artifacts?
7. What is the minimal multi-consumer conformance suite that proves the build contract is independent of TypeSpec and Simpler?

## Proposed convergence gates

1. Freeze the portable artifact contract before scaling either authoring syntax.
2. Compile the same two reference forms from the selected canonical inputs through one neutral validator and one Simpler adapter.
3. Demonstrate an independent consumer that loads, resolves, validates, and traverses the same artifacts without importing Simpler or TypeSpec.
4. Preserve exact question occurrences, roles, source evidence, and mapping review states in the analytical projection.
5. Prove projected Simpler schema, UI, rules, and XML behavior against existing oracles, with explicit exceptions.
6. Generate analysis and large parity evidence in CI and publish them as build artifacts.
7. Add the next form only after it requires no new form-specific compiler or adapter branch.

## Current recommendation

Use PR #44 as a serious architecture candidate and evidence source, not as an automatic merge. Retain its typed authoring and recursive block ideas. Converge them with the current kernel's neutral contract, occurrence model, review lifecycle, provenance, and artifact-publication boundary. The first shared milestone should be a small contract-and-conformance PR; form expansion follows from that common base.

[reviews](../architecture/billy-proposed-form-architecture.md)

[reviews](../architecture/billy-proposed-authoring-model.md)

[reviews](../architecture/billy-deferred-designs.md)

[applies](../evidence/billy-form-architecture-oracle-2026-08-21.md)
