---
type: Task
title: Implement the neutral conformance suite
priority: P0
assignee: codex-primary
description: >-
  Make authored JSON and TypeSpec emit equivalent Key Contacts contract
  semantics; validate and traverse the result in a genuinely independent
  consumer that imports neither producer nor the Simpler kernel; then exercise
  the actual Simpler registry, resolver, processFormSchema, validation,
  rendering, and XML path.
superbee_progress_status: in_progress
superbee_updated_by: codex-primary
generated:
  by: 'process:superbee'
  at: '2026-08-22T14:11:43.003Z'
---
[governed by](../decisions/pr44-canonical-authoring-architecture.md)

Work from private PR #44 commit `32a1f2d7610019a6d77de673c9a3a49be49659a1` on `codex/pr44-hardening`. First establish the existing green baseline, then complete per-build-target meta-schemas, add a hand-authored JSON fixture equivalent to a TypeSpec-emitted Key Contacts block, and validate/traverse both through an independent artifact consumer. Exercise the real Simpler resolver, registry, `processFormSchema`, validation, rendering, and XML boundary without introducing a second canonical model.
