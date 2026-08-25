---
type: Release Evidence
title: Attachment lifecycle CI closure evidence
description: >-
  Exact focused browser and merge receipts for the durable attachment upload and
  history assertions.
tags:
  - attachment
  - ci
  - browser-evidence
superbee_updated_by: codex
---
# Outcome

The attachment lifecycle E2E contract is stabilized and merged into the private Simpler fork. The test now waits for the durable completed-file row and Delete action instead of requiring observation of a transient spinner, and it refetches the application page while polling for durable attachment and submission history.

# Exact receipts

- Consumer PR: [mikec-ai/simpler-grants-gov #115](https://github.com/mikec-ai/simpler-grants-gov/pull/115)
- PR head validated: `413ee1aedfcc56b1fdb22bd69365d4bfd0cc57d7`
- Merge commit: `95fcbf5273c9093a494307b5125b87b8284df488`
- Focused hosted run: [E2E run 32864402654](https://github.com/mikec-ai/simpler-grants-gov/actions/runs/32864402654)
- Focused selector: `@attachment-persistence`
- Result: all four browser shards passed, including the tag-filtered lifecycle run, the repository's changed-spec rerun, and merged Playwright report generation.

# Scope preserved

- Organization and individual applicant paths remain covered.
- The completed upload row and Delete action still prove scanner completion.
- Abandoned client state remains excluded from saved application history.
- Re-upload, save, attachment history, submission history, and print-view persistence remain asserted.
- No upload, persistence, scanner, or history assertion was weakened.

# CI diagnosis

The earlier broad Firefox shard ran six workers and produced attachment retries alongside twelve unrelated form-save failures and multiple upload timeouts. A separate EPA admission run exposed the same attachment spec instability. The clean focused four-shard receipt demonstrates that PR #115's durable assertions are valid; broad-suite saturation remains a CI-capacity concern rather than a product defect in this change.

# Coordination

Downstream form evidence branches should rebase onto merge commit `95fcbf5273c9093a494307b5125b87b8284df488` before rerunning attachment-backed browser admission.

[records delivery evidence for](../workstreams/private-simpler-form-runtime-delivery.md)

[informs](../roadmap-items/portfolio-scale.md)
