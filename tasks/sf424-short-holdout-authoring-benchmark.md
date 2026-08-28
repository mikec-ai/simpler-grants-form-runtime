---
type: Task
title: Prove agent authoring with an SF-424 Short holdout benchmark
priority: P0
assignee: codex-primary
description: >-
  Build and run a deterministic leave-one-form-out authoring benchmark that
  measures reuse and parity without leaking the existing SF-424 Short
  implementation.
superbee_progress_status: done
superbee_updated_by: codex-primary
generated:
  by: 'process:superbee'
  at: '2026-08-28T18:51:56.927Z'
---
Built and verified a repeatable leave-one-form-out benchmark using SF-424 Short as the first target. Preparation excludes the target package before reading portable packages, stages exact digest-bound extraction evidence, and supplies the agent with a question bank built from the other 38 forms. The withheld producer package is read only during scoring.

Final capabilities delivered on 2026-08-28:

- Generic target-excluded question-catalog preparation with a regression test proving the hidden target package is never read.
- Target-excluded reuse context carrying prior form, version, path, cardinality, dimensions, response role, and semantic review state.
- Provider-neutral agent recommendations with strict structured output and a controlled `propose-source-question` operation.
- Source-specific proposals are namespaced to the form, cite pinned evidence, compile as self-identifying JSON Schemas, and remain `semanticReview: proposed`.
- Generic numbered-slot projection: three SF-424 Short applicant-type XML slots compile into one array-valued `MultiSelect` answer with cardinality `one`; no form-specific compiler or renderer branch was added.
- Accepted-for-preview recommendations compile into a portable form package while `semanticAcceptanceGranted` remains false.
- Preserved benchmark run history records the baseline, reuse-context run, the first source-proposal correction cycle, and a conservative complete package.

Final checked-in complete-source run:

- 230 target-excluded reusable questions and 83 pinned source records.
- 30 proposed fields: 26 reusable-question proposals and four source-specific proposals.
- 20 of 23 reusable oracle occurrences matched directly; four additional reusable dependency questions matched.
- All four source-specific proposals land on real oracle property paths. Two cover the target-only concepts (`primary-org/website` and `project/description`); two expose applicant-facing inline fields absent from the oracle occurrence ledger.
- Zero unmatched source-specific proposals.
- Compiled preview passes the portable package validator with zero errors.
- All recommendations remain proposals; no published semantic coverage was increased.

Experimental finding:

- The preserved runs show model variability. The best run recovered 22 of 23 reusable occurrences (95.7% recall); the complete-source run recovered 20 of 23 (87.0%) while covering all four source-specific oracle paths. This supports a human review-and-selection workflow rather than treating one agent pass as deterministic truth.
- Implementation exposed two architecture rules that static mapping had not made concrete: an array-valued answer still has one question occurrence, and source-specific questions need portable schema identity/provenance even before semantic reconciliation.

Verification:

- Full repository gate passed: 487 Vitest tests, 74 agent-tool tests, exact 232-question catalog verification, TypeScript checks, all workspace builds, and the production browser bundle.
- Branch: `codex/sf424-short-holdout-benchmark`
- Pull request: https://github.com/mikec-ai/grants-form-workbench/pull/60
- Initial commit: `975b3e4` (`Add target-excluded form authoring benchmark`)
- Completion commit: `fca1f38` (`Complete agent-authored holdout preview`)
- Hosted CI run `33201194513` failed before executing any steps and produced no logs. The PR remains mergeable; the complete equivalent local gate passed.

Authoritative artifacts are under `benchmarks/sf424-short/`, with the harness at `scripts/holdout-benchmark.mjs`.
