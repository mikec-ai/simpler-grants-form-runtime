---
type: Task
title: Prove R&R Budget through the shared contract
priority: P0
assignee: codex-primary
description: >-
  Compile one difficult R&R Budget form and one sibling from the selected
  producer through the portable contract and real Simpler path. Acceptance:
  calculations, conditions, ordering, UI, validation, and XML retain parity; no
  form-specific emitter or adapter branch is added; the sibling is
  declaration-only.
superbee_progress_status: in_progress
superbee_updated_by: codex-primary
generated:
  by: 'process:superbee'
  at: '2026-08-28T19:13:07.252Z'
---
[depends on](converge-reference-forms.md)

## Progress

The target-excluded R&R Budget holdout is complete as the first slice of this task. From 199 exact source records, the agent independently selected one existing reusable object, `budget/research/details`, at the RFC 6901 document root. The generic authoring, exchange, contract-validation, and renderer layers now support root composition without an artificial wrapper and without an R&R-specific branch.

The hidden-oracle evaluation preserves both measurements. The original oracle uses five top-level occurrences, so component-decomposition recall remains 0/5. The decomposition-neutral comparison shows all 6 top-level properties covered, identical required fields, and normalized structural parity after excluding only presentation text and relative reference depth. This is implementation evidence, not semantic acceptance: the reused component has two prior unreviewed occurrences and `semanticAcceptanceGranted` remains false.

Exact receipts live on `codex/rr-budget-holdout-benchmark` in `benchmarks/rr-budget/`: pinned extraction and manifest, oracle-isolated request and receipt, agent recommendations, preview, the first wrapper run, and the score. Full repository verification passed: 491 Vitest tests, 76 agent-tool tests, typechecking, question-catalog integrity (232 questions), and all builds.

## Remaining acceptance

The full P0 remains open. Next slices must prove calculation and condition execution, ordering/UI/validation parity, XML fidelity, the real Simpler consumer path, and a declaration-only sibling.
