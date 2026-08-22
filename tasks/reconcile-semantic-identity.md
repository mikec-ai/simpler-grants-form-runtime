---
type: Task
title: Reconcile question identity and occurrence semantics
priority: P0
assignee: codex-primary
description: >-
  Separate reusable validation shape, semantic question identity, and each
  role-qualified occurrence. Acceptance: repeated same-question/same-role
  occurrences remain distinct by context; each occurrence preserves cardinality,
  source evidence, mapping review event, reviewer/rationale when known, and
  projection path without conflating shared shape with shared meaning.
superbee_progress_status: done
superbee_updated_by: codex-primary
generated:
  by: 'process:superbee'
  at: '2026-08-22T14:11:42.730Z'
---
[depends on](inventory-and-preserve-form-corpus.md)

Completed as experimental evidence in commit `1c7d83ca6`. The work established that validation shape, semantic question identity, and occurrence context are distinct, and it preserved proposed/reviewed/accepted publication states. Under [the canonical PR #44 architecture decision](../decisions/pr44-canonical-authoring-architecture.md), these findings will be ported as review rules and sidecar evidence; contract v2 and its separate identity registry will not be merged.
