---
type: Guide
title: Superbee collaboration guide
description: >-
  How collaborators and agents set up, coordinate, and preserve the architecture
  evidence boundary.
tags:
  - onboarding
  - coordination
superbee_updated_by: codex
---
# Grants form architecture collaboration

This Superbee bundle is the shared coordination layer for the portable grants form architecture. It holds living architecture documents, source context, decisions, roadmap commitments, and tasks. Runtime code remains in the repository; large generated oracles and analyses remain CI build artifacts.

## Setup for each collaborator

From a clone of the private repository:

```sh
npm install -g superbee@next
superbee setup --host codex --scope project
superbee sync
```

Restart Codex after the first setup so the installed skill, MCP registration, and hooks become active. The shared bundle is published on the repository's `board` branch and materializes locally under `.superbee/`; the directory is intentionally ignored on code branches.

## Canonical starting points

- `architecture/billy-proposed-form-architecture`
- `architecture/billy-proposed-authoring-model`
- `architecture/billy-deferred-designs`
- `context-notes/billy-pr44-intake-2026-08-22`
- `reviews/pr44-current-kernel-convergence`
- `roadmaps/declarative-form-architecture`

## Working rules

1. Read the relevant architecture and review documents before changing the contract or adapter.
2. Claim a task by setting its assignee and status before beginning substantial work.
3. Record decisions as durable documents and link them to the roadmap item or task they affect.
4. Preserve exact source/version/hash provenance for extracted evidence.
5. Keep deterministic extraction separate from proposed semantic mappings.
6. Only accepted mappings contribute to published coverage.
7. Treat open questions as architecture state. Do not assume a named stakeholder must answer them.
8. Run `superbee sync` before starting and after completing a meaningful unit of work.
9. Keep code PRs small and reviewable. The board coordinates work but does not replace Git history.

## Source-control boundary

Commit canonical declarations, generic compilers/adapters, contracts, tests, and concise design documentation. Publish large resolved artifacts, parity oracles, and analytical workbooks as CI build artifacts. Preserve source hashes and deterministic build receipts so any artifact can be reproduced from a named commit.

Use three artifact classes: canonical authored source; compact generated deployable artifacts that remain available to the runtime without the authoring toolchain; and large reproducible oracles and analytical outputs published as durable build evidence. Do not place runtime-required artifacts only in an expiring CI store.

## Authority boundary

The board owns decisions, tasks, dependencies, and preserved evidence context. Git owns code, versioned contracts, tests, and implementation history. CI owns current build status and generated portfolio metrics. Do not manually copy changing implementation status or form counts into the board when they can be derived from Git or CI.

Billy's proposed architecture documents are immutable evidence snapshots tied to their source PR and commit. Working recommendations belong in review or decision documents rather than edited copies of those snapshots.

[coordinates](../roadmaps/declarative-form-architecture.md)
