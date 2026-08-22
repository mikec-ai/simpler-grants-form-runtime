---
type: Architecture Principles
title: Guiding principles for portable grants forms
superbee_updated_by: codex
---
# Purpose

These principles govern architecture, implementation, analysis, and review for the portable grants
form work. They distill Billy Daly's transcript-grounded architecture oracle into a concise working
standard. The full oracle remains the evidence source and retains nuance, examples, cautions, and
the boundary between direct statements and interpretation.

They remain governing until an explicit architecture decision supersedes them.

# Guiding principles

## 1. The canonical source is portable and declarative

Questions, forms, presentation, behavior, mappings, and metadata are expressed as reviewable data.
The canonical model does not depend on Simpler application code, a Python generator, or one
authoring language.

## 2. Build artifacts are the contract; authoring tools are replaceable

Directly authored JSON, TypeSpec, and a future visual builder are peer producers. They must emit the
same versioned artifact contract and pass the same conformance suite. Consumers never depend on a
producer's AST, runtime, or repository.

## 3. Reuse must be visible in the artifact graph

Shared questions and larger reusable blocks compose through standard references, principally JSON
Schema `$ref`. A generator that merely produces duplicate expanded snapshots does not preserve the
architectural value of reuse. Forms and reusable blocks follow the same recursive composition model.

## 4. Question identity is semantic; occurrences remain role-qualified

A reusable question represents stable meaning, not merely similar wording, a shared scalar type, or
a label. Every use in a form remains a separate occurrence with role, cardinality, repetition,
context, source path, mapping evidence, and review state. Sharing a validation template does not by
itself establish semantic equivalence.

## 5. Prefer established standards and ordinary mechanisms

Use JSON Schema for structure, constraints, and composition. Use JSON Forms-compatible UI artifacts
as the default presentation vocabulary. Add extensions only when a standard mechanism cannot carry
the requirement, keep them generic, and version them explicitly.

## 6. Keep concerns separate and interfaces explicit

Schema, UI, conditions, calculations, mappings, provenance, review state, and target adapters are
separate declarative concerns. Their relationships are validated, but they do not collapse into one
opaque form-specific package or executable builder.

## 7. The portable kernel never bends to a delivery target

Simpler IDs, legacy projections, runtime rule names, XML transforms, and other delivery-specific
details terminate in a named adapter. The adapter is generic across forms and produces Simpler's
existing hardened form boundary. Adding another consumer adds an adapter; it does not multiply or
reshape the canonical model.

## 8. Modernize incrementally and preserve working evidence

Use branch by abstraction. New declarations and adapters may coexist with current form
implementations while migration proceeds form by form. Preserve parity oracles, exact source
provenance, XML and validation tests, accessibility checks, known exceptions, and runtime behavior.
A migration does not turn implementation parity into source completeness or policy approval.

## 9. Prove portability with more than one consumer

A portable claim requires an independent consumer that can load, resolve, validate, and traverse
the same declarations without importing Simpler or the authoring tool. Simpler integration alone
proves compatibility with Simpler, not portability.

## 10. The analytical product derives from implementation evidence

Question inventory, form-to-question associations, pairwise overlap, and reuse curves are generated
from canonical identities and exact form occurrences. Deterministic extraction stays separate from
semantic judgment. Proposed, reviewed, accepted, and publishable mappings remain distinct; only
accepted mappings contribute to published coverage.

## 11. Correctness should fail as early as the architecture permits

Prefer authoring-time type checks, then build-time contract validation and linting, over load-time or
runtime conventions. Unknown fields, dangling references, invalid paths, cycles, stale hashes,
unbound occurrences, and target projection gaps fail closed with actionable diagnostics.

## 12. Make the central claims falsifiable

Measure new reusable questions or blocks introduced per form, resolved versus blocked behavior,
target-specific surface area, parity exceptions, and analytical coverage status. A form should get
cheaper as the bank grows. When evidence is incomplete, preserve the open question or blocker rather
than infer an answer.

# Architecture review checklist

A proposed change should answer yes to each applicable question:

1. Is the semantic decision stored in declarative, language-neutral data?
2. Is reuse visible through standard references rather than hidden in executable generator logic?
3. Are question identity and role-qualified occurrence identity both preserved?
4. Are UI, behavior, mappings, provenance, and review state separately inspectable?
5. Can a second producer emit the same contract without changing consumers?
6. Can an independent consumer use the artifacts without Simpler or the producer runtime?
7. Are target-specific details confined to a generic named adapter?
8. Does the change preserve source evidence, parity tests, and known exceptions?
9. Do proposed semantic mappings remain excluded from accepted or published metrics?
10. Does adding the form avoid a new form-specific compiler or adapter branch?

If the answer is no, the change either needs a bounded exception with an explicit retirement path or
should not establish a new architectural precedent.

# Interpretation boundary

Billy did not require TypeSpec as the only authoring language, completion of the CommonGrants
question bank before work could proceed, immediate replacement of Simpler's runtime, or blind reuse
based on label similarity. The direction is a portable declarative semantic source, standard
composition, a generic adapter, incremental migration, multi-consumer proof, and an analytical
projection derived from the same implementation evidence.

[derived-from](../evidence/billy-form-architecture-oracle-2026-08-21.md)

[governs](architecture.md)

[governs](authoring-model.md)

[governs](../reviews/pr44-current-kernel-convergence.md)

[governs](../roadmaps/declarative-form-architecture.md)
