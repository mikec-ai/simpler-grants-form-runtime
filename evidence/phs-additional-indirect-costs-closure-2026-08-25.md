---
type: Release Evidence
title: PHS Additional Indirect Costs closure evidence
description: >-
  Exact producer, consumer, parity-repair, and browser receipts for the banked
  PHS Additional Indirect Costs form.
tags:
  - portable-form
  - parity
  - budget
superbee_updated_by: codex
---
# Outcome

PHS Additional Indirect Costs 2.0 now has an evidence-backed declarative producer package and a banked Simpler consumer handoff. The consumer uses only generic nested-list, calculation, preview, and XML machinery; it is intentionally not assigned a production runtime identity.

# Defects found during independent review

1. `costType` was required but did not preserve the official XSD's `minLength: 1`, so an empty value could pass the portable schema while failing the Grants.gov wire contract.
2. Period and cumulative sum rules materialized eagerly. A dates-only budget period could therefore manufacture an optional `indirectCosts` branch and a cumulative zero even though no funds were entered.

# Generic repairs

- Producer PR [#104](https://github.com/mikec-ai/grants-form-spec/pull/104) adds `@minLength(1)` and merged at `4b3b1d78a96ea8e501f51e6edbaa0190d67b9949`.
- Both calculations now use the existing generic `@Validation.materializeWhenAnySourcePresent` contract. Emitted rules preserve exact `presence_fields`; the cumulative total depends on materialized period totals rather than dates alone.
- The producer negative canary proves empty `CostType` fails the exact official XSD.
- Consumer regressions prove dates-only periods preserve absent optional branches and mixed periods contribute only materialized totals to the cumulative value.
- No form-specific compiler, adapter, renderer, or runtime branch was added.

# Exact receipts

- Original producer introduction: PR [#99](https://github.com/mikec-ai/grants-form-spec/pull/99), merge `893b0710ee69d8e3455b5c954e9071504a3a61b0`.
- Producer repair: PR [#104](https://github.com/mikec-ai/grants-form-spec/pull/104), merge `4b3b1d78a96ea8e501f51e6edbaa0190d67b9949`.
- Consumer handoff: PR [#108](https://github.com/mikec-ai/simpler-grants-gov/pull/108), merge `cbc34d2243148af3d0118e7c02017ec37dc55e30`.
- Final-head bounded browser receipt: run [#32816048379](https://github.com/mikec-ai/simpler-grants-gov/actions/runs/32816048379), green including the 1/1 E2E shard and merged report.
- Producer full preflight: 125 TypeScript tests; 363 Python tests with 10 skipped; 33 exact-XSD fixtures; 1,707 artifacts; zero unclassified fields or exceptions.
- Consumer focused/integrity verification: 26 tests passed; Black/isort and focused mypy passed. Independent re-review approved final semantics and isolation.
- Official form XSD SHA-256: `ba38a3500b025b0414edbcdbffe80dc12165ceb7a7fb657012d450b2e9682b66`.
- Exact DAT/XLS SHA-256: `b0d0411dbb9794ba031b45dfaa4a94f735aad42311409a77bf44a0810196d3dd`.

# Open gates

- The official PDF was not acquired or reviewed.
- First-period UEI and organization prefill is DAT-backed but not compiled.
- Conditional requiredness of calculated totals is DAT-backed but not compiled.
- Semantic mappings remain unreviewed and contribute nothing to published coverage.

# Reusable lesson

Optional calculated subtrees require a presence-aware materialization contract, not merely a correct arithmetic formula. Exact wire constraints and absence behavior should be exercised before a banked form is called ready for human review.

[records delivery evidence for](../workstreams/private-simpler-form-runtime-delivery.md)

[provides implementation evidence for](../tasks/migrate-next-overlap-cohort.md)

[informs](../roadmap-items/portfolio-scale.md)
