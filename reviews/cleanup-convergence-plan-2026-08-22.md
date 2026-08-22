---
type: Architecture Review
title: Cleanup and convergence plan after independent review
description: >-
  Independent review findings and the minimal preservation-first path from PRs
  #44 and #46 to one scalable architecture.
tags:
  - architecture
  - cleanup
  - convergence
superbee_updated_by: codex
---
# Recommendation

Treat merged PR #46 as a provisional contract checkpoint, not a frozen architecture. Pause additional form expansion until the contract is produced by TypeSpec, consumed independently of both TypeSpec and Simpler, exercised through the real Simpler form-processing path, and stress-tested with the R&R Budget family.

Preservation precedes cleanup. Do not close PRs #8–36, delete branches, or remove either authoring path until a generated inventory records every unique source, oracle, mapping, test, commit, hash, and intended destination.

# Independent review findings

Two read-only reviewers challenged the cleanup proposal against the bundle, PRs #44 and #46, and the current code. Their feedback converged on the following:

- The four-stage roadmap is sound but lacked an explicit preservation and consolidation phase.
- The bundle should reuse existing tasks and add only the few missing gates.
- PR #46 establishes a useful shared seam, but the v1 contract still needs producer and runtime proof before it governs portfolio migration.
- Portable metadata currently includes target-shaped fields such as `legacy_form_id`, `short_form_name`, and `agency_code`; their ownership must be decided rather than assumed.
- Occurrence identity, provenance, review events, and repeated same-question/same-role occurrences need a precise contract-level representation.
- UI, conditions/calculations, mappings, and projection payloads need versioned semantic profiles rather than opaque artifact envelopes alone.
- Canonical nested paths versus Simpler's flat snake_case paths and projection ownership remain unresolved.
- Copying the existing Python kernel into another directory proves relocatability, not an independent consumer.
- Runtime-required compact generated artifacts, canonical source, and large analytical/oracle artifacts require three distinct storage policies.
- PR #44 should be decomposed into bounded evidence-backed verticals rather than merged wholesale.

# Critical path

1. Inventory and preserve the 28-form corpus and draft PR evidence.
2. Resolve semantic identity and harden the provisional artifact contract.
3. Make authored JSON and TypeSpec emit the same Key Contacts contract semantics.
4. Validate with a genuinely independent consumer and the real Simpler registry, resolver, processing, validation, rendering, and XML path.
5. Prove R&R Budget and one sibling without form-specific compiler or adapter branches.
6. Record one canonical authoring and artifact-publication decision.
7. Consolidate directories, compilers, catalogs, and the superseded PR stack.
8. Run a ten-form throughput wave with no form-specific kernel or adapter changes.

# Authority

The board is authoritative for decisions, tasks, dependencies, and evidence context. Git is authoritative for code, contracts, and tests. CI is authoritative for build status and generated form metrics. Form counts and the 28-form disposition report should be generated rather than manually maintained.

[applies](pr44-current-kernel-convergence.md)

[applies](portable-artifact-contract-v1.md)

[coordinates](../roadmaps/declarative-form-architecture.md)
