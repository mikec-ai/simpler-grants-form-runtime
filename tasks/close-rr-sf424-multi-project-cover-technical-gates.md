---
type: Task
title: Close R&R SF-424 Multi-Project Cover technical gates
priority: high
assignee: codex-multiproject-cover-closure
description: >-
  Exact-XSD, generic projection, lifecycle, and browser closure for the portable
  Multi-Project Cover form.
superbee_progress_status: in_progress
superbee_updated_by: codex-multiproject-cover-closure
generated:
  by: 'process:superbee'
  at: '2026-08-25T10:38:08.132Z'
---
# Summary

Close the R&R SF-424 Multi-Project Cover technical gates through the canonical declarative form architecture. Preserve exact official XSD and extraction provenance; reuse shared R&R SF-424 structure only where source-backed equivalence holds; keep semantic, policy, accessibility, and human release review explicitly separate.

Acceptance criteria:

- Exact Multi-Project XSD profile and representative mixed-payload validation, including SFLLL, pre-application, cover-letter, AOR signature, and signed date in official sequence.
- Generic projection operators are directly tested for ordering, rename/overlay behavior, collision and invalid-input cases.
- No form-specific compiler or adapter branch.
- Bounded preview, validation, save/reload, submission, XML, and browser receipts are recorded against merged producer provenance.
- R&R Subaward work remains non-overlapping.

## Exact-order finding

The initial 138/139 relative-path alignment did not expose a root-sequence difference. The standalone R&R SF-424 mapping orders AOR signature/date before pre-application and cover-letter attachments; the Multi-Project XSD requires SFLLL, AORInfo, pre-application, cover-letter, signature, then signed date. The initial mixed fixture omitted attachments and therefore did not exercise this constraint.

## Current receipts

- Producer PR #106 merged the initial exact XSD/profile and shared projection at commit `762d67354d1cf2447c782a85c91ba4abb4c3253b`; it is superseded for release purposes by the unmerged repair PR #107.
- Producer repair PR #107 (`5d4e2d3074d00d0139e2966abd91fd0f4345f0a2`) adds generic build-time `$moveAfter`, no form-specific compiler branch, eight focused projection tests, and the mixed SFLLL + pre-application + cover-letter + signature/date exact-XSD fixture. Both hosted checks are green; merge awaits operator review.
- Full producer preflight is green: 125 TypeScript tests, 370 Python tests with 10 skips, 8 projection-operator tests, 35 exact XSD profiles/fixtures, 320 blocks, and 1,709 validated artifacts.
- Consumer PR #112 is open and unmerged at clean pushed head `496d07979e09a80dbcb980a574028a60d73ec221`. Earlier focused preview/validation/submission/XML/provenance coverage was 17/17 green, with Black/Ruff/mypy green; repaired mixed-payload coverage must be reapplied after the dependency sequence below.
- Broad consumer form-spec execution produced 386 passes. Two errors were local database infrastructure only (`grants-db` unavailable). One unrelated brittle global-revision assertion was isolated into test-only consumer PR #113 at clean pushed head `9db239c1d24ed9ca74d2c979952d4b471aa0c291`; it now validates immutable bundle provenance plus exact form/shared-artifact hashes so later producer promotions do not invalidate the repair receipt.
- Hosted bounded browser evidence for the repaired consumer commit remains pending. Consumer merge is not authorized until producer repair review/merge, rebase, full checks, and browser evidence are complete.

## Sequencing dependency

Do not resynchronize PR #112 yet. The repair producer revision also contains the Project Abstract XML target, and Project Abstract is already in the consumer’s 42-form selection while that target has not landed on consumer `main`. Synchronizing now would create prohibited Project Abstract drift in #112. Required order: PR #93 scanner/isolation, then Project Abstract consumer PR #111 browser evidence and merge, then merge reviewed producer repair PR #107, rebase and resynchronize #112 from that merged producer provenance, add the repaired mixed lifecycle/XML fixture, run full checks and bounded browser evidence, and only then consider #112 merge.

## Separate gates

Human semantic equivalence, policy interpretation, accessibility, and release acceptance remain open and are not implied by these technical receipts.
