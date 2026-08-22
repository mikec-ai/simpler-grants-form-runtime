---
type: Architecture Review
title: Portable artifact contract v1 checkpoint
superbee_updated_by: codex
---
# Portable artifact contract v1 checkpoint

## Decision

The build artifact graph is the shared contract. TypeSpec, authored JSON, and a future form
builder are peer producers. No consumer may depend on the producer's language or AST.

The contract is one self-describing JSON Schema Draft 2020-12 document covering the authoring
catalog, individual form declarations, and the compiled runtime bundle. It requires exact source
evidence, reusable question descriptors, occurrence-level roles and cardinality, review states,
consumer adapter namespaces, and content-addressed artifacts.

## Implemented checkpoint

- All eight current declarative forms compile against the same contract.
- The generic compiler validates authored declarations and the compiled artifact graph before an
  atomic manifest write.
- The neutral kernel independently validates the same contract after its more precise semantic
  and provenance checks.
- Simpler-only IDs, type names, instruction IDs, runtime versions, and rule files are isolated in
  `adapters.simpler`; the portable metadata and semantic graph do not own them.
- Proposed, accepted, and publishable mappings remain distinct. Nothing in this checkpoint changes
  mapping acceptance or published coverage.
- Runtime oracles, parity packages, analysis exports, and workbooks remain generated CI artifacts,
  not runtime repository sources.

## Relationship to PR #44

PR #44's TypeSpec library is a candidate producer for this contract. Its recursive block model,
compile-time diagnostics, typed conditions/calculations, canonical nesting, and Simpler projection
are valuable inputs. It does not need to be merged as a competing runtime path. To conform, its
emitter must preserve the contract's exact occurrence bindings, source evidence, review lifecycle,
and adapter separation.

## Remaining convergence work

1. Implement a producer conformance fixture that emits the same reference form through authored
   JSON and TypeSpec and compares their contract-level semantics.
2. Reconcile canonical nested paths and the bijective Simpler legacy projection without moving
   target-shaped names into the portable layer.
3. Define portable typed conditions and calculations, then lower them generically into Simpler
   rules. Current `gg_*` rules remain explicitly adapter-owned until then.
4. Add the next form only when it requires declarations and reusable blocks, not a new compiler or
   adapter branch.

## Verification

The checkpoint has poison tests for contract drift, missing occurrence roles, invalid declaration
graphs, duplicate Simpler IDs at the consumer boundary, arbitrary new adapter namespaces, source
hash drift, and stale manifests. Focused runtime, compiler, analysis, and artifact tests remain the
merge gate.

[applies](pr44-current-kernel-convergence.md)

[documents](../tasks/define-portable-artifact-contract.md)
