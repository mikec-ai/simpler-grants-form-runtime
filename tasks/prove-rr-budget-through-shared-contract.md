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
  at: '2026-08-28T19:19:49.466Z'
---
[depends on](converge-reference-forms.md)

## Progress

The target-excluded R&R Budget holdout is complete as the first slice of this task. From 199 exact source records, the agent independently selected one existing reusable object, `budget/research/details`, at the RFC 6901 document root. The generic authoring, exchange, contract-validation, and renderer layers now support root composition without an artificial wrapper and without an R&R-specific branch.

The hidden-oracle evaluation preserves both measurements. The original oracle uses five top-level occurrences, so component-decomposition recall remains 0/5. The decomposition-neutral comparison shows all 6 top-level properties covered, identical required fields, and normalized structural parity after excluding only presentation text and relative reference depth. This is implementation evidence, not semantic acceptance: the reused component has two prior unreviewed occurrences and `semanticAcceptanceGranted` remains false.

Exact receipts are committed at `5efc201` on `codex/rr-budget-holdout-benchmark` and published in grants-form-workbench PR #61: https://github.com/mikec-ai/grants-form-workbench/pull/61. `benchmarks/rr-budget/` contains the pinned extraction and manifest, oracle-isolated request and receipt, agent recommendations, preview, the first wrapper run, and the score. Full repository verification passed: 491 Vitest tests, 76 agent-tool tests, typechecking, question-catalog integrity (232 questions), and all builds. Hosted run 33202974428 failed before executing any step (empty step list), so it provides no code-level failure signal.

A second shared-runtime slice is committed at `b41facd` and published in stacked PR #62: https://github.com/mikec-ai/grants-form-workbench/pull/62. Generic calculation `forEach` scopes now traverse nested arrays through wildcard segments while retaining bounded execution and fail-closed behavior. This supplies the missing runtime shape for period-level and nested-row R&R Budget calculations without adding form-specific code. Full verification passed with 493 Vitest tests and 76 agent-tool tests.

The source-resolved calculation projection is committed at `fc77000` and published in stacked PR #63: https://github.com/mikec-ai/grants-form-workbench/pull/63. A generic design-time projector now resolves exact source-ledger paths through the portable question schemas and emits one validated `form-behaviors/v1` artifact. It projects all 30 calculations that the pinned research ledger resolved: 10 within repeated personnel rows and 20 across budget periods. The same artifact executes over multiple periods and nested `keyPerson` and `other` rows without mutating input or adding an R&R-specific runtime branch. The source ledger's remaining 26 calculations are preserved as blocked rather than guessed.

The checked fixture is byte-identical to `grants-question-crosswalk` revision `b998b94fd4eadc4b84e466a8100540c894c82bc9`, path `artifacts/authoring/budget-runtime/RRBudget.runtime.json`, SHA-256 `d69f86e98bc188f25a18cab86b3dc98e53801ec7c7ae95325decb1a315b02282`. The projector fails closed on evidence drift. Its receipt explicitly retains `sourceReviewStatus: agent_proposed`, `semanticAcceptanceGranted: false`, and `publishedCoverageEligible: false`. Focused projection/runtime verification is green at 44 tests. A full repository run passed before the final source-drift guard was added; the post-guard full run reached 495 passing tests but encountered two unrelated UI timing failures, both of which passed immediately when rerun in isolation. No production code associated with those timing failures was changed. Hosted run `33205900392` failed before executing any step (empty step list), matching the existing account/infrastructure failure mode rather than supplying a code-level signal.

The repeated-row condition foundation is committed at `e584d40` and published in stacked PR #64: https://github.com/mikec-ai/grants-form-workbench/pull/64. The neutral behavior contract now supports explicit `present` predicates and row-scoped conditions over repeated and nested repeated collections. Execution returns each outcome with its exact indexed data pointer, the renderer preserves those instance receipts for consumer use, and capability preflight names this separately as `behavior.collection-condition`. Global calculation gates and UI effects are rejected for repeated conditions so one row's outcome cannot be incorrectly applied to an entire form.

The R&R Budget projection now contains 50 executable rules: the prior 30 calculations plus all 20 source-resolved requiredness predicates. Fourteen predicates run once per budget period; six run across nested repeated equipment and other-personnel rows. The 20 requiredness effects remain explicitly blocked with their exact relative targets until an instance-aware consumer binding exists. The source ledger has zero blocked condition predicates. Full repository verification passed with 499 Vitest tests, 76 agent-tool tests, typechecking, question-catalog integrity, and all builds.

## Remaining acceptance

The full P0 remains open. The 30 source-resolved calculations and 20 source-resolved condition predicates are projected and executable. The next consumer slice must bind each repeated condition outcome to the correct rendered row for field-level requiredness and validation. Remaining work also includes resolving or explicitly dispositioning the 26 blocked calculations, then proving ordering/UI parity, XML fidelity, the real Simpler consumer path, and a declaration-only sibling.
