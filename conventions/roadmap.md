---
type: Convention
title: Roadmap
governs: Roadmap
links:
  contains: Roadmap Item
fields:
  required:
    - title
  optional: []
---
# Roadmap

The spine document: a single top-level roadmap doc that CONTAINS the bundle's Roadmap
Items via typed links carrying the text `contains` (`link add <roadmap> <item> --text
contains`), making the whole roadmap → item → task chain one filtered query per hop
(`link show <id> --text contains`). Progress is DERIVED, never stored: list the
contained items and read their statuses.
