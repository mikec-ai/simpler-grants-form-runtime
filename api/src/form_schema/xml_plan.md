# Source-pinned XML plans

`compile_xml_plan` converts a versioned `source-pinned-xml-plan/v1` document into
the XML transformation configuration used by the application runtime. The plan
keeps wire-format facts separate from application-facing field names:

- the source set pins the root XSD and every dependency by reference and SHA-256;
- the document tree records expanded QNames, exact child order, occurrence
  bounds, exclusive choices, constants, and source selectors;
- value origins identify application pointers without inferring semantics; and
- an optional reviewed runtime profile may map those pointers to existing form
  fields.

Callers provide a local source root and the source manifest used to build the
plan. Compilation resolves every declared source below that root, verifies its
bytes and complete source graph against the recorded SHA-256 values, and verifies
the canonical manifest digest before any runtime configuration is emitted. Every
node-level provenance reference must match one of those verified sources. A
reviewed runtime profile is likewise content-addressed and carries reviewer,
timestamp, and evidence references for the profile and each binding.

The compiler is deterministic and fail-closed. It rejects unresolved values,
unreviewed runtime bindings, discontinuous order, invalid cardinality, missing
provenance, unsafe namespace mappings, and XML shapes the runtime cannot yet
serialize faithfully. Compiled rules retain their source provenance and the
complete source-plan identity under `_xml_config.source_plan`.

## Current boundary

The first contract supports:

- qualified roots, attributes, constants, simple values, nested objects, and
  repeating objects;
- exact per-instance namespace selection, including equal local names in
  different namespaces;
- exclusive choices and minimum/maximum occurrence enforcement; and
- single and repeated attachments in supported non-array wrapper shapes.

It deliberately rejects attachments nested in repeating rows, wrappers that mix
attachments with ordinary children, cross-namespace attachment paths, and
flattened runtime bindings whose child QNames change namespace. Those cases need
an explicit runtime representation before they can be enabled without losing XML
fidelity.

UI behavior, validation policy, population rules, and semantic field mapping are
not inferred from the XSD and remain separate reviewed contracts.
