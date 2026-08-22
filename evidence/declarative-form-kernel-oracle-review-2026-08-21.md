---
type: Architecture Review
title: 'Declarative form kernel oracle review, 2026-08-21'
description: >-
  Migrated independent review of the initial declarative-kernel canary from the
  prior Aslite bundle.
tags:
  - migrated-from-aslite
  - review
superbee_updated_by: codex
---
# Review scope

This independent review was performed only after `notes/billy-daly-form-architecture-oracle-2026-08-21` was written and synced. It evaluates:

- `notes/declarative-form-kernel-reset-2026-08-21`;
- `notes/declarative-form-kernel-independent-critique-2026-08-21`;
- `notes/declarative-form-kernel-canary-2026-08-21`;
- exact commit `d306e684e38a5e7f73f75cfebfe4dcc442dce68a` in the private `simpler-grants-form-runtime` mirror;
- the PR #6 seam at `d3f80fe16447c0a8b567a71d127d404b89906878`;
- Simpler's existing `form_schema/shared/` layer; and
- the open PR #1 through #36 topology as of August 21, 2026.

The review used Billy's transcript oracle as the acceptance standard and honored the later decision that TypeSpec and the CommonGrants question bank are optional compatibility inputs, not dependencies. No code, branch, pull request, or existing plan was modified. The focused portable-bundle and resolved-package test files were run independently: 26 tests passed.

# Verdict

**Promising architectural canary; do not scale it to the contact family yet.**

Commit `d306e684e` proves the most important narrow fact: two form schemas visibly compose the same directly authored question schema through standard `$ref`, and the adapter contains no form-name branches. That is materially closer to Billy's architecture than the Python component-builder train.

However, the current implementation does not yet satisfy the portable-kernel boundary described by the plan or transcript. It introduces a second package/loader path beside PR #6, makes bundle verification depend on the Simpler repository, requires CommonGrants mappings, and cannot faithfully represent multiple occurrences of the same question within one form. Those are foundation issues rather than expected missing-form content. Correct them before adding the remaining contact questions.

# Must-fix architecture findings

## P0. The bundle is not independently verifiable outside the Simpler repository

Evidence:

- `api/src/form_schema/portable_form_bundle.py:18-19` imports Simpler `FormType` and `Form` at module import time.
- `api/src/form_schema/portable_form_bundle.py:303-307` requires both a bundle root and a Simpler repository root.
- `api/src/form_schema/portable_form_bundle.py:485-501` resolves and hashes source evidence from that repository.
- `form-specs/manifest.json:69-74` and `114-119` use existing Simpler Python form files as the pinned source evidence.
- `api/tests/src/form_schema/test_portable_form_bundle.py:119-126` calls the Simpler-coupled loader before demonstrating a standards-only validator, so it does not prove that an independent consumer can load and verify a copied bundle.

Impact: another codebase can read individual schemas, but it cannot verify the declared portable bundle or run the analytical projection without the Simpler checkout and Python module. This weakens Billy's "plunk them in a totally different code base" test.

Correction:

1. Split a dependency-neutral bundle model, validator, reference registry, and analytical projector from the Simpler adapter.
2. Package evidence snapshots inside the bundle or represent external evidence with exact URL/repository/revision/path/hash records that do not require a Simpler checkout.
3. Add a test that copies only the portable bundle and neutral library into an isolated directory/process and validates, analyzes, and renders it without importing `src.*`.

## P0. The canary bypasses the PR #6 immutable resolved-package seam

Evidence:

- `PortableFormBundle.to_form` directly constructs the native `Form` at `api/src/form_schema/portable_form_bundle.py:199-237`.
- It sets `form_rule_schema` and `json_to_xml_schema` directly at `:231-232` rather than compiling a resolved package.
- PR #6 already defines the verified immutable artifact boundary and native materialization in `api/src/form_schema/resolved_form_package.py:25-111` and `:388-535`.

Impact: the reset now has two loaders, two manifests, two digest models, and two direct `Form` adapters. This recreates parallel architecture and makes branch-by-abstraction harder.

Correction: the neutral compiler should emit the immutable resolved artifact set accepted by one hardened package seam. The Simpler adapter should translate that package into `Form`. Either evolve the PR #6 contract generically or make the portable compiler's output an explicit input to it; do not maintain two peer runtime package abstractions.

## P0. Bindings cannot represent repeated or role-distinct occurrences of one shared question

Evidence:

