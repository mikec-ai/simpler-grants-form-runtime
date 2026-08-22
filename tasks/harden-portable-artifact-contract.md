---
type: Task
title: Harden the provisional portable artifact contract
priority: P0
assignee: unassigned
description: >-
  Audit contract v1 for target leakage, occurrence-level provenance and review
  events, repeated occurrence identity, canonical path/projection ownership, and
  versioned UI, rule, mapping, and projection profiles. Acceptance: negative
  tests cover these boundaries and no consumer depends on a producer AST or
  unversioned opaque semantics.
superbee_progress_status: canceled
superbee_updated_by: codex-primary
generated:
  by: 'process:superbee'
  at: '2026-08-22T14:11:42.867Z'
---
[depends on](inventory-and-preserve-form-corpus.md)

[depends on](reconcile-semantic-identity.md)

Canceled by [the canonical PR #44 architecture decision](../decisions/pr44-canonical-authoring-architecture.md). Hardening now proceeds directly on PR #44's artifact graph; the provisional contract v1/v2 line remains preserved experimental evidence.
