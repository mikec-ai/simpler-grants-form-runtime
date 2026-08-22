---
type: Architecture Oracle
title: 'Billy Daly form architecture oracle, 2026-08-21'
description: >-
  Migrated transcript-derived architectural principles and acceptance criteria
  from the prior Aslite bundle.
tags:
  - migrated-from-aslite
  - architecture
  - oracle
superbee_updated_by: codex
---
# Purpose and evidence boundary

This is an architecture-review oracle derived from the full transcript of Michael Collier's August 21, 2026 meeting with Billy Daly, recorded from 17:13:20 through 17:45:37, plus an isolated trailing utterance at 17:49:42. The transcript file is `/Users/michaelcollier/Downloads/Billy Daly's Zoom Meeting 2026-08-21 17_13(GMT-4_00).txt`.

The transcript consistently labels Billy Daly and Michael Collier. This oracle attributes only turns explicitly labeled `Billy Daly`. A few turns overlap in time and the automatic transcript contains disfluencies, likely transcription errors, and an isolated final phrase without useful context. No architectural claim depends on that trailing phrase. Concise excerpts below preserve exact wording only where it materially clarifies intent; everything else is a faithful synthesis.

This source is directional architectural guidance, not a complete specification or formal approval. Billy repeatedly qualified his observations because he had not reviewed the Simpler codebase recently or deeply. Future reviews should distinguish his stated principles from implementation details inferred by this oracle.

# Billy's stated objective

Billy wanted a clean, portable way to represent grant forms such that the same underlying form content can be used by Simpler.Grants.gov and by a different renderer or implementation. He prioritized a durable architectural foundation over merely demonstrating rapid conversion of many forms.

The central outcome is a reusable question library and declarative form composition model whose semantics remain visible outside any one application. That reusable core should support the original analytical deliverable: a list of questions, mappings between questions and forms, and evidence that the mapped questions can produce forms satisfying existing quality and compliance tests.

Billy closed by saying he remained "most interested in the mapping, the list of questions in the mapping," while recognizing comparable value in showing how that list translates into verified forms. Implementation validates and enriches the analytical product; it does not replace it.

# Directly evidenced architectural principles

## 1. Form definitions must be language-agnostic and declarative

Billy said it "shouldn't matter whether you're rendering forms in Python or TypeScript or, you know, Go." The content and behavior of a form should be represented in portable data rather than in custom functions or classes for individual questions or forms.

By declarative, Billy meant representations that could exist as JSON objects or equivalent dictionaries. The important boundary is between:

- declarative inputs that define the form; and
- implementation code that renders, validates, stores, or transforms it.

Review test: a second consumer in another language or framework must be able to consume the form declarations without importing Simpler application code or reproducing form-specific procedural logic.

## 2. Reuse must exist in the schemas, not only in a generator

Billy objected to Python components that generate expanded form-specific JSON Schemas. He described that as treating JSON Schema as a "snapshot target" while hiding reuse in custom Python inputs and functions. His desired evidence is a library of reusable JSON Schemas corresponding to shared questions, with form schemas visibly composing those definitions.

Review tests:

- Shared question schemas have stable identities and are referenced or inherited through standard JSON Schema mechanisms.
- Inspecting portable declarations reveals which questions a form reuses.
- A form-specific expanded deployment artifact is acceptable only when it is derived from, and traceable to, the referenced portable source.
- Custom per-question Python methods are not the semantic source of truth.

## 3. Use JSON Schema's native composition and validation vocabulary

Billy viewed JSON Schema as governing the information collected and its validation. He emphasized using its existing reference, inheritance, extension, and composition capabilities rather than inventing custom validation or inheritance semantics.

He was initially concerned by custom `x-*` attributes, then explicitly allowed that ancillary schemas might appear as attributes when necessary, as CommonGrants had sometimes done. His caution was narrower: custom attributes must not conceal bespoke validation or inheritance logic that belongs in JSON Schema itself.

Review tests:

- Data shape, cardinality, structural validation, and conditional validation use standard JSON Schema wherever the standard can express them.
- Custom extensions are metadata or clearly bounded declarations; they do not replace standard `$ref`/composition or require form-specific interpretation.
- Reference resolution and inheritance semantics do not depend on a proprietary application.

## 4. Separate schema concerns into declarative artifacts

Billy identified several distinct form concerns and wanted each expressed declaratively, with a hardened interface matching the consumer boundary:

- JSON Schema for collected content and validation;
- UI schema for page presentation and component choice;
- rule schema for behavior not otherwise represented;
- XML transformation or mapping rules;
- form metadata such as identifier and version.

He pointed to Simpler's `FormDefinition`-shaped boundary as encouraging because it already grouped form JSON schema, UI schema, rule schema, XML transformation rules, and metadata. His exact file recollection was exploratory, so reviewers should validate the actual code seam rather than treating his path description as normative.

Review test: concerns are separable and portable; a question or form does not require one procedural class to simultaneously generate schema, UI, rules, and XML.

## 5. Prefer existing standards, especially JSON Forms for UI

Billy recommended keeping the UI schema "as close as possible" to JSON Forms. He was uncertain whether JSON Forms offers sufficient built-in inheritance. Where an existing standard lacks composition, he allowed a very light, localized DSL or runtime layer.

Review tests:

- The portable UI contract is JSON Forms-compatible where feasible.
- Deviations are small, documented, and generic.
- Innovation is localized to gaps in existing standards, not dispersed across custom form or question classes.

## 6. Keep the portable kernel clean; adapt it to Simpler

Billy preferred portability across codebases and frameworks over binding the reusable model to Simpler's existing harness. His proposed split was a portable core plus an adapter that translates the shared declarative source into the precise inputs expected by Simpler's form renderer and runtime.

The adapter may need to absorb Simpler-specific "cruft," but that complexity must stay outside the shared kernel. The kernel should remain relatively lightweight, consistent, and untouched by runtime quirks.

Review tests:

- The portable declarations have no imports from Simpler application packages.
- Simpler-specific translation lives in a generic adapter.
- The adapter targets a hardened native boundary and contains no form-ID-specific or question-ID-specific semantic branches.
- A second clean reference consumer can use the same kernel.

## 7. Modernize incrementally through branch by abstraction

Billy explicitly recommended the branch-by-abstraction pattern: create a solid interface and swap components behind it. He rejected replacing the entire form engine in one step. The first proof should work with roughly the existing architecture by changing how declarative inputs are produced. A cleaner parallel renderer may demonstrate reduced complexity, but runtime replacement should follow adoption of the core rather than being bundled with it.

Review tests:

- The portable core works with the existing Simpler renderer through a narrow adapter.
- The migration can proceed form by form or component by component.
- Existing runtime behavior, tests, and deployment contracts remain available during migration.
- A clean reference implementation is used as a portability and simplicity proof, not as a prerequisite wholesale rewrite.

## 8. Prove multi-consumer semantic identity

Billy described the "real test" as whether the same underlying question set, UI representation, and declarative form content can live in both CommonGrants and Simpler, even if Simpler requires additional adapter artifacts. He compared this with CommonGrants opportunity-data adapters: protect a lightweight transformation kernel and tolerate framework-specific code around it.

Review tests:

- The same portable declarations can drive both a standards-oriented reference implementation and Simpler.
- Differences between consumers are adapter or renderer concerns, not divergent semantic definitions.
- Cross-consumer comparisons check content, role, cardinality, validation, and presentation semantics, not merely similar labels.

## 9. Reusable questions are semantic units, not labels

Billy's language in this transcript focused on shared questions and components. His earlier guidance, already captured elsewhere in this bundle, requires role-qualified identity for people and organizations. The August 21 guidance reinforces that a component should correspond to a question whose declarative content and validation are reusable, not merely a similarly named field.

Review tests:

- Shared IDs mean semantic equivalence, not textual resemblance.
- Role, cardinality, policy, and source-wire distinctions remain explicit.
- Proposed semantic mappings remain distinguishable from reviewed or accepted mappings.

## 10. Preserve the analytical deliverable

Billy did not abandon the form-question mapping in favor of implementation. He saw implementation as valuable evidence that the question list maps into forms that pass existing tests and quality controls.

Review tests:

- Canonical declarations generate a form-to-question association table.
- Question reuse/frequency and pairwise overlap can be derived from stable semantic identities.
- Exact XML paths and source metadata remain traceable.
- Coverage claims use reviewed mappings only; implementation or structural similarity alone does not constitute semantic acceptance.

# Examples and cautions Billy used

- Simpler's existing `shared` schema area appeared closer to the desired reusable pattern than the newly added Python `components` area. This was a directional observation made during a limited live code inspection, not a blanket endorsement of every existing shared schema.
- The PHS 398 Cover Page Supplement PR helped him see that many files were being added per form. He cautioned that this seemed heavy, while acknowledging many files might be generated artifacts required by Simpler.
- CommonGrants' question bank and form library were offered as examples of TypeSpec compiling reusable schemas and mappings. Billy did not state that TypeSpec was mandatory, that CommonGrants was complete, or that Simpler must take a runtime dependency on it.
- JSON Forms was offered as the preferred UI-schema standard, not as an absolute prohibition against a small extension for missing composition features.
- XML mappings and rules were important for parity and fidelity, but Billy did not trust existing runtime architecture enough to make it the portable semantic model.

# Tradeoffs and priorities

Billy acknowledged tension between speed of converting forms and building a clean architecture. He favored slowing the initial conversion proof enough to establish the right boundary because a fast, application-specific emitter would not support the intended pitch.

He also acknowledged tension between portability and compatibility with Simpler. His preference was portability, but his sequencing advice required sufficient compatibility to make incremental adoption palatable. The resolution is a portable core, generic Simpler adapter, and optional clean reference renderer.

He distinguished two layers of improvement:

1. establish the reusable declarative core and prove it works with the existing runtime;
2. later simplify or replace runtime machinery after the core is accepted.

These should not be attempted as one disruptive rewrite.

# What Billy did not require

- He did not require TypeSpec. He described it as CommonGrants' current way to generate JSON Schema.
- He did not require dependence on the CommonGrants question bank or assume it was complete.
- He did not prescribe a separate repository in this meeting.
- He did not require deleting or replacing Simpler's form engine.
- He did not require adopting every existing Simpler rule, XML, or UI design as portable architecture.
- He did not say expanded resolved form packages are forbidden; his objection was making expanded snapshots the only visible semantic representation.
- He did not claim that implementation eliminates the need for semantic question mapping or human review.
- He did not approve a specific JSON sidecar vocabulary, identifier scheme, compiler implementation, or deployment model.
- He did not fully audit the code and explicitly offered to perform a deeper tool-assisted review later.

# Acceptance criteria for future architecture reviews

A change aligns with Billy's guidance only if all mandatory criteria below remain true:

1. **Portable semantic source:** shared questions and form composition are stored in language-neutral declarative artifacts.
2. **Visible reuse:** standard JSON Schema references/composition expose reuse in the schemas themselves.
3. **Standard validation:** JSON Schema owns data structure and validation wherever expressible.
4. **Separated concerns:** UI, extra behavior, mappings, and metadata remain separate declarative concerns with explicit interfaces.
5. **Standards-oriented UI:** JSON Forms compatibility is the default; extensions are minimal and generic.
6. **Clean kernel:** portable content contains no Simpler application dependencies or form-specific executable generators.
7. **Generic adapter:** Simpler-specific translation terminates at a hardened native form boundary and does not encode per-form semantics.
8. **Incremental adoption:** the design can coexist with and gradually replace existing internals.
9. **Multi-consumer proof:** at least one independent consumer can use the same declarations.
10. **Analytical projection:** question mappings and overlap analyses derive from canonical identities while preserving review status and provenance.
11. **Semantic caution:** similar wording or structure never silently establishes question equivalence.
12. **Evidence preservation:** parity tests, source mappings, quality checks, and known exceptions survive migration.

# Evidence status and interpretation rules

- Items above labeled as Billy's statements are directly supported by turns explicitly attributed to him in the transcript.
- "Review tests" and the consolidated acceptance criteria are this oracle's operational synthesis of those statements.
- Existing bundle notes provide broader context, but they are not treated as words from this transcript.
- When this oracle conflicts with later, clearly attributable guidance from Billy, record the new evidence and supersede or qualify the relevant criterion rather than silently editing history.

[about](../projects/grants-strategy.md)

[informs](../workstreams/grants-form-question-bank-and-roadmap.md)

[informs](../workstreams/private-simpler-form-runtime-delivery.md)