- XML records are keyed only by `question_id` in both mapping files (`form-specs/mappings/*.mappings.json:18-25`).
- The loader looks up XML metadata as `xml_fields[question_id]` at `api/src/form_schema/portable_form_bundle.py:245-260` and `:467-470`.
- Analysis converts each form's questions to a `set` at `:243-268`.
- Binding validation checks that each declared binding contains its question, but does not prove every composed question occurrence has a binding (`:423-470`).

Impact: a form that uses the same semantic question in multiple roles or repeated structures cannot preserve distinct pointers and XML mappings. Undeclared `$ref` occurrences can also disappear from the analytical projection without failure. Full Key Contacts and SF-424 will exercise exactly this case.

Correction:

- Give every occurrence a stable `binding_id` and bind `question_id`, role, form pointer, cardinality/context, mapping reference, and review state at that occurrence.
- Key XML and target mappings by binding/occurrence, not solely by question identity.
- Preserve occurrence rows in the association table while separately deduplicating question IDs for question-frequency and Jaccard calculations.
- Fail closed unless every portable question reference occurrence is represented exactly once, or explicitly marked as a non-question structural composition.

## P1. CommonGrants is structurally mandatory despite the no-dependency decision

Evidence:

- The mapping contract requires exactly `common_grants` and `xml_fields` at `api/src/form_schema/portable_form_bundle.py:416-421`.
- Native materialization always injects CommonGrants mappings at `:208-210`.
- Both mapping artifacts require `common_grants` sections (`form-specs/mappings/*.mappings.json:2-17`).

Impact: a directly authored portable form cannot satisfy the bundle contract without declaring a CommonGrants translation. This is a schema-level dependency even though TypeSpec is absent.

Correction: make mappings a collection of optional named targets. The portable core should validate each installed mapping profile generically; the Simpler adapter may consume a CommonGrants mapping when present. Absence must be an explicit status, not a contract failure.

## P1. Review state and coverage cannot progress beyond the canary

Evidence:

- Every binding is required to equal `agent_proposed` at `api/src/form_schema/portable_form_bundle.py:462-466`.
- Every form's semantic state is required to remain `agent_proposed`, ineligible, and not ready at `:472-483`.
- `accepted_mappings` is hardcoded to zero at `:285-293`.

Impact: the declared `v1` contract cannot represent human-reviewed or accepted mappings, and published metrics can never be derived from actual review state. This conflicts with the analytical deliverable and the project's claims boundary.

Correction: add an explicit governed lifecycle such as proposed, agent-reviewed, human-reviewed, accepted, rejected, and superseded; define exactly which states contribute to each metric. Derive counts rather than hardcoding them. Keep the current canary records proposed.

## P1. Source provenance pins implementation evidence, not authoritative form evidence

Evidence:

- `form-specs/manifest.json:69-74` and `:114-119` identify native Python implementations as each form's sole `source_evidence`.
- The XML sidecars contain XSD URLs but no retrieved version, digest, or local evidence artifact (`form-specs/mappings/*.mappings.json:19-24`).
- The shared question schema has no direct source or derivation record (`form-specs/schemas/questions/organization-legal-name.schema.json:1-10`).

Impact: hashes prove consistency with the current implementation, not correctness against official XSD, DAT, PDF, or instructions. The canary's semantic and XML claims cannot yet be independently reconciled.

Correction: distinguish authoritative source, existing-implementation oracle, and agent derivation. Pin exact URL/repository, revision/version, retrieved artifact hash, and relevant locator. Attach question and binding provenance to the declarations that depend on it.

## P1. The namespace makes Simpler appear to own the portable semantic kernel

Evidence: every question and form `$id` uses `https://schemas.simpler.grants.gov/...` in `form-specs/manifest.json:10,19,28` and the schema files.

Impact: URI identity is technically portable, but the chosen authority contradicts the stated dependency-neutral ownership boundary and makes independent governance or later extraction harder.

Correction: select a durable, consumer-neutral namespace before IDs proliferate. Record alias/migration rules for existing Simpler shared-schema URIs rather than silently replacing them.

## P1. Existing Simpler shared schemas were bypassed rather than reconciled

Evidence:

- Existing Simpler forms already reference `COMMON_SHARED_V1.field_ref("organization_name")`, including Key Contacts and SF-424.
- `api/src/form_schema/shared/common_shared.py:126-144` defines the existing organization-name schema and URI.
- The canary introduces a new equivalent-looking schema and identity without a reconciliation record.

