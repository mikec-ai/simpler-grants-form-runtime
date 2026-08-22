---
type: Architecture Decision
title: 'Adopt PR #44 as the canonical form architecture'
description: >-
  PR #44 is the governing architecture; prior contract work is preserved
  evidence, not a parallel implementation.
tags:
  - architecture
  - decision
  - pr44
superbee_updated_by: codex-primary
---
# Decision

Billy Daly's PR #44 architecture and its three design documents are the governing architecture for the grants form work. This is a directional choice, not a compromise between two canonical models.

The implementation base is private PR #44 at commit `32a1f2d7610019a6d77de673c9a3a49be49659a1`. TypeSpec is the first typed producer. The emitted JSON Schema, UI, catalog/index, rule, and adapter artifacts are the replaceable contract. Forms and questions compose recursively as semantic `$ref`-addressable blocks. Canonical data stays nested, camelCase, and target-neutral. Per-form legacy shape projection and other multiplicative Simpler knowledge stay in the Simpler adapter.

# Consequences

- New hardening starts from PR #44, not from `codex/contract-convergence`.
- Commit `1c7d83ca6` and contract v2 remain preserved experimental evidence and will not be merged into the governing implementation.
- Source snapshots, provenance verification, parity oracles, semantic-review judgments, and independent conformance tests may be ported only after they are expressed through PR #44's artifact graph and sidecar boundaries.
- Validation-shape reuse remains distinct from semantic question identity, but PR #44's published question `$ref` is the canonical identity. No second question-ID registry will be introduced.
- The current budget-family implementation remains a preserved control group until PR #44's hardening and reference-form sequence are complete.
- Target-specific `options.simpler`, legacy IDs, and runtime projection knowledge will not be added to canonical question-bank artifacts.

# Artifact ownership and publication

Three artifact classes have distinct owners:

1. Authoring sources and portable compiled targets are owned by the form-spec library. Reviewable authoring sources and the small deterministic artifacts required by consumers may be versioned with the library when PR #44's build contract requires them.
2. Simpler projections, legacy paths, runtime rule-name mappings, and XML integration are owned by the Simpler adapter. Compatibility is proven at that boundary without changing the existing frontend, validator, registry, or XML runtime.
3. Large parity oracles, resolved snapshots, analysis workbooks/tables, and review reports are generated build artifacts. They are published by CI with hashes and retention metadata rather than checked into the runtime repository. Immutable source evidence is retained in the private evidence repository and referenced by exact commit, path, and byte hash.

Rollback is branch- and tag-based. The PR #44 head, the earlier experiment branches, corpus tips, and source snapshot tags remain privately reachable until the replacement passes all conformance and parity gates. No prior branch or evidence is deleted merely because this decision selects a direction. Compatibility policy is fail-closed: each migrated form must prove applicant-visible rendering and submission validation parity through an explicit bijective projection, while known semantic disagreements remain review findings rather than hidden adapter exceptions.

# Delivery sequence

1. Establish PR #44's existing green checks as the baseline.
2. Complete artifact-level meta-schemas and conformance fixtures against the emitted graph.
3. Add remote-verifiable source provenance to package/index/evidence sidecars.
4. Add semantic review state to analysis sidecars, separate from parity status.
5. Add a hand-authored JSON producer fixture to prove TypeSpec is replaceable.
6. Close the remaining PR #44 findings through compiler, linter, and artifact-level checks.
7. Continue the PR #44 migration sequence one representative form at a time.

# Preserved context

This decision is [governed by](../architecture/guiding-principles.md) and adopts [Billy's proposed form architecture](../architecture/billy-proposed-form-architecture.md), [authoring model](../architecture/billy-proposed-authoring-model.md), and [deferred-design boundaries](../architecture/billy-deferred-designs.md). The earlier [convergence review](../reviews/pr44-current-kernel-convergence.md) remains useful evidence, but its prior undecided posture is superseded by this decision. Delivery is tracked by [the canonical authoring decision task](../tasks/record-canonical-authoring-decision.md).
