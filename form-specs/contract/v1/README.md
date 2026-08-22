# Portable grants form contract v1

`schema.json` is the producer-neutral boundary for the portable form system. It validates three
document types:

- `portable-grants-form-catalog/v1`, which indexes source evidence and authored declarations;
- `portable-grants-form-declaration/v1`, which any authoring tool may emit; and
- `portable-grants-form-bundle/v1`, which neutral consumers and adapters load.

TypeSpec, directly authored JSON, and a future form builder are peer producers. Consumers depend
on this contract and the referenced standard artifacts, not on a producer's source language.

The contract deliberately keeps question identity and occurrence identity separate. A reusable
question schema owns validation shape and stable question identity. Every use in a form has a
separate binding carrying role, cardinality, repetition context, mapping references, provenance,
and review state. Shared labels or shapes do not establish semantic equivalence.

Consumer-specific artifacts are named under `adapters`. The contract validates their hashed
descriptors and configuration envelope without interpreting their content. Simpler-only database
IDs, runtime type names, instruction IDs, runtime versions, and rule artifacts remain in that
namespace. The Simpler adapter is therefore one consumer, not part of the canonical semantic model.

Canonical declarations and this compact contract are source-controlled. Resolved runtime
oracles, parity packages, analytical exports, and workbooks are deterministic CI build artifacts.