Impact: two shared identities now coexist, and similar constraints are being treated as likely equivalence without a formal reuse/adapt/migrate decision. This undermines the plan's explicit reconciliation gate.

Correction: add a machine-readable compatibility record comparing source, constraints, semantics, roles, and consumers. Decide whether the portable schema supersedes, aliases, imports, or intentionally diverges from `COMMON_SHARED_V1.organization_name`.

# Expected canary incompleteness, not architecture failure

These omissions are acceptable at this checkpoint if they become explicit gates:

- only one question and two partial form schemas are modeled;
- no calculations, conditions, prefill, lifecycle behavior, or XML runtime plan is emitted;
- the JSON Forms adapter supports only `Control`, `Group`, and `VerticalLayout`;
- there is no full Key Contacts/SF-424 golden parity comparison;
- the independent renderer proof is only JSON Schema validation, not presentation and behavior;
- accessibility, production readiness, policy approval, and accepted semantic equivalence remain out of scope.

One UI caution should be resolved before expansion: the current adapter treats `VerticalLayout` and `Group` as if both carry a section label (`api/src/form_schema/portable_form_bundle.py:138-159`), but no JSON Forms schema/conformance validation is run. Use standard JSON Forms structures where possible, document any extension, validate every UI scope against the data schema, and add an independent JSON Forms consumer test.

# What is aligned and worth preserving

- Standard Draft 2020-12 `$ref` visibly composes one question into two form schemas (`form-specs/schemas/forms/*.schema.json:8-14`).
- The semantic question has a stable ID and the two occurrences preserve different form pointers and labels.
- Portable declaration files live outside `api/` and execute no Simpler code.
- Unknown manifest fields, path escapes, hash drift, dangling references, and unreviewed publication claims fail closed.
- The adapter source contains no form IDs or form-specific branches.
- The same declared bindings drive question associations and pairwise overlap.
- Role and mapping review status are explicit, even though the current lifecycle needs generalization.
- TypeSpec is absent and no CommonGrants question-bank import is required to define the JSON Schema.
- The plan correctly preserves runtime capabilities, source evidence, and parity tests while parking Python component builders.

# Plan review

The current reset plan is substantially aligned with Billy's transcript oracle. It correctly chooses referenced JSON Schema as the portable source, separates UI/behavior/mapping/provenance concerns, treats CommonGrants and TypeSpec as optional, targets a generic Simpler adapter, preserves analysis, and sequences an incremental pilot before the budget family.

The plan needs two clarifications in execution, not a conceptual rewrite:

1. "Prototype may live in the private runtime repository" must not allow the neutral loader, validator, analysis projector, or namespace to depend on Simpler. Co-location is acceptable; dependency direction is not.
2. "Adapt into Simpler's native Form and resolved-package seam" should select one immutable package contract rather than allowing the canary's parallel direct-to-`Form` path.

The prior critique's recommendation to initially use CommonGrants TypeSpec is superseded by the current plan and user decision. Its remaining corrections, especially standards-based separation, role/cardinality caution, shared-schema reconciliation, and analysis during each pilot, remain valid.

# Recommended branch, commit, and PR strategy

## Replace the fragile PR train with two vertical checkpoints

The PR #1-36 topology is a long dependency chain. PRs #1, #3, #4, #5, and #6 form the useful runtime foundation; PRs #8-36 are primarily an evidence quarry and should not remain the base chain for the reset.

### Checkpoint A: consolidate and merge the runtime foundation

Create one integration PR from the PR #6 head to the private default branch `mirror-base`, preserving the existing logical commits for nested repetition, calculations, conditions, XML runtime, and the resolved-package seam. Retitle/descope it as the generic runtime foundation. Once its combined CI and focused review pass, merge it into `mirror-base` and close the component PRs #1/#3/#4/#5/#6 as merged or superseded, with links to the integration PR.

This is preferable to merging the five stacked PRs one by one because it gives reviewers one coherent diff against main and eliminates base-branch churn. The individual commits preserve forensic and review boundaries without preserving the fragile PR dependency chain.

After Checkpoint A merges, rebase `codex/declarative-form-kernel` onto the updated `mirror-base`. Do not base future reset work on PR #8-36.

### Checkpoint B: one complete portable-kernel vertical pilot

Keep the contract, neutral validation/projection, generic Simpler adapter, Key Contacts/SF-424 declarations, parity evidence, and independent consumer in one draft PR targeting updated `mirror-base`. Do not open the current `d306e684e` as the review checkpoint: doing so would prematurely anchor discussion on the second loader and repository-coupled boundary.

