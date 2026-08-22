# Portable grants form contract v2

`schema.json` is the producer-neutral boundary for the portable form system. It validates three
document types:

- `portable-grants-form-catalog/v2`, which indexes source evidence and authored declarations;
- `portable-grants-form-declaration/v2`, which any authoring tool may emit; and
- `portable-grants-form-bundle/v2`, which neutral consumers and adapters load.

TypeSpec, directly authored JSON, and a future form builder are peer producers. Consumers depend
on this contract and the referenced standard artifacts, not on a producer's source language.

The contract deliberately keeps four identities separate:

- `validation_fragment_id` identifies a concrete entry in the hashed validation-fragment registry.
  Distinct `question_id` values may deliberately use the same fragment;
- `schema_id` identifies the question schema artifact that applies that validation shape;
- `question_id` identifies the stable semantic question; and
- `binding_id` identifies one occurrence of that question in one form.

Every occurrence carries its own role, cardinality, repetition context,
canonical projection path (`form_pointer`), exact occurrence-evidence pairs (`source_ref` plus typed
locator), target mapping references, current semantic-identity review state, and ordered review
events. Two occurrences remain distinct even
when they use the same question in the same role. Shared labels or validation shapes do not
establish semantic equivalence.

Semantic-review events are specifically reviews of the declared semantic identity, not XML mapping
or implementation parity. `agent_proposed` may have no event because proposal is not review.
Reviewed, accepted, and published are separate gates: an accepted occurrence is not published unless
the independently reviewed form-level boundary permits published coverage.

The event list is ordered and event IDs are unique within the declaration. Contract validation does
not claim to make static JSON append-only; repository history supplies the cross-version audit trail.

Contract v1 remains available for existing producers and consumers. V2 is an explicit breaking
version because occurrence provenance and review events are now required rather than inferred.

Consumer-specific artifacts are named under `adapters`. The contract validates their hashed
descriptors and configuration envelope without interpreting their content. Simpler-only database
IDs, runtime type names, instruction IDs, runtime versions, and rule artifacts remain in that
namespace. The Simpler adapter is therefore one consumer, not part of the canonical semantic model.

Canonical declarations and this compact contract are source-controlled. Resolved runtime
oracles, parity packages, analytical exports, and workbooks are deterministic CI build artifacts.
