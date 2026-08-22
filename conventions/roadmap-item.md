---
type: Convention
title: Roadmap Item
governs: Roadmap Item
path: roadmap-items/
links:
  contains: Task
link_descriptions:
  contains: Tasks whose delivery is governed by this roadmap commitment.
fields:
  required:
    - title
    - superbee_progress_status
  optional:
    - description
    - sequence
  values:
    superbee_progress_status:
      - queued
      - active
      - done
  terminal:
    superbee_progress_status:
      - done
---
# Roadmap Item

A durable line of work spanning multiple tasks — the granular form of the single
roadmap spine doc. An item CONTAINS its tasks via links carrying the text `contains`;
backlinks from a task answer "which item owns this". An item's progress is DERIVED,
never stored: list its contained tasks and read their workflow states (the rollup). `progress_status`
tracks the item itself: `queued` (not started) → `active` (any contained task moving)
→ `done` (all contained tasks done or canceled).
