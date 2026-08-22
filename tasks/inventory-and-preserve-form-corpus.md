---
type: Task
title: Inventory and preserve the 28-form corpus and draft PR evidence
priority: P0
assignee: codex-primary
description: >-
  Generate a reproducible disposition report for the 28 forms and PRs #8–36,
  recording each unique source, oracle, mapping, test, commit, hash, and
  keep/migrate/archive destination. Acceptance: every unique artifact has a
  destination and no PR or branch is closed or deleted before preservation is
  verified.
superbee_progress_status: done
superbee_updated_by: codex-primary
generated:
  by: 'process:superbee'
  at: '2026-08-22T13:46:43.288Z'
---
# Completion

Implemented and pushed as private commit `1d9371b2e`. The deterministic inventory covers PRs #8-36, 53 commits, the separate pinned 28-form corpus tip, and 635 content-addressed artifact versions with zero fallback dispositions.

Eight minimal annotated archive tags were pushed only to the private `mikec-ai` remote. Remote verification confirmed their tag-object and peeled commit OIDs and proved all 53 commits not reachable from `mirror-base` are durably preserved. No PRs or branches were closed or deleted.

The verified build report is generated under `build/form-corpus-inventory/` and published by CI rather than committed. Verified report content hash: `89d5e74b2b94c6236177bcced88a603970e7452d3a67e8945978303d75e1110a`.
