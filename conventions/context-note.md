---
type: Convention
title: Context Note
governs: Context Note
path: context-notes/
fields:
  required:
    - title
    - timestamp
  optional:
    - description
    - tags
sections:
  - Summary
freshness_horizon: 24h
browse_collapsed: true
---
# Context Note

An agent's cross-session orientation note: what happened, what was decided, and what's still open. Create one with `new "Context Note" <id>` (scaffolds the `# Summary` section under `context-notes/`), read it with `doc read`, and edit it with `doc update` / `doc write`. This recipe retains `timestamp` as an explicit compatibility field and uses the Superbee-specific `freshness_horizon` Kind extension so `superbee status` can surface notes older than 24h. In an OKF v0.2 bundle, `generated.at` remains the standard meaningful-change clock when provenance is present.

## Declaring a kind convention

A kind convention is a plain OKF doc (`type: Convention`) living under `conventions/`. Its FRONTMATTER is the only part core parses (this prose is not). Supported frontmatter keys:

- `governs` (required, non-empty) — the `type` value this convention governs.
- `title` (optional) — display title; defaults to `governs`.
- `description` (optional) — the kind's purpose and intended use.
- `path` (optional) — canonical bundle-relative path prefix instances are scaffolded under (e.g. `roadmap/`).
- `fields.required` — list of field names an instance MUST carry (non-empty).
- `fields.optional` — list of field names an instance MAY carry.
- `fields.descriptions` — a MAP of `field name -> human guidance` for declared fields.
- `fields.values` — a MAP of `field name -> list of allowed values`. This is the ONLY place an enum constraint goes — never a top-level `enum:`/`enums:`/`values:`/`constraints:` key, and never a field named directly at the top level either.
- `sections` — list of expected level-1 (`# Heading`) body-section names. Declare only the headings EVERY instance must carry (this Context Note kind declares just `Summary`, the one section `new "Context Note"` scaffolds and every instance carries).
- `freshness_horizon` — a Superbee Kind extension using `<n>(m|h|d)`, e.g. `24h`, `30d`, `15m`.

Worked example (a `Roadmap Item` kind, with an enum-restricted field and expected sections):

```yaml
---
type: Convention
title: Roadmap Item
governs: Roadmap Item
description: A durable line of work that groups related tasks.
path: roadmap/
fields:
  required: [title, superbee_progress_status]
  optional: [horizon]
  values:
    superbee_progress_status: [planned, active, done]
  descriptions:
    title: A concise summary of the outcome.
    superbee_progress_status: The roadmap item's current workflow progress.
    horizon: The expected delivery window.
sections: [Why, "Done when"]
freshness_horizon: 30d
---
```