Open the draft after the P0 corrections are committed and the portable bundle can be independently verified and compiled through the single resolved-package seam. This is before the two forms are complete, allowing early architecture feedback without creating another stacked PR. Keep it draft until the full Key Contacts/SF-424 vertical proof passes the oracle gates.

Recommended commit granularity inside that one PR:

1. neutral bundle contract, stable identity/binding model, provenance/review lifecycle, and negative conformance tests;
2. deterministic compiler to the existing resolved-package contract plus the thin Simpler adapter;
3. independent standards consumer and analysis projections;
4. complete shared organization/contact declarations and Key Contacts composition;
5. SF-424 composition plus golden schema/UI/XML/behavior comparison and explicit exceptions;
6. documentation, migration ledger, and final oracle conformance report.

Each commit should be independently testable and should not add a new PR dependency.

## Preserve evidence without carrying the old architecture forward

Keep PRs #8-36 and their remote heads read-only until salvage is complete. Create a migration ledger on the reset branch that records, for every imported artifact or test, the source PR, exact commit, source path/hash, disposition, and destination. Bring forward source packages, parity fixtures, formulas, conditions, browser tests, and analysis expectations in the vertical slice that uses them. Do not merge or cherry-pick Python component builders merely to recover their tests.

This preserves auditability while preventing the parked branches from becoming runtime or merge dependencies.

## Merge cadence after the pilot

Merge Checkpoint B into `mirror-base` as soon as the full two-form pilot satisfies the oracle; do not wait for the R&R Budget family or a larger form count. Start the budget stress test from that newly updated main branch and target main directly with one bounded vertical PR. Repeat that cadence: one completed architectural/form-family proof merged to main, then the next branch from current main. Avoid PR-per-question, PR-per-component, and PRs based on other unmerged form branches.

## Preserve a clean path to future HHS upstream contributions

Treat the private mirror as a proving ground, not as the branch history that HHS must eventually review. Keep the commits within each private vertical PR linear, single-purpose, tested, and cherry-pickable. Avoid merge commits between experimental branches, generated-file noise mixed with runtime changes, and commits that combine private analysis artifacts with production code.

Separate two commit classes:

- **production candidates:** generic runtime behavior, portable contracts, adapters, validation, tests, and narrowly necessary documentation that could plausibly be proposed upstream;
- **private evidence:** source snapshots, large parity fixtures, analytical workbooks, migration ledgers, internal strategy, and oracle reports that establish confidence but do not belong in HHS history.

Private PRs are useful as review and CI surfaces, but they are optional evidence of development history, not future upstream PR dependencies. When the architecture is ready to propose to HHS, fetch current HHS `main`, create a fresh branch from that exact upstream commit, and reconstruct the smallest coherent upstream change by cherry-picking or re-implementing the production-candidate commits. Re-run upstream tests and resolve drift on that clean branch. Open multiple upstream PRs only where each one is independently useful and mergeable; do not recreate the exploratory PR #1-36 stack or expose private provenance.

Maintain a private provenance ledger mapping each clean upstream commit back to the private proof commit, tests/evidence used, and any intentionally omitted private artifacts. This preserves auditability without forcing internal research history into the public contribution.

# Next gates in order

1. Consolidate and merge the generic PR #1-6 foundation to `mirror-base`.
2. Split neutral kernel services from the Simpler adapter and remove repository-root verification dependency.
3. Unify compilation with the PR #6 resolved-package seam.
4. Fix occurrence-level bindings, optional mapping targets, review lifecycle, neutral IDs, provenance, and shared-schema reconciliation.
5. Add a genuinely independent copied-bundle consumer test.
6. Open the single draft kernel-pilot PR.
7. Complete Key Contacts and SF-424 parity plus analytical projections.
8. Review against `notes/billy-daly-form-architecture-oracle-2026-08-21`; merge to main when green.
9. Begin the R&R Budget stress test from updated main.

# Claims boundary

The canary establishes visible `$ref` reuse and a plausible adapter direction. It does not yet establish a dependency-neutral portable bundle, full multi-consumer equivalence, source parity, semantic acceptance, or production readiness. Those claims should remain withheld until the corresponding gates above pass.

[about](../projects/grants-strategy.md)

[informs](../workstreams/grants-form-question-bank-and-roadmap.md)

[informs](../workstreams/private-simpler-form-runtime-delivery.md)
