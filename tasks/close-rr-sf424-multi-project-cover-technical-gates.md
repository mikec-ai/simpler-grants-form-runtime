---
type: Task
title: Close R&R SF-424 Multi-Project Cover technical gates
priority: high
assignee: codex-multiproject-cover-closure
description: >-
  Exact-XSD, generic projection, lifecycle, and browser closure for the portable
  Multi-Project Cover form.
superbee_progress_status: in_progress
superbee_updated_by: codex
generated:
  by: 'process:superbee'
  at: '2026-08-25T10:33:19.817Z'
---
# Summary

Close the R&R SF-424 Multi-Project Cover technical gates through the canonical declarative form architecture. Preserve exact official XSD and extraction provenance; reuse shared R&R SF-424 structure only where source-backed equivalence holds; keep semantic, policy, accessibility, and human release review explicitly separate.

Acceptance criteria:

- Exact Multi-Project XSD profile and representative mixed-payload validation, including SFLLL, pre-application, cover-letter, AOR signature, and signed date in official sequence.
- Generic projection operators are directly tested for ordering, rename/overlay behavior, collision and invalid-input cases.
- No form-specific compiler or adapter branch.
- Bounded preview, validation, save/reload, submission, XML, and browser receipts are recorded against merged producer provenance.
- R&R Subaward work remains non-overlapping.

Current implementation surfaced and is repairing an exact XML-order difference that was invisible in the 138/139 suffix-path overlap measurement.
