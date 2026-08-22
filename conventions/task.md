---
type: Convention
title: Task
governs: Task
description: >-
  A concrete unit of work that can be claimed, prioritized, assigned, and
  completed.
path: tasks/
links:
  depends on: Task
fields:
  required:
    - title
    - superbee_progress_status
  optional:
    - priority
    - assignee
    - description
  values:
    superbee_progress_status:
      - todo
      - in_progress
      - blocked
      - done
      - canceled
  terminal:
    superbee_progress_status:
      - done
      - canceled
  descriptions:
    title: A concise human-readable summary of the work.
    superbee_progress_status: The task's current workflow state.
    priority: >-
      Relative urgency used to order the work; follow the bundle's adopted
      priority scale.
    assignee: The person or agent currently responsible for the task.
    description: 'The task''s scope, context, acceptance criteria, and other working details.'
freshness_horizon: 30d
---
# Task

A unit of work, composed entirely from lite primitives — no bespoke task engine.
A task is a `type: Task` doc; its logical `progress_status` is a validated enum; its DEPENDENCIES are
typed `depends on` cross-links to prerequisite task docs (the declared link type —
the link graph IS the DAG, and `link show <id> --text "depends on"` shows both
directions); an atomic CLAIM is a compare-and-swap write flipping `progress_status` to
`in_progress` (a second claimer gets a VersionConflict). Query with `list --type Task`;
lint/orphans/staleness via `status`.
